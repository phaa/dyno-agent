from sqlalchemy import text
from langgraph.runtime import get_runtime
from agents.stream_writer import get_stream_writer
from core.cache import schema_cache
from agents.state import GraphState

""" import logging
logging.basicConfig(level=logging.CRITICAL)

logger = logging.getLogger(__name__) """


async def get_schema_node(state: GraphState) -> GraphState:
    """Fetch the full schema (tables + columns) from public schema with caching."""
    writer = get_stream_writer()
    
    # Try cache first
    cached_schema = schema_cache.get()
    if cached_schema:
        writer("📊 Using cached system informations")
        return {"schema": cached_schema}
    
    writer("📊 Loading system informations")
    
    runtime = get_runtime()
    db = runtime.context.db
    
    # Single query to get all tables and columns to avoid connection conflicts
    sql_schema = """
        SELECT t.table_name, c.column_name
        FROM information_schema.tables t
        JOIN information_schema.columns c ON t.table_name = c.table_name
        WHERE t.table_schema = 'public' AND c.table_schema = 'public'
        ORDER BY t.table_name, c.ordinal_position;
    """
    
    try:
        result = await db.execute(text(sql_schema))
        rows = result.fetchall()
        
        schema = {}
        for table_name, column_name in rows:
            if table_name not in schema:
                schema[table_name] = []
            schema[table_name].append(column_name)

        # Cache the result
        schema_cache.set(schema)
        return {
            "schema": schema,
        }
    except Exception as e:
        return {
            "retry_count": 0,  # Force immediate error handling
            "error": str(e),
            "error_node": "get_schema_node"
        }
    # logger.critical(schema)

    