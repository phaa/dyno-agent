import os
import logging
import json
from langchain_core.messages import AIMessage, SystemMessage, BaseMessage
from langgraph.graph import END
from sqlalchemy import text
from core.config import GEMINI_MODEL_ID
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.prebuilt import ToolNode
from langgraph.runtime import get_runtime
from langgraph.config import get_stream_writer

from .state import AgentSummary, GraphState 
from .tools import (
    find_available_dynos,
    check_vehicle_allocation,
    detect_conflicts,
    completed_tests_count,
    maintenance_check,
    query_database,
    get_datetime_now,
    auto_allocate_vehicle
)

logger = logging.getLogger(__name__)

SYSTEM = """
You are an assistant specialized in vehicle dynamometers.  
You are free to use any of the given tools and query the following database:

{schema}

Whenever the user asks for information, use all available tools to make the response as complete as possible.

Use **markdown formatting** for all outputs.

**Formatting rules:**
- Use bullet points for short lists.
- For vertical numbered lists with descriptions, use this format:
  - Item 1: description
  - Item 2: description
  - Item 3: description
  End each item with a newline.
- For horizontal lists, separate items with commas.
- When listing multiple objects of the same type (e.g., multiple vehicle allocations, tests, or dynamometers), present them as a **Markdown table** whenever possible, using clear headers (e.g., | ID | Vehicle | Test Type | Start | End | Status |).
- When using Markdown tables:
  - Always start the table on a new line.
  - Each table row must have a line break at the end.
  - Do not merge rows into a single line.
  - Example:
    | **Column 1** | **Column 2** |
    |--------------|--------------|
    |   Value 1    |   Value 2    |
    |   Value 3    |   Value 4    |
- If a table is not appropriate (for example, when showing detailed records of one entity at a time), **separate each record visually** using a horizontal rule (`---`) between them.
- Always ensure the output is **easy to read** and **well-structured**.
- Always give accurate and complete information.  
- If you don't know the answer, just say you don't know. Never make up an answer.

Address the user as {user_name}.
"""


# -------------------------------
# Summarization configuration
# -------------------------------

SUMMARY_PROMPT = """
You are updating a structured conversation summary for a production system.

Rules (STRICT):
- Only use information explicitly stated in the messages.
- NEVER remove existing decisions or constraints.
- NEVER rephrase constraints or decisions.
- NEVER infer intent or add new information.
- If information is unclear, keep the previous value.
- Keep lists concise and factual.
- Context must be a short neutral narrative (max 5 lines).

Previous summary (JSON):
{previous_summary}

New messages:
{messages}

Return ONLY valid JSON following this schema:
{{
  "decisions": string[],
  "constraints": string[],
  "open_tasks": string[],
  "context": string
}}
"""

CONVERSATION_SUMMARY_PROMPT = """
Conversation summary:
Decisions:
{decisions}

Constraints:
{constraints}

Open tasks:
{open_tasks}

Context:
{context}
"""

INITIAL_SUMMARY: AgentSummary = {
    "decisions": [],
    "constraints": [],
    "open_tasks": [],
    "context": ""
}

summary_llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL_ID,
    temperature=0.0,          # production safe
    max_output_tokens=400,
    max_retries=2,
)

# -------------------------------
# LLM configuration
# -------------------------------
llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL_ID,
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.5,
    max_output_tokens=1024,
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
    auto_allocate_vehicle
]
 
model_with_tools = llm.bind_tools(tools)
 
# -------------------------------
# Nodes
# -------------------------------
tool_node = ToolNode(tools)


def should_summarize(messages: list) -> bool:
    return (
        len(messages) >= 6 or
        count_tokens_approximately(messages) > 1800
    )


def format_messages(messages: list[BaseMessage]) -> str:
    return "\n".join(
        f"{m.type.upper()}: {m.content}" for m in messages
    )

async def summarization_node(state: GraphState):
    messages = state.get("messages", [])
    summary = state.get("summary", INITIAL_SUMMARY)
    
    if not should_summarize(messages):
        return state # No summarization needed, continue the flow
    
    prompt = SUMMARY_PROMPT.format(
        previous_summary=json.dumps(summary, ensure_ascii=False),
        messages=format_messages(messages)
    )

    try:
        reponse = await summary_llm.ainvoke(prompt)
        new_summary = json.loads(reponse.content)
    except Exception as e:
        logger.error(f"Summarization failed — keeping messages intact")
        return state # Fail safe

    return {
        "summary": new_summary,
        "messages": [] # Messages have been summarized
    }

async def get_schema_node(state: GraphState) -> GraphState:
    """Fetch the full schema (tables + columns) from public schema."""
    writer = get_stream_writer()
    writer("📊 Loading database schema...")
    
    runtime = get_runtime()
    db = runtime.context.db
    
    # Single query to get all tables and columns to avoid connection conflicts
    sql_schema = """
        SELECT t.table_name, c.column_name
        FROM information_schema.tables t
        JOIN information_schema.columns c ON t.table_name = c.table_name
        WHERE t.table_schema = 'public' AND c.table_schema = 'public'
        ORDER BY t.table_name, c.ordinal_position;
    """
    
    result = await db.execute(text(sql_schema))
    rows = result.fetchall()
    
    schema = {}
    for table_name, column_name in rows:
        if table_name not in schema:
            schema[table_name] = []
        schema[table_name].append(column_name)

    return {
        "schema": schema,
    }


def db_disabled_node(state: GraphState) -> GraphState:
    """Handles the case where the database is empty or unreachable."""

    error_message = "Apparently our database is not configured. Aborting further operations"
    return {
        "messages": [AIMessage(content=error_message)]
    }


async def llm_node(state: GraphState):
    """Main reasoning node with tool bindings."""
    writer = get_stream_writer()
    writer("🤖 Thinking...")
    
    summary = state.get("summary", INITIAL_SUMMARY)
    user_name = state.get("user_name")
    schema = state.get("schema")

    msgs = [
        SystemMessage(
            content=SYSTEM.format(schema=schema, user_name=user_name)
        ),
        SystemMessage(
            content=CONVERSATION_SUMMARY_PROMPT.format(
                decisions="\n".join(summary["decisions"]),
                constraints="\n".join(summary["constraints"]),
                open_tasks="\n".join(summary["open_tasks"]),
                context=summary["context"]
            )
        )
    ]
    
    msgs.extend(state.get("messages", []))

    ai: AIMessage = await model_with_tools.ainvoke(msgs)

    return {"messages": [ai]}


# -------------------------------
# Routers (branching logic)
# -------------------------------
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
    

