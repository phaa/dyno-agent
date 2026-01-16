"""
Retry utilities with exponential backoff for async functions.

This module provides decorators and utilities for implementing retry logic
with exponential backoff in async applications, helping handle transient failures
gracefully.
"""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

class RetryableError(Exception):
    """
    Exception that should be retried with exponential backoff.
    
    Used for transient, temporary failures that may succeed on retry:
    - Database connection timeouts and temporary unavailability
    - Network timeouts and intermittent connectivity issues
    - Rate limit errors (API service recovering)
    - Temporary resource exhaustion (connection pool saturation)
    - Service restarts and rolling deployments
    
    Production Pattern:
    except SQLAlchemyError as e:
        if is_connection_error(e):
            raise RetryableError(f"Database connection failed: {str(e)}") from e
    """
    pass

class NonRetryableError(Exception):
    """
    Exception that should NOT be retried.
    
    Used for permanent, deterministic failures that won't change on retry:
    - Authentication and authorization failures (wrong credentials)
    - User not found in database (400/404 errors)
    - Validation errors (malformed input, business rule violations)
    - Resource access denied (403 forbidden)
    - Configuration errors (missing required settings)
    
    Production Pattern:
    except ValueError as e:
        raise NonRetryableError(f"Invalid user input: {str(e)}") from e
    """
    pass

def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0
) -> Callable[[F], F]:
    """Decorator for async functions with exponential backoff retry logic.
    
    Automatically retries on transient failures with exponential backoff.
    Distinguishes between retryable and non-retryable errors.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds between retries (default: 1.0)
        max_delay: Maximum delay in seconds between retries (default: 10.0)
    
    Returns:
        Decorated async function with retry logic
    
    Example:
        @async_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
        async def fetch_data():
            return await client.get('/data')
    
    Error Handling:
    - RetryableError: Retried up to max_attempts times
    - NonRetryableError: Raised immediately without retry
    - SQLAlchemyError: Treated as retryable (database transient failures)
    - asyncio.TimeoutError: Treated as retryable
    - Other exceptions: Treated as retryable with logging
    
    Backoff Strategy:
    - Uses exponential backoff: delay = base_delay * (2 ^ attempt)
    - Capped at max_delay to prevent excessive waiting
    - Logs warning for each retry attempt
    - Logs error when all retries exhausted
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                
                except NonRetryableError:
                    # Non-retryable errors fail immediately
                    raise
                
                except (RetryableError, SQLAlchemyError, asyncio.TimeoutError) as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"Retry attempt {attempt + 1}/{max_attempts} for {func.__name__}. "
                            f"Error: {str(e)}. Waiting {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}. "
                            f"Final error: {str(e)}"
                        )
                
                except Exception as e:
                    # Unexpected errors also retry once
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"Unexpected error in {func.__name__} "
                            f"(attempt {attempt + 1}/{max_attempts}): {str(e)}. "
                            f"Waiting {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Permanent failure in {func.__name__}: {str(e)}")
            
            # If we get here, all retries failed
            raise last_exception if last_exception else Exception("Retry failed")
        
        return wrapper
    return decorator
