from langgraph.graph import StateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.constants import START, END
from .state import GraphState
from .nodes import (
    get_schema_node, 
    db_disabled_node,
    llm_node,
    tool_node,
    route_from_llm,
    route_from_schema,
    route_from_tools,
    summarization_node,
    error_llm,
    cleanup_node
)

# ====================================
# Graph Definition
# ====================================

async def build_graph(checkpointer: AsyncPostgresSaver = None) -> StateGraph:
    """
    Builds the LangGraph for the dynamometer allocation agent.
    
    Execution flow:
    1. START → get_schema: load and cache the database schema once per run.
    2. route_from_schema: if history is heavy, go to summarize; otherwise go straight to llm.
    3. summarize: compress/prune messages and return to llm with a summary marker.
    4. llm: runs with tool bindings; if it emits tool calls → tools, else END.
    5. tools: executes tools with retry/error tracking. Retryable errors decrement
       retry_count and loop back; exhausted/fatal errors route to error_llm; success
       routes back to llm for another reasoning step.
    6. error_llm: crafts a user-facing failure message, clears error state, then END.

    Components wired in the graph:
    - get_schema, summarize, llm, tools, error_llm
    - db_disabled and error_handler nodes are available for future routing but not
      currently used in the edge definitions.

    Args:
        checkpointer: AsyncPostgresSaver for state persistence; defaults to the
            in-memory saver when None.

    Returns:
        StateGraph: Compiled graph ready for invoke/stream.
    """
    builder = StateGraph(GraphState)

    # ---- Nodes ----
    builder.add_node("summarize", summarization_node) # Node to summarize messages
    builder.add_node("get_schema", get_schema_node) # Node to fetch DB schema dynamically
    builder.add_node("llm", llm_node) # Node for LLM reasoning with tool bindings
    builder.add_node("tools", tool_node) # Node for tool execution with retry logic
    builder.add_node("error_llm", error_llm)
    builder.add_node("cleanup", cleanup_node)
    
    # ---- Edges ----
    # Add guardrail before get_schema
    builder.add_edge(START, "get_schema")  # Prefetch schema once at start (cached)
    builder.add_conditional_edges("get_schema", route_from_schema) # Schema loaded, 
    builder.add_conditional_edges("llm", route_from_llm)  # Check for tool calls or summarization
    builder.add_conditional_edges("tools", route_from_tools) # Handle retries/errors (if any) or LLM
    builder.add_edge("error_llm", "cleanup") # After error handling, goes to cleanup and end conversation without summarizing
    builder.add_edge("summarize", "cleanup") # Clean the state to save checkpointer space
    builder.add_edge("cleanup", END)
    
    # ---- Compile Graph ----
    # Checkpointer for snapshotting all the state across executions
    graph = builder.compile(checkpointer=checkpointer) 
    return graph
