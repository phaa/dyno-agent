import pytest
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

from services.conversation_service import ConversationService


@pytest.mark.asyncio
async def test_get_or_create_conversation_creates_new_when_missing(mock_async_session):
    db = mock_async_session
    # db.get returns None
    db.get.return_value = None

    svc = ConversationService(db)
    conv = await svc.get_or_create_conversation(user_email="u@example.com")

    assert conv.user_email == "u@example.com"


@pytest.mark.asyncio
async def test_get_or_create_conversation_returns_existing(mock_async_session):
    db = mock_async_session
    existing = SimpleNamespace(id="cid", user_email="u@example.com")
    db.get.return_value = existing

    svc = ConversationService(db)
    conv = await svc.get_or_create_conversation(user_email="u@example.com", conversation_id="cid")

    assert conv is existing


@pytest.mark.asyncio
async def test_save_message_commits_and_returns_message(mock_async_session):
    db = mock_async_session
    svc = ConversationService(db)

    # DB methods flush/commit should be awaited without error
    db.flush.return_value = None
    db.commit.return_value = None

    msg = await svc.save_message(conversation_id="c1", role="user", content="hello")
    assert msg.content == "hello"
    assert msg.role == "user"


@pytest.mark.asyncio
async def test_get_conversation_history_returns_messages():
    db = AsyncMock()
    svc = ConversationService(db)

    mock_result = MagicMock()
    msg1 = SimpleNamespace(id=1, content="a")
    mock_result.scalars.return_value = MagicMock(all=lambda: [msg1])
    db.execute.return_value = mock_result

    history = await svc.get_conversation_history("c1", limit=10)
    assert isinstance(history, list)
    assert history[0].content == "a"
