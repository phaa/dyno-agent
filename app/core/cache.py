import time
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SchemaCache:
    """Simple in-memory cache for database schema with TTL."""
    
    def __init__(self, ttl_seconds: int = 3600):  # 1 hour default
        self.ttl_seconds = ttl_seconds
        self._cache: Optional[Dict[str, Any]] = None
        self._timestamp: Optional[float] = None
    
    def get(self) -> Optional[Dict[str, Any]]:
        """Get cached schema if valid."""
        if not self._cache or not self._timestamp:
            return None
        
        if time.time() - self._timestamp > self.ttl_seconds:
            logger.info("Schema cache expired")
            self._cache = None
            self._timestamp = None
            return None
        
        logger.info("Using cached schema")
        return self._cache
    
    def set(self, schema: Dict[str, Any]) -> None:
        """Cache the schema."""
        self._cache = schema
        self._timestamp = time.time()
        logger.info(f"Schema cached with {len(schema)} tables")
    
    def invalidate(self) -> None:
        """Manually invalidate cache."""
        self._cache = None
        self._timestamp = None
        logger.info("Schema cache invalidated")

# Global cache instance
schema_cache = SchemaCache()