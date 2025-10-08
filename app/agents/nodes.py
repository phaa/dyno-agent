import os
import logging
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END
from sqlalchemy import text
from core.config import GEMINI_MODEL_ID
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import ToolNode
from langgraph.runtime import get_runtime
from .tools import (
    find_available_dynos,
    check_vehicle_allocation,
    detect_conflicts,
    completed_tests_count,
    maintenance_check,
    query_database,
    get_datetime_now,
)
from .state import GraphState

logger = logging.getLogger(__name__)

SYSTEM = """
You are an assistant specialized in vehicle dynamometers. 
You are free to use any of the given tools and query the following database:

{schema}

Whenever the user asks for information, use all available tools to make the response as complete as possible.
Use markdown formatting.
Use lists when needed.

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

# -------------------------------
# LLM configuration
# -------------------------------
llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL_ID,
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

tools = [
    get_datetime_now,
    find_available_dynos,
    check_vehicle_allocation,
    detect_conflicts,
    completed_tests_count,
    maintenance_check,
    query_database,
]

model_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)


# -------------------------------
# Nodes
# -------------------------------
async def get_schema_node(state: GraphState) -> GraphState:
    """Fetch the full schema (tables + columns) from public schema."""
    runtime = get_runtime()
    db = runtime.context.db
    sql_tables = "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
    result = await db.execute(text(sql_tables))
    tables = [row[0] for row in result.fetchall()]

    schema = {}
    for table in tables:
        sql_columns = f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='{table}';
        """
        result = await db.execute(text(sql_columns))
        columns = [row[0] for row in result.fetchall()]
        schema[table] = columns

    # Depois posso colocar uma  mensagem dizendo que esta consultando o banco
    return {
        "schema": schema,
        
    }

""" "messages": [
            AIMessage(content=("Estou consultando o banco de dados..."))
        ] """


def db_disabled_node(state: GraphState) -> GraphState:
    """Handles the case where the database is empty or unreachable."""
    return {
        "messages": [
            AIMessage(
                content=(
                    "O nosso banco de dados está vazio. "
                    "Por favor, adicione dados para que eu possa ajudar você."
                )
            )
        ]
    }


def llm_node(state: GraphState) -> GraphState:
    """Main reasoning node powered by Gemini with tool bindings."""
    user_name = state.get("user_name")
    schema = state.get("schema")
    msgs = [SystemMessage(content=SYSTEM.format(schema=schema, user_name=user_name))]
    msgs += state["messages"]

    ai: AIMessage = model_with_tools.invoke(msgs)
    return {"messages": [ai]}


# -------------------------------
# Routers (branching logic)
# -------------------------------
def route_from_llm(state: GraphState):
    """Decide whether to call tools or end after LLM."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    
    return END


def route_from_db(state: GraphState):
    """Decide whether to continue to LLM or terminate if DB is empty."""
    if state.get("schema") and len(state["schema"]) > 0:
        return "llm"
    
    logger.warning("DB unavailable or no tables → routing to db_disabled.")
    return "db_disabled"
