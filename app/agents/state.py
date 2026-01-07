from typing import List, Optional, TypedDict
from langchain.messages import AnyMessage
from langmem.short_term import RunningSummary
from langgraph.graph import MessagesState


class AgentSummary(TypedDict):
    decisions: List[str]
    constraints: List[str]
    open_tasks: List[str]
    context: str


class GraphState(MessagesState):
    summary: AgentSummary
    user_name: str
    schema: Optional[list[str]] = None