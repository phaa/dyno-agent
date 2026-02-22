from typing import TypedDict
from sqlalchemy.ext.asyncio import AsyncSession

class ContextSchema(TypedDict):
    db: AsyncSession