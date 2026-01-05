import time
import uuid
import asyncio
import logging
from functools import wraps
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta

from models.metrics import Metrics
from core.db import get_db
from core.prometheus_metrics import prometheus_collector

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Centralized metrics collection and analysis"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def record_metric(
        self,
        correlation_id: str,
        service_name: str,
        method_name: str,
        duration_ms: float,
        success: bool,
        user_id: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a single metric entry into the database"""
        metric = Metrics(
            correlation_id=correlation_id,
            service_name=service_name,
            method_name=method_name,
            user_id=user_id,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            metadata=metadata
        )
        
        self.db.add(metric)
        try:
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to record metric: {e}")
            await self.db.rollback()
    
    async def get_performance_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance statistics for the last N hours"""
        since = datetime.now() - timedelta(hours=hours)
        
        stmt = select(
            Metrics.service_name,
            Metrics.method_name,
            func.count().label('total_calls'),
            func.avg(Metrics.duration_ms).label('avg_duration_ms'),
            func.max(Metrics.duration_ms).label('max_duration_ms'),
            func.sum(Metrics.success.cast('integer')).label('success_count'),
            func.count().label('total_count')
        ).where(
            Metrics.created_at >= since
        ).group_by(
            Metrics.service_name, 
            Metrics.method_name
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        stats = []
        for row in rows:
            success_rate = (row.success_count / row.total_count) * 100 if row.total_count > 0 else 0
            stats.append({
                'service': row.service_name,
                'method': row.method_name,
                'total_calls': row.total_calls,
                'avg_duration_ms': round(row.avg_duration_ms, 2),
                'max_duration_ms': row.max_duration_ms,
                'success_rate': round(success_rate, 2)
            })
        
        return {'period_hours': hours, 'stats': stats}
    
    async def get_business_metrics(self) -> Dict[str, Any]:
        """Get business-specific metrics and update Prometheus/CloudWatch"""
        # Total allocations created
        allocations_stmt = select(func.count()).select_from(Metrics).where(
            and_(
                Metrics.service_name == 'AllocationService',
                Metrics.method_name == 'auto_allocate_vehicle_core',
                Metrics.success == True
            )
        )
        
        # Average allocation time
        avg_time_stmt = select(func.avg(Metrics.duration_ms)).select_from(Metrics).where(
            and_(
                Metrics.service_name == 'AllocationService',
                Metrics.method_name == 'auto_allocate_vehicle_core'
            )
        )
        
        total_allocations = (await self.db.execute(allocations_stmt)).scalar() or 0
        avg_allocation_time = (await self.db.execute(avg_time_stmt)).scalar() or 0
        
        # Calculate business metrics
        estimated_hours_saved = round((total_allocations * 4) / 60, 2)  # Ex: 4min saved per allocation
        monthly_cost_savings = estimated_hours_saved * 50  # Ex: $50/hour
        
        # Update Prometheus/CloudWatch
        prometheus_collector.update_business_metrics(
            hours_saved=estimated_hours_saved,
            cost_savings=monthly_cost_savings
        )
        
        return {
            'total_successful_allocations': total_allocations,
            'avg_allocation_time_ms': round(avg_allocation_time, 2),
            'estimated_time_saved_hours': estimated_hours_saved,
            'monthly_cost_savings_usd': monthly_cost_savings
        }


def track_performance(
    service_name: Optional[str] = None,
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
            # Generate correlation ID
            correlation_id = str(uuid.uuid4())
            
            # Extract service name and method name
            actual_service_name = service_name or (args[0].__class__.__name__ if args else "Unknown")
            method_name = func.__name__
            
            # Extract user_id if available
            user_id = kwargs.get('user_id') or getattr(args[0], 'current_user_id', None) if args else None
            
            # Start timing
            start_time = time.time()
            success = False
            error_message = None
            metadata = {}
            
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                success = True
                
                # Extract metadata from result if requested
                if include_metadata and isinstance(result, dict):
                    metadata = {
                        'result_keys': list(result.keys()),
                        'success_flag': result.get('success', None)
                    }
                
                return result
                
            except Exception as e:
                error_message = str(e)
                logger.error(f"Error in {actual_service_name}.{method_name}: {e}")
                raise
                
            finally:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                duration_seconds = duration_ms / 1000
                
                # Record to Prometheus + CloudWatch
                prometheus_collector.record_allocation_request(
                    service_name=actual_service_name,
                    method_name=method_name,
                    duration_seconds=duration_seconds,
                    success=success,
                    user_id=user_id
                )
                
                # Log structured metrics
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
                
                # Record to database (fire and forget)
                asyncio.create_task(
                    _record_metric_async(
                        correlation_id=correlation_id,
                        service_name=actual_service_name,
                        method_name=method_name,
                        duration_ms=duration_ms,
                        success=success,
                        user_id=user_id,
                        error_message=error_message,
                        metadata=metadata if metadata else None
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
    metadata: Optional[Dict[str, Any]] = None
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
                metadata=metadata
            )
            break
    except Exception as e:
        logger.error(f"Failed to record metric asynchronously: {e}")


@asynccontextmanager
async def metrics_context(service_name: str, method_name: str, user_id: Optional[int] = None):
    """Context manager for manual metrics tracking"""
    correlation_id = str(uuid.uuid4())
    start_time = time.time()
    success = False
    error_message = None
    
    try:
        yield correlation_id
        success = True
    except Exception as e:
        error_message = str(e)
        raise
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