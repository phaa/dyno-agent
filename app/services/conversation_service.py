import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.conversation import Conversation, Message

class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_conversation(self, user_email: str, conversation_id: str):
        if conversation_id:
            conv = await self.db.get(Conversation, conversation_id)
            if conv and conv.user_email == user_email:
                return conv
            
        # Create a new conversation
        conv = Conversation(
            id=str(uuid.uuid4()),
            user_email=user_email,
            title="New Chat"
        )

        self.db.add(conv)
        await self.db.flush()  # Ensure the conversation is saved and has an ID
        return conv
    
    async def save_message(self, conversation_id: str, role: str, content: str):
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )

        self.db.add(message)
        await self.db.flush()  # Ensure the message is saved and has an ID
        return message

    async def get_conversation_history(self, conversation_id: str, limit: int = 50):
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        messages = result.scalars().all()

        # Invert to chronological order
        return list(reversed(messages))