import re
from pydantic import BaseModel, Field, field_validator

class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="The message the chat agent (1-5000 characters)",
    )
    # conversation_id is a UUID string to identify the conversation
    conversation_id: str | None = Field(
        None,
        description="The ID of the conversation. If not provided, a new conversation will be started.",
    )
    
    @field_validator('message')
    def validate_message(cls, v: str):
        v = v.strip()

        if not v:
            raise ValueError("Please provide a message")

        # Prevent SQL injection patterns
        sql_patterns = [
            r"(?i)(drop|delete|truncate|union|select).*(from|where)",
            r"(?i)execute\s*\(",
        ]
        for pattern in sql_patterns:
            if re.search(pattern, v):
                raise ValueError("Message contains suspicious SQL patterns")
        
        # Prevent script injection
        if "<script>" in v.lower() or "javascript:" in v.lower():
            raise ValueError("Message contains script injection attempt")
        
        # Prevent prompt injection (common attack on LLMs)
        prompt_injection_patterns = [
            r"(?i)ignore.*previous.*instructions",
            r"(?i)pretend.*you.*are",
            r"(?i)system.*prompt",
        ]
        for pattern in prompt_injection_patterns:
            if re.search(pattern, v):
                raise ValueError("Message appears to be prompt injection attempt")
            
        return v


class ChatResponse(BaseModel):
    response: str
    conversation_id: str