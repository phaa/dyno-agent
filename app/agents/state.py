from typing import List, Optional, TypedDict
from langgraph.graph import MessagesState


class AgentSummary(TypedDict):
    decisions: List[str]
    constraints: List[str]
    open_tasks: List[str]
    context: str


class GraphState(MessagesState):
    conversation_id: str
    user_name: str
    summary: AgentSummary
    # Error handling fields
    retry_count: int = 2
    error: Optional[str]
    error_node: Optional[str]
    # DB schema info
    schema: Optional[list[str]] = None