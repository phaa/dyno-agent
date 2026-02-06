from sqlalchemy import text
from langgraph.runtime import get_runtime
from agents.stream_writer import get_stream_writer
from core.cache import schema_cache
from agents.state import GraphState
from .utils import reset_error_state, decrement_retry_count

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
    
    # Query to get unique values from array columns
    sql_array_values = """
        SELECT 'dynos' as table_name, 'supported_weight_classes' as column_name, 
               ARRAY_AGG(DISTINCT unnest ORDER BY unnest) as values
        FROM (SELECT UNNEST(supported_weight_classes) FROM dynos WHERE supported_weight_classes IS NOT NULL) t
        UNION ALL
        SELECT 'dynos' as table_name, 'supported_drives' as column_name,
               ARRAY_AGG(DISTINCT unnest ORDER BY unnest) as values
        FROM (SELECT UNNEST(supported_drives) FROM dynos WHERE supported_drives IS NOT NULL) t
        UNION ALL
        SELECT 'dynos' as table_name, 'supported_test_types' as column_name,
               ARRAY_AGG(DISTINCT unnest ORDER BY unnest) as values
        FROM (SELECT UNNEST(supported_test_types) FROM dynos WHERE supported_test_types IS NOT NULL) t;
    """
    
    try:
        result = await db.execute(text(sql_schema))
        rows = result.fetchall()
        
        schema = {}
        for table_name, column_name in rows:
            if table_name not in schema:
                schema[table_name] = []
            schema[table_name].append(column_name)

        # Get array column values
        array_values = {}
        try:
            array_result = await db.execute(text(sql_array_values))
            array_rows = array_result.fetchall()
            for table_name, column_name, values in array_rows:
                key = f"{table_name}.{column_name}"
                if values:
                    array_values[key] = list(values)
        except Exception:
            # If array values query fails, continue without them
            pass

        # Convert to compact string representation for prompt efficiency
        schema_str = "\n".join(
            f"{table}: {', '.join(columns)}"
            for table, columns in sorted(schema.items())
        )
        
        # Append array values information if available
        if array_values:
            schema_str += "\n\n# Array Field Options:\n"
            for field, values in sorted(array_values.items()):
                schema_str += f"{field}: {values}\n"

        # Cache the result
        schema_cache.set(schema_str)
        return {
            "schema": schema_str,
            **reset_error_state(),
        }
    except Exception as e:
        return {
            **decrement_retry_count(state, str(e), "get_schema_node")
        }
    # logger.critical(schema)

    