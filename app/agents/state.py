from typing import Optional
from langgraph.graph import MessagesState


class GraphState(MessagesState):
    user_name: str
    schema: Optional[list[str]] = None
