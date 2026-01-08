import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.prebuilt import ToolNode
from core.config import GEMINI_MODEL_ID
from ..state import AgentSummary
from ..tools import (
    find_available_dynos,
    check_vehicle_allocation,
    detect_conflicts,
    completed_tests_count,
    maintenance_check,
    query_database,
    get_datetime_now,
    auto_allocate_vehicle
)

# System prompt
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

# Summarization prompts
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

# LLM instances - lazy initialization to avoid import errors
def get_summary_llm():
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL_ID,
        temperature=0.0,
        max_output_tokens=400,
        max_retries=2,
    )

def get_llm():
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL_ID,
        api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.5,
        max_output_tokens=1024,
        timeout=None,
        max_retries=2,
    )

# Tools setup - lazy initialization
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

def get_model_with_tools():
    llm = get_llm()
    return llm.bind_tools(tools)

def get_tool_node():
    return ToolNode(tools)

# Helper functions
def should_summarize(messages: list) -> bool:
    return (
        len(messages) >= 6 or
        count_tokens_approximately(messages) > 1800
    )