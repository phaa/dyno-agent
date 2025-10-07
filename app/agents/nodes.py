import os
from langchain_core.messages import AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import START, END, StateGraph
from sqlalchemy import select, or_, and_, extract, text
from .state import GraphState
from core.config import GEMINI_MODEL_ID
from langchain.agents import ToolNode

from .tools import (
    find_available_dynos,
    check_vehicle_allocation,
    detect_conflicts,
    completed_tests_count,
    maintenance_check,
    query_database,
    get_datetime_now
)

SYSTEM = """
    You are an assistant specialized in vehicle dynamometers. 
    You are free to use any of the given tools and query any database.
    Whenever the user asks for information, use all available tools to make the response as complete as possible.
    Always respond in plain text, using correct punctuation. 
    Use  markdown formatting.
    Use lists when needed 

    For vertical numbered lists with descriptions, use this format:
    - Item 1: description
    - Item 2: description
    - Item 3: description
    End each item with a newline.
    For horizontal lists, separate items with commas. 
    Always give accurate and complete information. 
    If you don't know the answer, just say you don't know. Never make up an answer.
    Address the user as {user_name}.
"""

tools = [
    get_datetime_now,
    find_available_dynos,
    check_vehicle_allocation,
    detect_conflicts,
    completed_tests_count,
    maintenance_check,
    query_database, 
]

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL_ID,
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

model_with_tools = llm.bind_tools(tools)


async def get_allowed_tables_node(state: GraphState) -> list[str]:
    db = state.get("db")
    forbidden_tables = []

    sql = "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
    result = db.execute(text(sql))
    rows = result.fetchall()

    if not rows:
        return {
        "messages": AIMessage(
            "O nosso banco de dados está vazio. Por favor, adicione dados para que eu possa ajudar você."
        )
    }

    allowed = [
        row[0] for row in rows
        if row[0] not in forbidden_tables
    ]

    return { "allowed_tables": allowed }


def db_disabled_node(state: GraphState):
    return {
        "messages": AIMessage(
            f"The user, first_name:{state.get('first_name','missing')}, "
            f"last_name:{state.get('last_name','missing')} is not in the database"
        )
    }


def llm_node(state: GraphState) -> GraphState:
    user_name = state.get("user_name")
    
    msgs = [
        SystemMessage(content=SYSTEM.format(user_name=user_name))
    ]
    msgs += state["messages"]
    
    ai: AIMessage = model_with_tools.invoke(msgs)
    return { "messages": [ai] }


def route_from_llm(state: GraphState):
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return END


def route_from_identify(state: GraphState):
    # Continue only if the allowed tables and the db are present; otherwise END
    if state.get("allowed_tables") and state.get("db"):
        return "llm"
    return "db_disabled"

# Node : Tool execution
tool_node = ToolNode(tools)

builder = StateGraph(GraphState)

# Nodes
builder.add_node("get_allowed_tables", get_allowed_tables_node)
builder.add_node("db_disabled", db_disabled_node)
builder.add_node("llm", llm_node)
builder.add_node("tools", tool_node)

# Flow
builder.set_entry_point("get_allowed_tables")
builder.add_conditional_edges("identify", route_from_identify, {"llm": "llm", "unknown_user": "unknown_user"})
builder.add_conditional_edges("llm", route_from_llm, {"tools": "tools", END: END})
builder.add_edge("tools", "llm")

graph = builder.compile()
