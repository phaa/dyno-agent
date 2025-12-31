import json
from dataclasses import dataclass
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import build_graph
from services.conversation_service import ConversationService
from auth.auth_bearer import JWTBearer
from auth.auth_handler import get_user_email_from_token
from core.db import get_db
from schemas.chat import ChatRequest

@dataclass
class UserContext:
    db: AsyncSession

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/chat/stream", dependencies=[Depends(JWTBearer())], tags=["chat"])
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """
    Endpoint for chat with SSE (Server-Sent Events) streaming.
    Receives a message from the user and sends the model's responses in real time, chunk by chunk.
    """

    user_email = get_user_email_from_token(request)
    user_message: str = request.message
    conv_id: str | None = request.conversation_id

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        Generator function to yield chat response chunks as SSE.
        """
        graph = await build_graph(app.state.checkpointer)

        conv_service = ConversationService(db=db)
        
        # Get or create conversation
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
            "user_name": user_email.split("@")[0], 
        }

        # Thread ID to maintain context
        config = {"configurable": {"thread_id": user_email}}
        context = UserContext(db=db)

        stream_args = {
            "input": inputs,
            "config": config,
            "context": context,
            "stream_mode": ["updates", "custom"],  # Can be "values", "updates", "custom"
        }

        async for stream_mode, chunk in graph.astream(**stream_args):
            if stream_mode == "updates":
                for step, data in chunk.items():
                    #logger.warning(step)
                    #logger.warning(data)

                    if not data or "messages" not in data:
                        continue

                    for msg in data["messages"]:
                        if isinstance(msg, AIMessage) and msg.content:
                            payload = json.dumps({
                                "type": "assistant" ,
                                "content": msg.content
                            })
                            await conv_service.save_message(
                                conversation_id=conversation.id,
                                role="assistant",
                                content=msg.content
                            )
                            yield f"data: {payload}\n\n"

            elif stream_mode == "custom":   
                payload = json.dumps({
                    "type": "token",
                    "content": chunk
                })
                yield f"data: {payload}\n\n" 

        # Finaliza o stream
        yield "data: [DONE]\n\n"

    # Retorna a resposta como SSE
    return StreamingResponse(event_generator(), media_type="text/event-stream")


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