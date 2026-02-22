import asyncio
import json
import time
import logging
from typing import AsyncGenerator, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import build_graph
from agents.config import DEFAULT_ERROR_RETRY_COUNT
from services.conversation_service import ConversationService
from auth.auth_bearer import JWTBearer
from auth.auth_handler import get_user_email_from_token
from core.db import get_db
from core.metrics import track_performance
from core.conversation_metrics import ConversationMetrics
from core.retry import NonRetryableError
from schemas.chat import ChatRequest
from middleware.rate_limit import limiter
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

def _get_checkpointer(request: Request):
    return request.app.state.checkpointer

_graph_lock = asyncio.Lock()

async def _get_graph(
    request: Request,
    checkpointer = Depends(_get_checkpointer),
):
    """
    Return a cached LangGraph instance for this FastAPI process.

    This dependency lazily initializes the LangGraph graph on first use and
    stores it in request.app.state.graph so subsequent requests reuse the
    same graph (and its loaded LLM/tools), avoiding expensive rebuilds per
    request.

    Concurrency:
        Uses a process-local async lock to ensure only one coroutine builds the
        graph when multiple requests arrive simultaneously.

    Notes:
        - The cache is per Uvicorn worker/process (if running multiple workers,
          each will build its own graph once).
        - The checkpointer is injected from app state and passed to
          build_graph() during initialization.

    Args:
        request: FastAPI/Starlette request object used to access application
            state (request.app.state).
        checkpointer: Checkpointer dependency used by LangGraph for state
            persistence.

    Returns:
        A ready-to-use LangGraph instance (cached after the first call).

    Raises:
        Exception: Propagates any exception raised by build_graph() during the
            first initialization attempt.
    """
    graph = getattr(request.app.state, "graph", None)
    if graph is not None:
        return graph

    async with _graph_lock:
        graph = getattr(request.app.state, "graph", None)
        if graph is None:
            request.app.state.graph = await build_graph(checkpointer)
            graph = request.app.state.graph

    return graph

def sse(payload: dict) -> str:
    """Format a dict payload as a Server-Sent Event data block.

    Args:
        payload: JSON-serializable dictionary to send as SSE `data`.

    Returns:
        A string containing the SSE-formatted data line(s).
    """
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

