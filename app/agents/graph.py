from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from .state import GraphState
from .nodes import (
    get_schema_node, 
    db_disabled_node,
    llm_node,
    tool_node,
    route_from_llm,
    check_db,
    summarization_node,
    graceful_error_handler,
)

# ====================================
# Graph Definition
# ====================================

async def build_graph(checkpointer: AsyncPostgresSaver = None) -> StateGraph:
    """
    Builds the LangGraph for the dynamometer allocation agent.
    
    Components:
    - check_db: Verifies database availability and routes flow (entry point)
    - get_schema: Fetches DB schema dynamically when query_database tool is needed
    - summarize: Summarizes messages and prepares context for LLM
    - llm: Main processing with tool bindings and error routing
    - tools: Execution of the 9 specialized agent tools with retry logic
    - retry_tools: Retry mechanism for failed tool executions
    - error_handler: Graceful error handling when retries are exhausted
    - db_disabled: Fallback when database is unavailable
    
    Error Handling:
    The graph includes comprehensive retry logic and error recovery:
    - Automatic retry for transient failures (network, timeouts)
    - Intelligent error classification (retryable vs fatal)
    - Graceful degradation with user-friendly error messages
    - Error state tracking and recovery mechanisms
    
    Main Loop:
    The graph executes: check_db → summarize → llm → (get_schema if needed) → tools → summarize
    until the LLM decides to finish (no tool calls).
    
    Args:
        checkpointer: AsyncPostgresSaver for state persistence.
                     If None, uses InMemorySaver for development.
    
    Returns:
        StateGraph: Compiled graph ready for execution with invoke/stream.
        
    Example:
        graph = await build_graph(checkpointer)
        result = await graph.ainvoke(
            {"messages": [HumanMessage("Allocate AWD vehicle")]},
            config={"configurable": {"thread_id": "user123"}}
        )
    """
    builder = StateGraph(GraphState)

    # ---- Nodes ----
    builder.add_node("summarize", summarization_node) # Node to summarize messages
    builder.add_node("get_schema", get_schema_node) # Node to fetch DB schema dynamically
    builder.add_node("db_disabled", db_disabled_node) # Node for handling empty/unreachable DB
    builder.add_node("llm", llm_node) # Node for LLM reasoning with tool bindings
    builder.add_node("tools", tool_node) # Node for tool execution with retry logic
    builder.add_node("error_handler", graceful_error_handler) # Node for graceful error handling

    # ---- Entry Point ----
    builder.set_entry_point("check_db")

    # ---- Conditional Edges ----
    builder.add_conditional_edges("check_db", check_db) # summarize or db_disabled based on DB availability
    builder.add_edge("summarize", "llm")
    builder.add_conditional_edges("llm", route_from_llm)  # tools, error_handler, get_schema, or END
    builder.add_edge("get_schema", "tools") # after schema fetch, execute tools
    builder.add_edge("tools", "summarize") # summarize tools output and return to LLM

    builder.add_edge("error_handler", "summarize") # error handler returns to conversation flow
    
    # Enhanced flow: summarize → llm → (error handling/retry logic) → tools → summarize
    
    # ---- Compile Graph ----
    graph = builder.compile(checkpointer=checkpointer)

    return graph
