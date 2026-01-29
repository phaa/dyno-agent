import json
import time
import logging
from dataclasses import dataclass
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import build_graph
from agents.nodes.utils import strip_thinking_tags
from services.conversation_service import ConversationService
from auth.auth_bearer import JWTBearer
from auth.auth_handler import get_user_email_from_token
from core.db import get_db
from core.metrics import track_performance
from core.conversation_metrics import ConversationMetrics
from core.retry import RetryableError, NonRetryableError
from schemas.chat import ChatRequest
from middleware.rate_limit import limiter
from models.user import User

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("langchain").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

@dataclass
class UserContext:
    db: AsyncSession


def get_checkpointer(request: Request):
    """Dependency to get checkpointer from app state"""
    return request.app.state.checkpointer


@router.post("/stream", dependencies=[Depends(JWTBearer())], tags=["chat"])
@limiter.limit("20/minute") # 20 requests per minute per user
@track_performance(service_name="ChatService", include_metadata=True)
async def chat_stream(
    chat_request: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    checkpointer = Depends(get_checkpointer)
) -> StreamingResponse:
    """
    SSE chat endpoint using LangGraph.
    - Streaming is event-based (not token-based)
    - Deduplicated AI messages
    - writer() used only for status updates
    - PostgreSQL persistence is UI-only
    """

    user_email = get_user_email_from_token(request)
    user_message: str = chat_request.message
    conv_id: str | None = chat_request.conversation_id

    # Get or create conversation (with automatic retry via service)
    conv_service = ConversationService(db=db)

    try:
        conversation = await conv_service.get_or_create_conversation(
            user_email=user_email,
            conversation_id=conv_id
        )
        # Async + streaming = avoid lazy loading after await
        # Avoid conversation.user lazy load issues
        user = await db.get(User, user_email)
    except NonRetryableError as e:
        logger.error(f"Non-retryable error starting conversation: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to start conversation: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to start conversation after all retries: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize chat session")

    if conversation.user_email != user_email:
        error_msg = f"User {user_email} not found in conversation"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail="User doesn't exist.")

    # Capture conversation_id here to avoid lazy loading issues in the async generator
    conversation_id = conversation.id

    async def event_generator() -> AsyncGenerator[str, None]:
        start_time = time.time()
        last_ai_message_id: str | None = None
        final_assistant_response: str | None = None
        
        try:
            logger.info(f"Starting chat stream for user {user_email}, conversation {conversation_id}")
            
            # Initialize services with error handling
            try:
                graph = await build_graph(checkpointer)
            except Exception as e:
                logger.error(f"Failed to build graph: {str(e)}")
                error_payload = json.dumps({"type": "error", "content": "Failed to initialize AI engine"}, ensure_ascii=False)
                yield f"data: {error_payload}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # Save user message with error handling
            try:
                await conv_service.save_message(
                    conversation_id=conversation_id,
                    role="user",
                    content=user_message
                )
            except Exception as e:
                logger.warning(f"Failed to save user message: {str(e)}")
                # Continua mesmo se falhar, mas loga para auditoria

            inputs = {
                #"messages": [HumanMessage(content=user_message)],
                "user_input": user_message,
                "user_name": user.fullname.split(" ")[0],
                "conversation_id": conversation_id,
            }

            config = {
                "configurable": {
                    "thread_id": f"{user_email}_{conversation_id}"
                }
            }

            context = UserContext(db=db)

            stream_args = {
                "input": inputs,
                "config": config,
                "context": context,
                "stream_mode": ["updates", "custom"], 
            }

            # Stream processing
            async for stream_mode, chunk in graph.astream(**stream_args):
                try:
                    # STATUS STREAM (writer)
                    if stream_mode == "custom":   
                        payload = json.dumps({
                            "type": "status",
                            "content": chunk
                        }, ensure_ascii=False)
                        # Don't save status messages to DB - too much I/O overhead
                        yield f"data: {payload}\n\n" 
                        continue
                    
                    # ASSISTANT STREAM 
                    if stream_mode != "updates":
                        continue
                        
                    for _, data in chunk.items():
                        if not data or "messages" not in data:
                            continue

                        ai_messages = [
                            msg for msg in data["messages"] 
                            if isinstance(msg, AIMessage) and msg.content
                        ]

                        if not ai_messages:
                            continue

                        msg = ai_messages[-1]  # only the newest

                        if msg.id == last_ai_message_id:
                            continue  # deduplicate

                        last_ai_message_id = msg.id

                        if isinstance(msg.content, list):
                            contents = [
                                item["text"]
                                for item in msg.content
                                if item.get("type") == "text"
                            ]
                            response_text = "\n".join(contents)
                        else:
                            response_text = msg.content

                        # Strip thinking tags before sending to user
                        response_text = strip_thinking_tags(response_text) if isinstance(response_text, str) else response_text
                        
                        # Skip if content is empty after stripping
                        if not response_text or response_text.isspace():
                            continue

                        final_assistant_response = response_text
                        
                        payload = json.dumps({
                            "type": "assistant",
                            "content": response_text
                        }, ensure_ascii=False)
                        
                        yield f"data: {payload}\n\n"
                        
                except Exception as chunk_error:
                    # Log chunk processing error with full context
                    logger.error(
                        f"Error processing stream chunk: {str(chunk_error)}",
                        exc_info=True
                    )
                    error_payload = json.dumps({
                        "type": "error",
                        "content": "Error processing response. Please try again."
                    }, ensure_ascii=False)
                    yield f"data: {error_payload}\n\n"
                    continue

        except Exception as e:
            # Handle major errors with logging
            logger.error(
                f"Critical error in chat stream: {str(e)}",
                exc_info=True,
                extra={"user_email": user_email, "conversation_id": conversation_id}
            )
            error_payload = json.dumps({
                "type": "error",
                "content": "Critical error occurred. Our team has been notified."
            }, ensure_ascii=False)
            yield f"data: {error_payload}\n\n"
            
        finally:
            # Save conversation at the end (single DB operation)
            try:
                if conversation and conv_service and final_assistant_response:
                    await conv_service.save_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=final_assistant_response,
                    )
            except Exception as e:
                logger.error(
                    f"Failed to save assistant response: {str(e)}",
                    exc_info=False
                )
            
            # Track metrics if possible
            try:
                if conversation and conv_service:
                    duration_ms = (time.time() - start_time) * 1000
                    metrics_tracker = ConversationMetrics(db)
                    await metrics_tracker.track_conversation(
                        user_message=user_message,
                        assistant_response=final_assistant_response,
                        user_email=user_email,
                        conversation_id=conversation_id,
                        duration_ms=duration_ms,
                        tools_used=[]
                    )
            except Exception as e:
                # Log metrics errors but continue
                logger.error(
                    f"Failed to track conversation metrics: {str(e)}",
                    exc_info=False
                )
            
            # Log completion
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Chat stream completed for user {user_email}",
                extra={"duration_ms": duration_ms, "conversation_id": conversation_id}
            )
            
            # Always end the stream
            yield "data: [DONE]\n\n"

    # Retorna a resposta como SSE
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx compatibility for production
        }
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
        user_email=user_email,
        conversation_id=conversation_id
    )
    
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")
    
    return {"messages": messages}


