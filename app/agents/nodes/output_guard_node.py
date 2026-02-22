import re
from typing import Literal
from langgraph.types import Command
from agents.state import GraphState

SQL_PATTERNS = [
    r"(?is)```sql.*?```",
    r"(?i)\bselect\b.*\bfrom\b",
    r"(?i)\binsert\b.*\binto\b",
    r"(?i)\bdelete\b.*\bfrom\b",
    r"(?i)\bupdate\b.*\bset\b",
    r"(?i)\bdrop\b\s+\btable\b",
]

MSG_REMOVED = "[SQL REMOVED FOR SECURITY]"

def sanitize_sql(text: str) -> str:
    sanitized = text
    for pattern in SQL_PATTERNS:
        sanitized = re.sub(pattern, MSG_REMOVED, sanitized)
    return sanitized 

def output_guard_node(state: GraphState) -> Command[Literal["__end__", "error_llm"]]:
    """Output guard node to prevent SQL injection in response.
    
    Routing Logic:
    - SQL detected: Routes to 'error_llm' for graceful error handling
    - Safe output: Routes to END to complete the graph
    """
    text = state.get("response", "")

    for pattern in SQL_PATTERNS:
        if re.search(pattern, text):
            return Command(
                update={
                    "error": f"LLM response blocked. SQL queries detected in output.", 
                    "error_node": "output_guard_node",
                    "retry_count": 0
                },
                goto="error_llm"
            )

    # Output is safe, proceed to end
    return Command(update=state, goto="__end__")