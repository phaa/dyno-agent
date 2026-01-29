"""
Pydantic schemas for agent data validation.
"""
from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    """
    Schema for validated conversation summary structure.
    
    This schema enforces the structured format used by the summarization node
    to maintain conversation context in a compressed, high-signal format.
    """
    decisions: list[str] = Field(
        default_factory=list,
        description="Key decisions made during the conversation"
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Important constraints or limitations mentioned"
    )
    open_tasks: list[str] = Field(
        default_factory=list,
        description="Pending tasks or actions to be completed"
    )
    context: str = Field(
        default="",
        description="General context and background information from the conversation"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "decisions": ["User allocated vehicle VIN 123 to dyno ID 45"],
                "constraints": ["4k miles tests cannot be allocated to dynos under maintenance"],
                "open_tasks": ["Check for delayed allocations"],
                "context": "User is managing vehicle-dyno allocations and needs to track maintenance status."
            }
        }
