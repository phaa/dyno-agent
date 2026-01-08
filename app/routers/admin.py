from fastapi import APIRouter, Depends
from core.cache import schema_cache
from auth.auth_bearer import JWTBearer

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/cache/schema/invalidate")
async def invalidate_schema_cache(token: str = Depends(JWTBearer())):
    """Manually invalidate schema cache (useful after migrations)."""
    schema_cache.invalidate()
    return {"message": "Schema cache invalidated successfully"}

@router.get("/cache/schema/status")
async def get_schema_cache_status(token: str = Depends(JWTBearer())):
    """Get current schema cache status."""
    cached_schema = schema_cache.get()
    return {
        "cached": cached_schema is not None,
        "tables_count": len(cached_schema) if cached_schema else 0,
        "ttl_seconds": schema_cache.ttl_seconds
    }