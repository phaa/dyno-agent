import asyncio
import json
import time
import logging
from dataclasses import dataclass
from typing import AsyncGenerator, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import build_graph
from agents.config import ERROR_RETRY_COUNT
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

@dataclass
class UserContext:
    db: AsyncSession

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
    """
    Stream chat responses over Server-Sent Events (SSE) using LangGraph.

    This endpoint:
      1) Authenticates the user via JWT.
      2) Gets or creates a conversation for the user.
      3) Persists the incoming user message (best-effort).
      4) Executes a LangGraph workflow and streams events to the client:
         - type="status": progress updates emitted via the graph "custom" stream.
         - type="assistant": assistant responses emitted via the graph "updates" stream.
      5) Deduplicates assistant messages by message id.
      6) Persists the final assistant response once at the end (single DB write).
      7) Tracks conversation metrics (duration, etc.).
      8) Always terminates the SSE stream by sending data: [DONE].

    Streaming format:
        Each event is sent as an SSE "data" line containing a JSON payload:
            {"type": "...", "content": ...}

        The stream ends with:
            data: [DONE]

    Args:
        chat_request: Request payload containing the user message and optional
            conversation_id.
        request: FastAPI request object (used for auth context and disconnect
            detection).
        db: Async SQLAlchemy session.
        graph: Cached LangGraph instance (injected via get_graph).

    Returns:
        StreamingResponse: A text/event-stream response producing SSE events.

    Raises:
        HTTPException:
            - 400 if the conversation cannot be started due to a non-retryable
              error or the conversation does not belong to the authenticated user.
            - 404 if the user record is not found.
            - 500 if the chat session cannot be initialized.
    """
    user_email = get_user_email_from_token(request)
    user_message: str = chat_request.message
    conv_id: str | None = chat_request.conversation_id

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

    conversation_id = conversation.id # Avoid async closure issues by capturing conversation_id in a local variable
    user_name = user.fullname.split()[0]

    async def event_generator() -> AsyncGenerator[str, None]:
        start_time = time.time()
        last_ai_message_id: str | None = None
        final_assistant_response: str | None = None

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
                "retry_count": ERROR_RETRY_COUNT,  # Initial retry count
            }
            config = {"configurable": {"thread_id": f"{user_email}_{conversation_id}"}}
            context = UserContext(db=db)

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

                        if msg.id == last_ai_message_id:
                            continue
                        
                        last_ai_message_id = msg.id

                        if isinstance(msg.content, list):
                            contents = [
                                item.get("text", "")
                                for item in msg.content
                                if isinstance(item, dict) and item.get("type") == "text"
                            ]
                            response_text = "\n".join([c for c in contents if c])
                        else:
                            response_text = msg.content

                        final_assistant_response = response_text
                        yield sse({"type": "assistant", "content": response_text})

                except Exception:
                    logger.exception("Error processing stream chunk")
                    yield sse({"type": "error", "content": "Error processing response. Please try again."})

        except asyncio.CancelledError:
            # important for streaming: the client can cancel the request
            logger.info(f"Stream cancelled: user={user_email} conv={conversation_id}")
            raise
        except Exception:
            logger.exception(
                "Critical error in chat stream",
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
            except Exception:
                logger.exception("Failed to save assistant response")

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
            except Exception:
                logger.exception("Failed to track conversation metrics")

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
async def get_conversation_messages(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get messages from a specific conversation for the authenticated user."""
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
    Delete a conversation and all its associated messages.
    
    This endpoint:
    1. Authenticates the user via JWT
    2. Verifies the conversation belongs to the authenticated user
    3. Deletes the conversation and all messages from SQLAlchemy database
    4. Deletes the thread from the LangGraph checkpointer
    
    Args:
        conversation_id: UUID of the conversation to delete
        request: FastAPI request object for authentication
        db: Async SQLAlchemy session
        checkpointer: LangGraph checkpointer for thread cleanup
        
    Returns:
        Dictionary with success status
        
    Raises:
        HTTPException:
            - 400 if conversation doesn't exist or user is not authorized
            - 500 if the conversation cannot be deleted due to database error
    """
    user_email = get_user_email_from_token(request)
    conv_service = ConversationService(db=db)
    
    try:
        # Delete conversation and all messages from database
        await conv_service.delete_conversation(
            conversation_id=conversation_id,
            user_email=user_email
        )
        
        # Delete the thread from checkpointer
        thread_id = f"{user_email}_{conversation_id}"
        try:
            # LangGraph checkpointer stores state by thread_id
            # adelete_thread() deletes all checkpoints and writes for this thread
            await checkpointer.adelete_thread(thread_id)
            logger.info(f"Deleted thread {thread_id} from checkpointer")
        except Exception as e:
            logger.warning(f"Failed to delete thread {thread_id} from checkpointer: {str(e)}")
            # Don't fail the entire operation if checkpointer cleanup fails
        
        return {"status": "success", "message": f"Conversation {conversation_id} deleted successfully"}
        
    except NonRetryableError as e:
        logger.warning(f"Failed to delete conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")



