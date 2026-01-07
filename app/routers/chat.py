import json
import time
from dataclasses import dataclass
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import build_graph
from models.user import User
from services.conversation_service import ConversationService
from auth.auth_bearer import JWTBearer
from auth.auth_handler import get_user_email_from_token
from core.db import get_db
from core.metrics import track_performance
from core.conversation_metrics import ConversationMetrics
from schemas.chat import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])

@dataclass
class UserContext:
    db: AsyncSession


def get_checkpointer(request: Request):
    """Dependency to get checkpointer from app state"""
    return request.app.state.checkpointer


@router.post("/stream", dependencies=[Depends(JWTBearer())], tags=["chat"])
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

    existing_user = (
        await db.execute(select(User).where(User.email == user_email))
    ).scalar_one_or_none()

    if not existing_user:
        raise HTTPException(status_code=400, detail="User don't exist.")
    
    user_message: str = chat_request.message
    conv_id: str | None = chat_request.conversation_id

    async def event_generator() -> AsyncGenerator[str, None]:
        start_time = time.time()

        last_ai_message_id: str | None = None

        # Final assistant message (UI only)
        final_assistant_response: str | None = None
        
        graph = await build_graph(checkpointer)
        conv_service = ConversationService(db=db)
        
        conversation = await conv_service.get_or_create_conversation(
            user_email=user_email,
            conversation_id=conv_id
        )

        # Save user message
        await conv_service.save_message(
            conversation_id=conversation.id,
            role="user",
            content=user_message
        )

        inputs = {
            "messages": [HumanMessage(content=user_message)],
            "user_name": existing_user.fullname.split(" ")[0],
        }

        config = {
            "configurable": {
                "thread_id": f"{user_email}_{conversation.id}"
            }
        }

        context = UserContext(db=db)

        stream_args = {
            "input": inputs,
            "config": config,
            "context": context,
            "stream_mode": ["updates", "custom"], 
        }

        async for stream_mode, chunk in graph.astream(**stream_args):
            # STATUS STREAM (writer)
            if stream_mode == "custom":   
                payload = json.dumps({
                    "type": "status",
                    "content": chunk
                })

                await conv_service.save_message(
                    conversation_id=conversation.id,
                    role="status",
                    content=chunk,
                )
                
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

                final_assistant_response = response_text
                
                payload = json.dumps({
                    "type": "assistant",
                    "content": response_text
                })

                await conv_service.save_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=response_text,
                )
                
                yield f"data: {payload}\n\n"
            

        

        
        # Track conversation metrics
        duration_ms = (time.time() - start_time) * 1000

        metrics_tracker = ConversationMetrics(db)
        await metrics_tracker.track_conversation(
            user_message=user_message,
            assistant_response=final_assistant_response,
            user_email=user_email,
            conversation_id=conversation.id,
            duration_ms=duration_ms,
            tools_used=[]
        )
        
        # End the stream
        yield "data: [DONE]\n\n"

    # Retorna a resposta como SSE
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream"
    )


@router.get("/metrics", dependencies=[Depends(JWTBearer())])
async def get_conversation_metrics(hours: int = 24, db: AsyncSession = Depends(get_db)):
    """Get real conversation metrics from database and LangSmith"""
    metrics_tracker = ConversationMetrics(db)
    return await metrics_tracker.get_conversation_stats(hours=hours)


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