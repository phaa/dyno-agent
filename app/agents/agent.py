from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

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
# 🌐 Graph Definition
# ====================================

builder = StateGraph(GraphState)

# ---- Nodes ----
builder.add_node("get_schema", get_schema_node)
builder.add_node("db_disabled", db_disabled_node)
builder.add_node("llm", llm_node)
builder.add_node("tools", tool_node)

# ---- Entry Point ----
builder.set_entry_point("get_schema")

# ---- Conditional Edges ----
builder.add_conditional_edges("get_schema", route_from_db)
builder.add_conditional_edges("llm", route_from_llm)
builder.add_edge("tools", "llm")

# ---- Compile Graph ----
memory = InMemorySaver()  # mantém o histórico entre execuções
graph = builder.compile(checkpointer=memory)
