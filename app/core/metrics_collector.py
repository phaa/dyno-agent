import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, Integer
from datetime import datetime, timedelta

from models.metrics import Metrics
from core.prometheus_metrics import metrics_storer  # global instance of MetricsStorer

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
        extra_data: Optional[Dict[str, Any]] = None 
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
            extra_data=extra_data
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
        
        stmt = select(  # SQL query to aggregate metrics
            Metrics.service_name,
            Metrics.method_name,
            func.count().label('total_calls'),  
            func.avg(Metrics.duration_ms).label('avg_duration_ms'),  
            func.max(Metrics.duration_ms).label('max_duration_ms'),  
            func.sum(Metrics.success.cast(Integer)).label('success_count'), 
            func.count().label('total_count')  
        ).where(
            Metrics.created_at >= since  # Filter by period
        ).group_by(
            Metrics.service_name,  
            Metrics.method_name  
        )
        
        result = await self.db.execute(stmt) 
        rows = result.all()
        
        stats = []  
        for row in rows:  
            success_rate = (row.success_count / row.total_count) * 100 if row.total_count > 0 else 0  # Calcula taxa de sucesso
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
                Metrics.success == True  # Só sucessos
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
        estimated_hours_saved = round((total_allocations * 4) / 60, 2)  # Eg: 4min economizados por alocação
        monthly_cost_savings = estimated_hours_saved * 50  # Eg: $50/hora de engenheiro
        
        # Update Prometheus/CloudWatch 
        metrics_storer.update_business_metrics(
            hours_saved=estimated_hours_saved,
            cost_savings=monthly_cost_savings
        )
        
        return {  
            'total_successful_allocations': total_allocations,
            'avg_allocation_time_ms': round(avg_allocation_time, 2),
            'estimated_time_saved_hours': estimated_hours_saved, 
            'monthly_cost_savings_usd': monthly_cost_savings 
        }

