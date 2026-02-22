from langgraph.graph import StateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.constants import START, END
from .context import ContextSchema
from .state import GraphState
from .nodes import (
    get_schema_node, 
    db_disabled_node,
    llm_node,
    tool_node,
    summarization_node,
    error_llm,
    cleanup_node
)

# ====================================
# Graph Definition
# ====================================

async def build_graph(checkpointer: AsyncPostgresSaver):
    """
    Builds the LangGraph for the dynamometer allocation agent.
    
    Execution flow:
    1. START → get_schema: load and cache the database schema once per run.
    2. get_schema: on success routes to llm; on error routes to error_llm
    3. llm: runs with tool bindings; detects tool calls and routes to tools or summarize
    4. tools: executes tools with intelligent error handling and routing:
       - Success: routes back to llm for next reasoning step
       - Retryable error with attempts: loops back to tools
       - Retries exhausted: routes to error_llm
    5. summarize: compresses messages when token limit exceeded, routes to END
    6. error_llm: crafts user-facing failure message, routes to END

    Routing Strategy:
    All routing is handled within nodes using Command objects:
    - Each node declares its possible next nodes via type hints
    - No conditional_edge functions needed
    - Flow is explicit and traceable directly in node code

    Args:
        checkpointer: AsyncPostgresSaver for state persistence; defaults to the
            in-memory saver when None.

    Returns:
        StateGraph: Compiled graph ready for invoke/stream.
    """
    builder = StateGraph(
        state_schema=GraphState, 
        context_schema=ContextSchema
    )

    # ---- Nodes ----
    builder.add_node("get_schema", get_schema_node)     # Node to fetch DB schema dynamically
    builder.add_node("llm", llm_node)                   # Node for LLM reasoning with tool bindings
    builder.add_node("tools", tool_node)                # Node for tool execution with retry logic
    builder.add_node("summarize", summarization_node)   # Node to summarize messages
    builder.add_node("error_llm", error_llm)            # Node for graceful error handling
    
    # ---- Edges ----
    # Simple linear edges; routing happens inside nodes via Command objects
    builder.add_edge(START, "get_schema")  # Prefetch schema once at start (cached)
    
    # All other edges are determined by Command routing within nodes:
    # - get_schema routes to: llm | error_llm
    # - llm routes to: tools | summarize | error_llm
    # - tools routes to: llm | tools (retry) | error_llm
    # - summarize routes to: __end__
    # - error_llm routes to: __end__
    
    # ---- Compile Graph ----
    # Checkpointer for snapshotting all the state across executions
    graph = builder.compile(checkpointer=checkpointer) 
    return graph
