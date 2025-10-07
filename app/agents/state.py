from typing import Optional
from langgraph.graph import MessagesState


class GraphState(MessagesState):
    allowed_tables: list[str]
    






""" last_name: Optional[str]
    customer: bool
    customer_id: Optional[int] """