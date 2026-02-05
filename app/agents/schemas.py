"""
Pydantic schemas for agent data validation.
"""
from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    """
    Schema for conversation history in narrative action format.
    
    Stores user actions chronologically as simple past-tense sentences.
    This format is more natural for LLM context and easier to interpret.
    """
    actions: list[str] = Field(
        default_factory=list,
        description="Chronological list of user actions in this conversation (max 10)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "actions": [
                    "User allocated vehicle VIN123 to dyno 2 starting 2024-06-01",
                    "User asked for all AWD vehicles",
                    "User checked conflicts for dyno 3"
                ]
            }
        }

