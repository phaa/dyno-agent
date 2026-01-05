from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from core.db import get_db
from core.metrics_collector import MetricsCollector  
from core.prometheus_metrics import metrics_storer  
from auth.auth_bearer import JWTBearer

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/performance", dependencies=[Depends(JWTBearer())]) 
async def get_performance_metrics(
    hours: int = 24,  
    db: AsyncSession = Depends(get_db) 
) -> Dict[str, Any]:
    """Get system performance metrics for the last N hours"""
    try:
        collector = MetricsCollector(db)
        return await collector.get_performance_stats(hours=hours) 
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch performance metrics: {str(e)}")


@router.get("/business", dependencies=[Depends(JWTBearer())]) 
async def get_business_metrics(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get business impact metrics"""
    try:
        collector = MetricsCollector(db) 
        return await collector.get_business_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch business metrics: {str(e)}")


@router.get("/health") 
async def metrics_health():
    """Health check for metrics system"""
    return {
        "status": "healthy",
        "metrics_system": "operational",
        "timestamp": datetime.now().isoformat()  
    }


@router.get("/prometheus")  # Public endpoint for Prometheus scraping
async def prometheus_metrics():
    """Prometheus metrics endpoint for scraping"""
    try:
        metrics_data = metrics_storer.get_prometheus_metrics() 
        return Response(content=metrics_data, media_type="text/plain") 
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Prometheus metrics: {str(e)}")