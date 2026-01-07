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
)

# ====================================
# Graph Definition
# ====================================

async def build_graph(checkpointer: AsyncPostgresSaver = None) -> StateGraph:
    """
    Builds the LangGraph for the dynamometer allocation agent.
    
    Components:
    - **get_schema**: Fetches DB schema dynamically for LLM context
    - **check_db**: Verifies database availability and routes flow
    - **summarize**: Summarizes messages and prepares context for LLM
    - **llm**: Main processing with tool bindings
    - **tools**: Execution of the 9 specialized agent tools
    - **db_disabled**: Fallback when database is unavailable
    
    Main Loop:
    The graph executes in loop: summarize → llm → tools → summarize
    until the LLM decides to finish (no tool calls).
    
    Args:
        checkpointer: AsyncPostgresSaver for state persistence.
                     If None, uses InMemorySaver for development.
    
    Returns:
        StateGraph: Compiled graph ready for execution with invoke/stream.
        
    Example:
        >>> graph = await build_graph(checkpointer)
        >>> result = await graph.ainvoke(
        ...     {"messages": [HumanMessage("Allocate AWD vehicle")]},
        ...     config={"configurable": {"thread_id": "user123"}}
        ... )
    """
    builder = StateGraph(GraphState)

    # ---- Nodes ----
    builder.add_node("summarize", summarization_node) # Node to summarize messages
    builder.add_node("get_schema", get_schema_node) # Node to fetch DB schema dynamically
    builder.add_node("db_disabled", db_disabled_node) # Node for handling empty/unreachable DB
    builder.add_node("llm", llm_node) # Node for LLM reasoning with tool bindings
    builder.add_node("tools", tool_node) # Node for tool execution

    # ---- Entry Point ----
    builder.set_entry_point("get_schema")

    # ---- Conditional Edges ----
    builder.add_conditional_edges("get_schema", check_db) # summarize or db_disabled based on DB availability
    builder.add_edge("summarize", "llm")
    builder.add_conditional_edges("llm", route_from_llm)  # tools or END based on LLM output
    builder.add_edge("tools", "summarize") # summarize tools output and return to LLM
    
    # The graph loops between summarize → llm → tools → summarize until the LLM decides to end.
    
    # ---- Compile Graph ----
    graph = builder.compile(checkpointer=checkpointer)

    return graph
