from typing import Literal
from sqlalchemy import text
from langgraph.runtime import get_runtime
from langgraph.types import Command
from agents.stream_writer import get_stream_writer
from core.cache import schema_cache
from agents.state import GraphState
from .utils import get_reset_error_state, get_decrement_retry_count

""" import logging
logging.basicConfig(level=logging.CRITICAL)

logger = logging.getLogger(__name__) """


async def get_schema_node(state: GraphState) -> Command[Literal["llm", "error_llm"]]:
    """Fetch the full schema (tables + columns) from public schema with caching.

    Routing Logic:
    - Success: Routes to 'llm' to begin reasoning with schema context
    - Error with retries: Routes back to 'get_schema_node' for retry
    - Retries exhausted: Routes to 'error_llm' for graceful error handling

    This function is a thin orchestrator that uses smaller helpers to keep the
    logic easy to test and maintain.
    """
    writer = get_stream_writer()

    # Try cache first
    cached_schema = _get_cached_schema()
    if cached_schema:
        writer("📊 Using cached system informations")
        return Command(
            update={"schema": cached_schema},
            goto="llm"
        )

    writer("📊 Loading system informations")

    runtime = get_runtime()
    db = runtime.context.db

    try:
        rows = await _query_schema_rows(db)
        schema = _rows_to_schema(rows)

        array_values = await _query_array_values(db)

        schema_str = _build_schema_str(schema, array_values)

        # Cache the result
        schema_cache.set(schema_str)

        return Command(
            update={
                "schema": schema_str,
                **get_reset_error_state(),
            },
            goto="llm"
        )
    except Exception as e:
        error_update = get_decrement_retry_count(state, str(e), "get_schema_node")
        retry_count = error_update.get("retry_count", 0)
        
        # Route based on retry attempts remaining
        next_node = "get_schema" if retry_count > 0 else "error_llm"
        return Command(update=error_update, goto=next_node)


def _get_cached_schema() -> str | None:
    """Return cached schema string or None."""
    return schema_cache.get()


async def _query_schema_rows(db) -> list:
    """Query database to get (table_name, column_name) rows."""
    sql_schema = """
        SELECT t.table_name, c.column_name
        FROM information_schema.tables t
        JOIN information_schema.columns c ON t.table_name = c.table_name
        WHERE t.table_schema = 'public' AND c.table_schema = 'public'
        ORDER BY t.table_name, c.ordinal_position;
    """
    result = await db.execute(text(sql_schema))
    return result.fetchall()


def _rows_to_schema(rows: list) -> dict:
    """Convert rows of (table_name, column_name) into a mapping.

    Returns:
        dict[str, list[str]]: mapping table -> list of columns
    """
    schema: dict[str, list[str]] = {}
    for table_name, column_name in rows:
        schema.setdefault(table_name, []).append(column_name)
    return schema


async def _query_array_values(db) -> dict:
    """Query array-type columns and return mapping of field -> list of values."""
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
        array_result = await db.execute(text(sql_array_values))
        array_rows = array_result.fetchall()
        array_values: dict[str, list] = {}
        for table_name, column_name, values in array_rows:
            key = f"{table_name}.{column_name}"
            if values:
                array_values[key] = list(values)
        return array_values
    except Exception:
        # If array values query fails, continue without them
        return {}


def _build_schema_str(schema: dict, array_values: dict) -> str:
    """Convert schema mapping and optional array values to a compact string."""
    schema_str = "\n".join(
        f"{table}: {', '.join(columns)}"
        for table, columns in sorted(schema.items())
    )

    if array_values:
        schema_str += "\n\n# Array Field Options:\n"
        for field, values in sorted(array_values.items()):
            schema_str += f"{field}: {values}\n"

    return schema_str

    