import time
import uuid
import asyncio
import logging
from functools import wraps
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from core.db import get_db
from core.prometheus_metrics import metrics_storer  # Global instance of MetricsStorer
from core.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


def track_performance(
    service_name: Optional[str] = None,  # Eg: (AllocationService)
    include_metadata: bool = False 
):
    """
    Decorator to automatically track method performance
    
    Usage:
    @track_performance(service_name="AllocationService")
    async def my_method(self, param1, param2):
        # method implementation
    """
    def decorator(func): 
        @wraps(func) 
        async def wrapper(*args, **kwargs): 
            # Generate correlation ID - Unique for tracking
            correlation_id = str(uuid.uuid4())
            
            # Extract service name and method name 
            actual_service_name = service_name or (args[0].__class__.__name__ if args else "Unknown")  # Nome da classe se não especificado
            method_name = func.__name__  # Nome da função
            
            # Extract user_id if available 
            user_id = kwargs.get('user_id') or getattr(args[0], 'current_user_id', None) if args else None
            
            # Start timing
            start_time = time.time()
            success = False  # Assume fail until completed
            error_message = None
            extra_data = {}
            
            try:
                # Execute the function 
                result = await func(*args, **kwargs)
                success = True
                
                # Extract metadata from result if requested 
                if include_metadata and isinstance(result, dict):
                    extra_data = {
                        'result_keys': list(result.keys()), 
                        'success_flag': result.get('success', None)
                    }
                
                return result
                
            except Exception as e:
                error_message = str(e)
                logger.error(f"Error in {actual_service_name}.{method_name}: {e}")
                raise  # Re-raise exception
                
            finally:
                # Calculate duration 
                duration_ms = (time.time() - start_time) * 1000  # Convert to milissegundos
                duration_seconds = duration_ms / 1000  # Convert to seconds (Prometheus)
                
                # Record to Prometheus + CloudWatch 
                metrics_storer.record_method_execution(  
                    service_name=actual_service_name,
                    method_name=method_name,
                    duration_seconds=duration_seconds,
                    success=success,
                    user_id=user_id
                )
                
                # Log structured metrics for debugging 
                logger.info(
                    f"Method executed: {actual_service_name}.{method_name}",
                    extra={ 
                        'correlation_id': correlation_id,
                        'service_name': actual_service_name,
                        'method_name': method_name,
                        'duration_ms': duration_ms,
                        'success': success,
                        'user_id': user_id
                    }
                )
                
                # Record to database without blocking (fire and forget) 
                asyncio.create_task(
                    _record_metric_async(
                        correlation_id=correlation_id,
                        service_name=actual_service_name,
                        method_name=method_name,
                        duration_ms=duration_ms,
                        success=success,
                        user_id=user_id,
                        error_message=error_message,
                        metadata=extra_data if extra_data else None
                    )
                )
        
        return wrapper
    return decorator


async def _record_metric_async(
    correlation_id: str,
    service_name: str,
    method_name: str,
    duration_ms: float,
    success: bool,
    user_id: Optional[int] = None,
    error_message: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None
):
    """Helper to record metrics asynchronously"""
    try:
        async for db in get_db(): 
            collector = MetricsCollector(db) 
            await collector.record_metric( 
                correlation_id=correlation_id,
                service_name=service_name,
                method_name=method_name,
                duration_ms=duration_ms,
                success=success,
                user_id=user_id,
                error_message=error_message,
                metadata=extra_data
            )
            break # Exit after first successful db session
    except Exception as e:
        logger.error(f"Failed to record metric asynchronously: {e}")


@asynccontextmanager
async def metrics_context(service_name: str, method_name: str, user_id: Optional[int] = None):
    """Context manager for manual metrics tracking"""
    correlation_id = str(uuid.uuid4())  # Unique ID for tracking
    start_time = time.time() 
    success = False
    error_message = None
    
    try:
        yield correlation_id  # Return correlation_id for use
        success = True 
    except Exception as e:
        error_message = str(e)
        raise  # Re-raise exception
    finally:
        duration_ms = (time.time() - start_time) * 1000
        
        asyncio.create_task(  
            _record_metric_async(
                correlation_id=correlation_id,
                service_name=service_name,
                method_name=method_name,
                duration_ms=duration_ms,
                success=success,
                user_id=user_id,
                error_message=error_message
            )
        )