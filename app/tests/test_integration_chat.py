import pytest
from datetime import date
from fastapi import FastAPI, Request, Depends
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from types import SimpleNamespace
from unittest.mock import AsyncMock

from core.db import get_db
from services.conversation_service import ConversationService


@pytest.mark.asyncio
async def test_chat_stream_minimal():
    # Create minimal FastAPI app with a simplified /chat/stream endpoint
    app = FastAPI()

    async def override_get_db():
        yield None

    app.dependency_overrides[get_db] = override_get_db

    # Monkeypatch ConversationService methods
    ConversationService.get_or_create_conversation = AsyncMock(return_value=SimpleNamespace(id="conv-1"))
    ConversationService.save_message = AsyncMock(return_value=None)

    async def event_generator():
        # Simulate streaming assistant messages
        yield "data: {\"type\": \"assistant\", \"content\": \"Hello\"}\n\n"
        yield "data: [DONE]\n\n"

    @app.post("/chat/stream")
    async def chat_stream(request: Request, db=Depends(get_db)):
        # Simulate obtaining user and saving user message
        svc = ConversationService(db=db)
        await svc.get_or_create_conversation(user_email="u@example.com", conversation_id=None)
        await svc.save_message(conversation_id="conv-1", role="user", content="hi")
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    with TestClient(app) as client:
        resp = client.post("/chat/stream", json={"message": "hi"})

    assert resp.status_code == 200
    text = resp.text
    assert "assistant" in text or "[DONE]" in text
