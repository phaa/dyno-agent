import logging
from langchain_core.messages import AIMessage
from langgraph.graph import END
from ..state import GraphState

logger = logging.getLogger(__name__)

def db_disabled_node(state: GraphState) -> GraphState:
    """Handles the case where the database is empty or unreachable."""
    error_message = "Apparently our database is not configured. Aborting further operations"
    return {
        "messages": [AIMessage(content=error_message)]
    }

# Routers (branching logic)
def route_from_llm(state: GraphState):
    """Decide whether to call tools or end after LLM."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools" # Proceed to tools node
    
    return END

def check_db(state: GraphState):
    """Decide whether to continue to LLM or terminate if DB is empty."""
    schema = state.get("schema")
    if schema and len(schema) > 0:
        return "summarize" # Proceed to LLM reasoning
    
    logger.warning("DB unavailable or no tables → routing to db_disabled.")
    return "db_disabled"