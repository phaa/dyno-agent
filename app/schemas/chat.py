from pydantic import BaseModel, field_validator

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str
    user_email: str 

    @field_validator('user_email')
    def no_email(cls, v):
        if not v or "@" not in v:
            raise ValueError("Please provide a valid email address")
        return v
    
    @field_validator('message')
    def no_message(cls, v):
        if not v:
            raise ValueError("Please provide a message")
        return v