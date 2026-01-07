import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.conversation import Conversation, Message

class ConversationService:
    """
    Business logic service for conversation and message management operations.
    
    This service provides core functionality for:
    - Creating and retrieving user conversations
    - Managing conversation state and persistence
    - Storing and retrieving chat messages
    - Maintaining conversation history with proper ordering
    
    The service is fully isolated from LangChain/LangGraph frameworks,
    enabling clean unit testing and reusability across different interfaces.
    
    All database operations use SQLAlchemy 2.0 async patterns with proper
    transaction management and error handling for data consistency.
    """
    def __init__(self, db: AsyncSession):
        """
        Initializes the conversation service with a database session.
        
        Args:
            db (AsyncSession): Active SQLAlchemy async database session
                              for all database operations
        """
        self.db = db

    async def get_or_create_conversation(self, user_email: str, conversation_id: str = None):
        """
        Retrieves an existing conversation or creates a new one for the user.
        
        This method handles conversation lifecycle management by either:
        - Returning an existing conversation if valid conversation_id is provided
        - Creating a new conversation with auto-generated UUID if none exists
        
        Args:
            user_email (str): Email address of the user owning the conversation
            conversation_id (str, optional): UUID of existing conversation to retrieve
            
        Returns:
            Conversation: Either the retrieved existing conversation or newly created one
            
        Database Operations:
            - Uses get() for efficient primary key lookup
            - Validates conversation ownership by user_email
            - Creates new conversation with UUID4 identifier
            - Uses flush() + commit() for immediate availability
            
        Transaction Safety:
            - Automatic rollback on any database errors
            - Proper exception propagation for error handling
        """
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

        try:
            await self.db.flush() # writes to db withou committing
            #await self.db.refresh(conv)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise

        return conv
    
    async def save_message(self, conversation_id: str, role: str, content: str):
        """
        Persists a chat message to the database with automatic timestamping.
        
        Creates and stores a new message record associated with a conversation,
        maintaining the chronological order of the chat history.
        
        Args:
            conversation_id (str): UUID of the conversation this message belongs to
            role (str): Message role ('user', 'assistant', 'system')
            content (str): The actual message content/text
            
        Returns:
            Message: The created message object with auto-generated ID and timestamp
            
        Database Operations:
            - Creates Message with foreign key to conversation
            - Auto-generates created_at timestamp via model defaults
            - Uses flush() + commit() for immediate persistence
            
        Transaction Safety:
            - Automatic rollback on any database errors
            - Proper exception propagation for error handling
        """
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )

        self.db.add(message)

        try:
            await self.db.flush() # writes to db withou committing
            #await self.db.refresh(conv)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise

        return message

    async def get_conversation_history(self, conversation_id: str, limit: int = 50):
        """
        Retrieves the chronological message history for a conversation.
        
        Fetches messages in reverse chronological order (newest first) from the database,
        then reverses the list to return messages in chronological order (oldest first)
        for proper conversation flow display.
        
        Args:
            conversation_id (str): UUID of the conversation to retrieve history for
            limit (int): Maximum number of messages to retrieve (default: 50)
            
        Returns:
            list[Message]: List of message objects ordered chronologically (oldest first)
            
        Database Operations:
            - Filters messages by conversation_id foreign key
            - Orders by created_at DESC for efficient recent message retrieval
            - Applies LIMIT for performance with large conversation histories
            - Reverses result list for chronological display order
            
        Note:
            There's a bug in the current implementation - uses self.session instead of self.db
        """
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(
                Message.created_at.asc(),
                Message.id.asc(),
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()