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
    route_from_db,
)

# ====================================
# Graph Definition
# ====================================

async def build_graph(checkpointer: AsyncPostgresSaver = None) -> StateGraph:
    builder = StateGraph(GraphState)

    # ---- Nodes ----
    builder.add_node("get_schema", get_schema_node) # Node to fetch DB schema dynamically
    builder.add_node("db_disabled", db_disabled_node) # Node for handling empty/unreachable DB
    builder.add_node("llm", llm_node) # Node for LLM reasoning with tool bindings
    builder.add_node("tools", tool_node) # Node for tool execution

    # ---- Entry Point ----
    builder.set_entry_point("get_schema")

    # ---- Conditional Edges ----
    builder.add_conditional_edges("get_schema", route_from_db) # Decide wether to proceed to LLM reasoning or DB disabled node
    builder.add_conditional_edges("llm", route_from_llm) # Decide wether to proceed to tool execution or end
    builder.add_edge("tools", "llm") # After tool execution, return to LLM for further reasoning

    # ---- Compile Graph ----
    #memory = InMemorySaver()  # Maintains state in memory
    graph = builder.compile(checkpointer=checkpointer) #checkpointer=memory

    return graph