@router.post("/stream", dependencies=[Depends(JWTBearer())], tags=["chat"])
@limiter.limit("5/minute")
@track_performance(service_name="ChatService", include_metadata=True)
async def chat_stream(
    chat_request: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    graph = Depends(_get_graph),
) -> StreamingResponse:
    """Stream chat responses over SSE using the LangGraph workflow.

    Produces `status` and `assistant` SSE events, deduplicates assistant
    messages by id, persists the final assistant response once, and tracks
    conversation metrics. The graph receives an `input` dict which includes
    a `retry_count` value initialized from `ERROR_RETRY_COUNT`.

    Streaming format: each SSE `data` line contains a JSON payload
    of the form {"type": "...", "content": ...}. The stream always ends
    with the sentinel `data: [DONE]`.
    """
    user_email = get_user_email_from_token(request)
    user_message = chat_request.message
    conv_id = chat_request.conversation_id

    conv_service = ConversationService(db=db)

    try:
        conversation = await conv_service.get_or_create_conversation(
            user_email=user_email,
            conversation_id=conv_id
        )
        user = await db.get(User, user_email)
    except NonRetryableError as e:
        raise HTTPException(status_code=400, detail=f"Failed to start conversation: {str(e)}")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to initialize chat session")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if conversation.user_email != user_email:
        raise HTTPException(status_code=400, detail="User doesn't exist.")

    # Avoid async closure issues by capturing conversation_id in a local variable
    conversation_id = conversation.id 
    user_name = user.fullname.split()[0]

    async def event_generator() -> AsyncGenerator:
        start_time = time.time()
        last_ai_message_id: Optional[str] = None
        final_assistant_response: Optional[str] = None

        try:
            try:
                await conv_service.save_message(
                    conversation_id=conversation_id,
                    role="user",
                    content=user_message
                )
            except Exception as e:
                logger.warning(f"Failed to save user message: {str(e)}")

            # Instead of passing the user input as a HumanMessage in the messages list within stream_args, 
            # we inject it as a separate "user_input" field in the graph state for using later in the error_llm node
            inputs = {
                "user_input": user_message, 
                "user_name": user_name,
                "conversation_id": conversation_id,
                "retry_count": DEFAULT_ERROR_RETRY_COUNT, 
            }
            config = {"configurable": {"thread_id": f"{user_email}_{conversation_id}"}}
            context = {"db": db}

            stream_args = {
                "input": inputs,
                "config": config,
                "context": context,
                "stream_mode": ["updates", "custom"],
            }

            async for stream_mode, chunk in graph.astream(**stream_args):
                # Stops processing if client disconnects to save resources (important for streaming endpoints)
                if await request.is_disconnected():
                    logger.info(f"Client disconnected: user={user_email} conv={conversation_id}")
                    break

                if stream_mode == "custom":
                    yield sse({"type": "status", "content": chunk})
                    continue

                if stream_mode != "updates":
                    continue

                try:
                    for _, data in chunk.items():
                        # Discard non message updates
                        if not data or "messages" not in data:
                            continue

                        turn_messages = data["messages"]

                        # Get the last AI message with content
                        # Dont create a list, reduces to O(n) in the worst case
                        msg = next((
                            m for m in reversed(turn_messages)
                            if isinstance(m, AIMessage) and m.content
                        ), None)
                        
                        if not msg:
                            continue

                        # We must avoid duplicate messages due to checkpointing
                        if msg.id == last_ai_message_id:
                            continue
                        
                        last_ai_message_id = msg.id

                        if isinstance(msg.content, list):
                            response_text = ""
                            for item in msg.content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    response_text += item.get("text", "")
                        else:
                            response_text = msg.content

                        final_assistant_response = response_text
                        yield sse({"type": "assistant", "content": response_text})

                except Exception as e:
                    logger.exception(f"Error processing stream chunk: {str(e)}")
                    yield sse({"type": "error", "content": "Error processing response. Please try again."})

        except asyncio.CancelledError:
            # important for streaming: the client can cancel the request
            logger.info(f"Stream cancelled")
            raise
        except Exception as e:
            logger.exception(
                f"Critical error in chat stream: {str(e)}",
                extra={"user_email": user_email, "conversation_id": conversation_id},
            )
            yield sse({"type": "error", "content": "Critical error occurred. Our team has been notified."})

        finally:
            try:
                if final_assistant_response:
                    await conv_service.save_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=final_assistant_response,
                    )
            except Exception as e:
                logger.exception(f"Failed to save assistant response: {str(e)}")

            try:
                if final_assistant_response:
                    duration_ms = (time.time() - start_time) * 1000
                    metrics_tracker = ConversationMetrics(db)
                    await metrics_tracker.track_conversation(
                        user_message=user_message,
                        assistant_response=final_assistant_response,
                        user_email=user_email,
                        conversation_id=conversation_id,
                        duration_ms=duration_ms,
                        tools_used=[], # todo
                    )
            except Exception as e:
                logger.exception(f"Failed to track conversation metrics: {str(e)}")

            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive", # For Nginx proxy compatibility
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/metrics", dependencies=[Depends(JWTBearer())])
async def get_conversation_metrics(hours: int = 24, db: AsyncSession = Depends(get_db)):
    """Get real conversation metrics from database and LangSmith"""
    metrics_tracker = ConversationMetrics(db)
    return await metrics_tracker.get_conversation_stats(hours=hours)


@router.get("/conversations", dependencies=[Depends(JWTBearer())], tags=["chat"])
async def list_conversations(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """List conversations for the authenticated user."""
    user_email = get_user_email_from_token(request)
    conv_service = ConversationService(db=db)
    
    try:
        conversations = await conv_service.get_conversations(user_email)
    except Exception as e:
        logger.error(f"Error retrieving conversations for user {user_email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve conversations")
    
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}/messages", dependencies=[Depends(JWTBearer())], tags=["chat"])
async def get_conversation_messages(
    conversation_id: str, 
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get messages from a specific conversation for the authenticated user."""
    user_email = get_user_email_from_token(request)
    conv_service = ConversationService(db=db)
    
    messages = await conv_service.get_conversation_history(
        conversation_id=conversation_id
    )
    
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")
    
    return {"messages": messages}


@router.delete("/conversations/{conversation_id}", dependencies=[Depends(JWTBearer())], tags=["chat"])
async def delete_conversation(
    conversation_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    checkpointer = Depends(_get_checkpointer),
):
    """
    Delete a conversation and all its associated messages:
    - Deleting the conversation and all messages from SQLAlchemy database
    - Deleting the thread from the LangGraph checkpointer (with automatic retry)
    
    Args:
        conversation_id: UUID of the conversation to delete
        request: FastAPI request object for authentication
        db: Async SQLAlchemy session
        checkpointer: LangGraph checkpointer (passed to service)
        
    Returns:
        Dictionary with success status
        
    Raises:
        HTTPException:
            - 400 if conversation doesn't exist or user is not authorized
            - 500 if the conversation cannot be deleted due to database error
    """
    user_email = get_user_email_from_token(request)
    conv_service = ConversationService(db=db, checkpointer=checkpointer)
    
    try:
        # Delete conversation and all messages from database, plus checkpointer cleanup
        # with automatic retry on transient failures
        await conv_service.delete_conversation(
            conversation_id=conversation_id,
            user_email=user_email
        )
        
        return {"status": "success", "message": f"Conversation {conversation_id} deleted successfully"}
        
    except NonRetryableError as e:
        logger.warning(f"Failed to delete conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")



