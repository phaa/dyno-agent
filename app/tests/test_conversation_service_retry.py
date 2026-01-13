"""
Integration tests for ConversationService with retry behavior.

Tests cover:
- Automatic retry on database transient failures
- Immediate failure on non-retryable errors (auth, validation)
- Retry success after N attempts
- Message persistence with retry
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from services.conversation_service import ConversationService
from core.retry import RetryableError, NonRetryableError


class TestConversationServiceRetry:
    """Test ConversationService retry behavior"""

    @pytest.mark.asyncio
    async def test_get_or_create_retries_on_db_timeout(self, mock_async_session):
        """get_or_create_conversation retries on database timeout"""
        db = mock_async_session
        user = MagicMock(email="user@test.com")

        # First call raises SQLAlchemyError, second succeeds
        db.get.side_effect = [
            SQLAlchemyError("connection timeout"),
            user
        ]
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        service = ConversationService(db)

        with patch('services.conversation_service.logger'):
            conv = await service.get_or_create_conversation(user_email="user@test.com")

        assert conv is not None
        # get() should be called twice (first failed, second succeeded)
        assert db.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_or_create_fails_immediately_on_user_not_found(self, mock_async_session):
        """get_or_create_conversation fails immediately when user not found (non-retryable)"""
        db = mock_async_session
        db.get.return_value = None  # User not found

        service = ConversationService(db)

        with pytest.raises(NonRetryableError) as exc_info:
            await service.get_or_create_conversation(user_email="nonexistent@test.com")

        assert "not found" in str(exc_info.value).lower()
        # Should only call once - no retry on non-retryable error
        assert db.get.call_count == 1

    @pytest.mark.asyncio
    async def test_get_or_create_fails_immediately_on_unauthorized_access(self, mock_async_session):
        """get_or_create_conversation fails immediately on unauthorized access (non-retryable)"""
        db = mock_async_session
        user = MagicMock(email="user@test.com")
        wrong_conv = MagicMock(id="conv123", user_email="other@test.com")

        db.get.side_effect = [user, wrong_conv]

        service = ConversationService(db)

        with pytest.raises(NonRetryableError) as exc_info:
            await service.get_or_create_conversation(
                user_email="user@test.com",
                conversation_id="conv123"
            )

        assert "not authorized" in str(exc_info.value).lower()
        # Should only call once for conversation lookup - no retry on non-retryable error
        assert db.get.call_count == 2

    @pytest.mark.asyncio
    async def test_save_message_retries_on_db_error(self, mock_async_session):
        """save_message retries on database errors"""
        db = mock_async_session

        # First attempt: flush fails with SQLAlchemyError
        # Second attempt: succeeds
        db.flush.side_effect = [
            SQLAlchemyError("connection pool exhausted"),
            None
        ]
        db.commit.side_effect = [None, None]
        db.rollback = AsyncMock()

        service = ConversationService(db)

        with patch('services.conversation_service.logger'):
            msg = await service.save_message(
                conversation_id="conv123",
                role="user",
                content="test message"
            )

        assert msg is not None
        # Both flush and commit should have been called
        assert db.flush.call_count == 2

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_conversation(self, mock_async_session):
        """get_or_create_conversation creates new conversation when none exists"""
        db = mock_async_session
        user = MagicMock(email="user@test.com")

        db.get.return_value = user
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        service = ConversationService(db)
        conv = await service.get_or_create_conversation(user_email="user@test.com")

        assert conv is not None
        assert conv.user_email == "user@test.com"
        assert db.add.called
        assert db.flush.called
        assert db.commit.called

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing_conversation(self, mock_async_session):
        """get_or_create_conversation returns existing conversation"""
        db = mock_async_session
        user = MagicMock(email="user@test.com")
        existing_conv = MagicMock(id="conv123", user_email="user@test.com")

        db.get.side_effect = [user, existing_conv]

        service = ConversationService(db)
        conv = await service.get_or_create_conversation(
            user_email="user@test.com",
            conversation_id="conv123"
        )

        assert conv is existing_conv

    @pytest.mark.asyncio
    async def test_retry_logging_on_transient_failure(self, mock_async_session):
        """Transient failures are logged during retry"""
        db = mock_async_session
        user = MagicMock(email="user@test.com")

        db.get.side_effect = [
            SQLAlchemyError("connection timeout"),
            user
        ]

        service = ConversationService(db)

        with patch('services.conversation_service.logger') as mock_logger:
            await service.get_or_create_conversation(user_email="user@test.com")

        # Should have warning logs for retry attempts
        warning_calls = [call for call in mock_logger.warning.call_args_list]
        assert len(warning_calls) > 0

    @pytest.mark.asyncio
    async def test_save_message_with_successful_persistence(self, mock_async_session):
        """save_message successfully persists message without retry"""
        db = mock_async_session
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        service = ConversationService(db)
        msg = await service.save_message(
            conversation_id="conv123",
            role="assistant",
            content="Hello, user!"
        )

        assert msg is not None
        assert msg.role == "assistant"
        assert msg.content == "Hello, user!"
        assert db.flush.call_count == 1
        assert db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_rollback_on_db_error(self, mock_async_session):
        """Database rollback is called on error"""
        db = mock_async_session
        db.flush = AsyncMock(side_effect=SQLAlchemyError("connection lost"))
        db.rollback = AsyncMock()

        service = ConversationService(db)

        with patch('services.conversation_service.logger'):
            with pytest.raises(RetryableError):
                await service.save_message(
                    conversation_id="conv123",
                    role="user",
                    content="test"
                )

        # Rollback should be called on all attempts
        assert db.rollback.call_count > 0

    @pytest.mark.asyncio
    async def test_get_conversation_history_returns_messages(self, mock_async_session):
        """get_conversation_history returns messages in chronological order"""
        db = mock_async_session
        mock_result = AsyncMock()
        messages = [
            MagicMock(id=1, content="first"),
            MagicMock(id=2, content="second")
        ]
        mock_result.scalars.return_value.all.return_value = messages

        db.execute = AsyncMock(return_value=mock_result)

        service = ConversationService(db)
        result = await service.get_conversation_history("conv123")

        assert result == messages
        assert db.execute.called


class TestRetryExhaustion:
    """Test behavior when retries are exhausted"""

    @pytest.mark.asyncio
    async def test_get_or_create_raises_after_max_retries(self, mock_async_session):
        """get_or_create_conversation raises after max retries exhausted"""
        db = mock_async_session
        # Always fail with retryable error
        db.get.side_effect = SQLAlchemyError("persistent connection failure")

        service = ConversationService(db)

        with patch('services.conversation_service.logger'):
            with pytest.raises(RetryableError):
                await service.get_or_create_conversation(user_email="user@test.com")

        # Should have attempted max_attempts times (3)
        assert db.get.call_count == 3

    @pytest.mark.asyncio
    async def test_save_message_raises_after_max_retries(self, mock_async_session):
        """save_message raises after max retries exhausted"""
        db = mock_async_session
        # Always fail with retryable error
        db.flush.side_effect = SQLAlchemyError("persistent db error")
        db.rollback = AsyncMock()

        service = ConversationService(db)

        with patch('services.conversation_service.logger'):
            with pytest.raises(RetryableError):
                await service.save_message(
                    conversation_id="conv123",
                    role="user",
                    content="test"
                )

        # Should have attempted max_attempts times (3)
        assert db.flush.call_count == 3
        assert db.rollback.call_count == 3


class TestErrorMessagePreservation:
    """Test that error messages are preserved and informative"""

    @pytest.mark.asyncio
    async def test_error_message_preserved_on_non_retryable(self, mock_async_session):
        """Error message is preserved on non-retryable error"""
        db = mock_async_session
        db.get.return_value = None

        service = ConversationService(db)

        with pytest.raises(NonRetryableError) as exc_info:
            await service.get_or_create_conversation(user_email="missing@test.com")

        error_msg = str(exc_info.value)
        assert "missing@test.com" in error_msg or "not found" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_error_message_preserved_on_retryable(self, mock_async_session):
        """Error message is preserved on retryable error"""
        db = mock_async_session
        db.get.return_value = None
        db.get.side_effect = SQLAlchemyError("Specific DB Error: Connection Pool Exhausted")

        service = ConversationService(db)

        with patch('services.conversation_service.logger'):
            with pytest.raises(RetryableError) as exc_info:
                await service.get_or_create_conversation(user_email="user@test.com")

        error_msg = str(exc_info.value)
        assert "DB Error" in error_msg or "Connection Pool" in error_msg or "Database" in error_msg
