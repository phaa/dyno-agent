from pydantic import BaseModel, field_validator

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    
    @field_validator('message')
    def no_message(cls, v):
        if not v:
            raise ValueError("Please provide a message")
        return v