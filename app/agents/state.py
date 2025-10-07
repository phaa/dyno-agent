from typing import Optional
from langgraph.graph import MessagesState
from sqlalchemy.ext.asyncio import AsyncSession


class GraphState(MessagesState):
    user_name: str
    db: AsyncSession
    allowed_tables: Optional[list[str]] = None
    



""" last_name: Optional[str]
    customer: bool
    customer_id: Optional[int] """