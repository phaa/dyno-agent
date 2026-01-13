"""
Unit tests for the async retry system (core/retry.py).

Tests cover:
- Exponential backoff calculation and timing
- Exception classification (retryable vs non-retryable)
- Retry success after N attempts
- Immediate failure on non-retryable errors
- Logging behavior
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, call
from sqlalchemy.exc import SQLAlchemyError

from core.retry import async_retry, RetryableError, NonRetryableError


class TestAsyncRetryDecorator:
    """Test suite for @async_retry decorator"""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Function succeeds immediately without retry"""
        async_fn = AsyncMock(return_value="success")
        decorated = async_retry(max_attempts=3)(async_fn)

        result = await decorated()

        assert result == "success"
        assert async_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error_then_success(self):
        """Function fails once with RetryableError, succeeds on second attempt"""
        async_fn = AsyncMock(side_effect=[
            RetryableError("connection timeout"),
            "success"
        ])
        decorated = async_retry(max_attempts=3, base_delay=0.01)(async_fn)

        result = await decorated()

        assert result == "success"
        assert async_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_sqlalchemy_error_then_success(self):
        """SQLAlchemyError is treated as retryable"""
        async_fn = AsyncMock(side_effect=[
            SQLAlchemyError("connection pool exhausted"),
            "success"
        ])
        decorated = async_retry(max_attempts=3, base_delay=0.01)(async_fn)

        result = await decorated()

        assert result == "success"
        assert async_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout_error_then_success(self):
        """asyncio.TimeoutError is treated as retryable"""
        async_fn = AsyncMock(side_effect=[
            asyncio.TimeoutError("request timeout"),
            "success"
        ])
        decorated = async_retry(max_attempts=3, base_delay=0.01)(async_fn)

        result = await decorated()

        assert result == "success"
        assert async_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_non_retryable_error_fails_immediately(self):
        """NonRetryableError causes immediate failure without retry"""
        async_fn = AsyncMock(side_effect=NonRetryableError("invalid input"))
        decorated = async_retry(max_attempts=3, base_delay=0.01)(async_fn)

        with pytest.raises(NonRetryableError):
            await decorated()

        # Should only be called once - no retry
        assert async_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_exhausts_all_retries_then_fails(self):
        """All retries exhausted, raises last exception"""
        async_fn = AsyncMock(side_effect=RetryableError("persistent error"))
        decorated = async_retry(max_attempts=3, base_delay=0.01)(async_fn)

        with pytest.raises(RetryableError) as exc_info:
            await decorated()

        assert str(exc_info.value) == "persistent error"
        assert async_fn.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Backoff delays increase exponentially: 0.01s → 0.02s → 0.04s"""
        async_fn = AsyncMock(side_effect=[
            RetryableError("fail"),
            RetryableError("fail"),
            "success"
        ])
        decorated = async_retry(max_attempts=3, base_delay=0.01, max_delay=1.0)(async_fn)

        with patch('asyncio.sleep') as mock_sleep:
            result = await decorated()

        assert result == "success"
        
        # Check sleep was called with correct delays
        sleep_calls = mock_sleep.call_args_list
        assert len(sleep_calls) == 2
        assert sleep_calls[0][0][0] == pytest.approx(0.01, abs=0.001)  # 0.01 * (2^0)
        assert sleep_calls[1][0][0] == pytest.approx(0.02, abs=0.001)  # 0.01 * (2^1)

    @pytest.mark.asyncio
    async def test_backoff_capped_at_max_delay(self):
        """Backoff is capped at max_delay"""
        async_fn = AsyncMock(side_effect=[
            RetryableError("fail"),
            RetryableError("fail"),
            RetryableError("fail"),
            "success"
        ])
        decorated = async_retry(max_attempts=4, base_delay=1.0, max_delay=2.0)(async_fn)

        with patch('asyncio.sleep') as mock_sleep:
            result = await decorated()

        assert result == "success"
        
        sleep_calls = mock_sleep.call_args_list
        assert len(sleep_calls) == 3
        # Delays: 1.0 * (2^0) = 1.0, 1.0 * (2^1) = 2.0, 1.0 * (2^2) = 4.0 → capped at 2.0
        assert sleep_calls[0][0][0] == pytest.approx(1.0)
        assert sleep_calls[1][0][0] == pytest.approx(2.0)
        assert sleep_calls[2][0][0] == pytest.approx(2.0)  # Capped

    @pytest.mark.asyncio
    async def test_unknown_exception_treated_as_retryable(self):
        """Unknown exceptions are treated as retryable with logging"""
        async_fn = AsyncMock(side_effect=[
            ValueError("unexpected error"),
            "success"
        ])
        decorated = async_retry(max_attempts=3, base_delay=0.01)(async_fn)

        result = await decorated()

        assert result == "success"
        assert async_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_function_arguments(self):
        """Retry works with function arguments"""
        async_fn = AsyncMock(side_effect=[
            RetryableError("fail"),
            "success"
        ])
        decorated = async_retry(max_attempts=3, base_delay=0.01)(async_fn)

        result = await decorated("arg1", 42, kwarg1="value1")

        assert result == "success"
        assert async_fn.call_count == 2
        # Verify arguments were passed
        async_fn.assert_called_with("arg1", 42, kwarg1="value1")

    @pytest.mark.asyncio
    async def test_logging_on_retry(self):
        """Retry attempts are logged as warnings"""
        async_fn = AsyncMock(side_effect=[
            RetryableError("connection failed"),
            "success"
        ])
        decorated = async_retry(max_attempts=3, base_delay=0.01)(async_fn)

        with patch('core.retry.logger') as mock_logger:
            result = await decorated()

        assert result == "success"
        
        # Verify warning was logged
        assert mock_logger.warning.called
        warning_calls = mock_logger.warning.call_args_list
        assert any("Retry attempt" in str(call) for call in warning_calls)

    @pytest.mark.asyncio
    async def test_logging_on_all_retries_exhausted(self):
        """Exhausted retries are logged as errors"""
        async_fn = AsyncMock(side_effect=RetryableError("persistent"))
        decorated = async_retry(max_attempts=3, base_delay=0.01)(async_fn)

        with patch('core.retry.logger') as mock_logger:
            with pytest.raises(RetryableError):
                await decorated()

        # Verify error was logged
        assert mock_logger.error.called
        error_calls = mock_logger.error.call_args_list
        assert any("All 3 attempts failed" in str(call) for call in error_calls)

    @pytest.mark.asyncio
    async def test_preserves_exception_chain(self):
        """Original exception is preserved in exception chain"""
        original_error = SQLAlchemyError("db connection lost")
        async_fn = AsyncMock(side_effect=original_error)
        decorated = async_retry(max_attempts=2, base_delay=0.01)(async_fn)

        with pytest.raises(SQLAlchemyError) as exc_info:
            await decorated()

        # Exception chain should be preserved
        assert exc_info.value is original_error

    @pytest.mark.asyncio
    async def test_single_attempt_no_retry(self):
        """max_attempts=1 means no retry, immediate failure or success"""
        async_fn = AsyncMock(side_effect=RetryableError("fail"))
        decorated = async_retry(max_attempts=1, base_delay=0.01)(async_fn)

        with pytest.raises(RetryableError):
            await decorated()

        # Should only be called once
        assert async_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_mixed_error_types_retries_on_retryable(self):
        """Different retryable error types all trigger retry"""
        errors = [
            RetryableError("custom retryable"),
            SQLAlchemyError("db error"),
            asyncio.TimeoutError("timeout"),
            "success"
        ]
        async_fn = AsyncMock(side_effect=errors)
        decorated = async_retry(max_attempts=4, base_delay=0.01)(async_fn)

        result = await decorated()

        assert result == "success"
        assert async_fn.call_count == 4


class TestExceptionClassification:
    """Test suite for exception classification"""

    def test_retryable_error_inheritance(self):
        """RetryableError is an Exception"""
        error = RetryableError("test")
        assert isinstance(error, Exception)

    def test_non_retryable_error_inheritance(self):
        """NonRetryableError is an Exception"""
        error = NonRetryableError("test")
        assert isinstance(error, Exception)

    def test_retryable_error_message(self):
        """RetryableError preserves message"""
        msg = "Database connection timeout"
        error = RetryableError(msg)
        assert str(error) == msg

    def test_non_retryable_error_message(self):
        """NonRetryableError preserves message"""
        msg = "User not found"
        error = NonRetryableError(msg)
        assert str(error) == msg


class TestRetryWithServicePattern:
    """Integration tests with service-like patterns"""

    @pytest.mark.asyncio
    async def test_service_method_with_retry(self):
        """Simulates ConversationService.get_or_create_conversation pattern"""
        class MockService:
            @async_retry(max_attempts=3, base_delay=0.01)
            async def get_or_create(self, user_id: str):
                if not hasattr(self, '_attempts'):
                    self._attempts = 0
                self._attempts += 1
                
                if self._attempts == 1:
                    raise SQLAlchemyError("connection pool exhausted")
                
                return {"id": "conv_123", "user_id": user_id}

        service = MockService()
        result = await service.get_or_create("user@example.com")

        assert result["id"] == "conv_123"
        assert service._attempts == 2

    @pytest.mark.asyncio
    async def test_non_retryable_classification_in_service(self):
        """Simulates service classifying validation errors as non-retryable"""
        class MockService:
            @async_retry(max_attempts=3, base_delay=0.01)
            async def validate_and_save(self, data: dict):
                if not data.get("email"):
                    raise NonRetryableError("Email is required")
                return {"saved": True}

        service = MockService()

        with pytest.raises(NonRetryableError):
            await service.validate_and_save({})

    @pytest.mark.asyncio
    async def test_hybrid_error_handling(self):
        """Simulates catching both retryable and non-retryable errors"""
        async def operation():
            raise SQLAlchemyError("connection failed")

        @async_retry(max_attempts=2, base_delay=0.01)
        async def decorated_op():
            try:
                return await operation()
            except SQLAlchemyError as e:
                raise RetryableError(f"DB error: {str(e)}") from e

        with pytest.raises(RetryableError):
            await decorated_op()
