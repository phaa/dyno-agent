import uuid
import logging
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from models.user import User
from models.conversation import Conversation, Message
from core.retry import async_retry, RetryableError, NonRetryableError

logger = logging.getLogger(__name__)

class ConversationService:
    """
    Business logic service for conversation and message management operations.
    
    This service provides core functionality for:
    - Creating and retrieving user conversations with automatic retry
    - Managing conversation state and persistence
    - Storing and retrieving chat messages with automatic retry
    - Maintaining conversation history with proper ordering
    
    The service is fully isolated from LangChain/LangGraph frameworks,
    enabling clean unit testing and reusability across different interfaces.
    
    All database operations use SQLAlchemy 2.0 async patterns with proper
    transaction management and error handling for data consistency.
    
    Retry Strategy:
    - Database operations are automatically retried on transient failures
    - Exponential backoff: 0.5s → 1s → 2s (max 5s)
    - Non-retryable errors (404, 403) fail immediately
    - Retryable errors (connection failures, timeouts) are retried
    """
    def __init__(self, db: AsyncSession):
        """
        Initializes the conversation service with a database session.
        
        Args:
            db (AsyncSession): Active SQLAlchemy async database session
                              for all database operations
        """
        self.db = db

    @async_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def get_or_create_conversation(self, user_email: str, conversation_id: str = None):
        """
        Retrieves an existing conversation or creates a new one for the user.
        
        This method handles conversation lifecycle management by either:
        - Returning an existing conversation if valid conversation_id is provided
        - Creating a new conversation with auto-generated UUID if none exists
        
        Automatically retries on database transient failures with exponential backoff.
        Non-retryable errors (validation, authorization) fail immediately.
        
        Args:
            user_email (str): Email address of the user owning the conversation
            conversation_id (str, optional): UUID of existing conversation to retrieve
            
        Returns:
            Conversation: Either the retrieved existing conversation or newly created one
            
        Raises:
            NonRetryableError: User not found or conversation access denied
            RetryableError: Database connection failures (auto-retried)
            
        Database Operations:
            - Uses get() for efficient primary key lookup
            - Validates conversation ownership by user_email
            - Creates new conversation with UUID4 identifier
            - Uses flush() + commit() for immediate availability
            
        Transaction Safety:
            - Automatic rollback on any database errors
            - Proper exception propagation for error handling
        """
        try:
            user = await self.db.get(User, user_email)
            if not user:
                raise NonRetryableError(f"User {user_email} not found")

            if conversation_id:
                conv = await self.db.get(Conversation, conversation_id)
                if not conv or conv.user_email != user_email:
                    raise NonRetryableError(f"Not authorized to access conversation {conversation_id}")
                return conv

            # Create a new conversation
            conv = Conversation(
                user_email=user_email,
                title="New Chat"
            )

            self.db.add(conv)

            try:
                await self.db.flush()  # writes to db without committing
                await self.db.commit()
            except SQLAlchemyError as e:
                await self.db.rollback()
                raise RetryableError(f"Database error creating conversation: {str(e)}") from e
            except Exception as e:
                await self.db.rollback()
                raise

            return conv
        
        except (NonRetryableError, RetryableError):
            # Re-raise our custom exceptions
            raise
        except SQLAlchemyError as e:
            # Convert database errors to retryable
            raise RetryableError(f"Database error in get_or_create_conversation: {str(e)}") from e
        except Exception as e:
            # Log unexpected errors
            logger.error(f"Unexpected error in get_or_create_conversation: {str(e)}", exc_info=True)
            raise
    
    @async_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def save_message(self, conversation_id: str, role: str, content: str):
        """
        Persists a chat message to the database with automatic timestamping and retry.
        
        Creates and stores a new message record associated with a conversation,
        maintaining the chronological order of the chat history.
        
        Automatically retries on database transient failures with exponential backoff.
        
        Args:
            conversation_id (str): UUID of the conversation this message belongs to
            role (str): Message role ('user', 'assistant', 'system', 'status')
            content (str): The actual message content/text
            
        Returns:
            Message: The created message object with auto-generated ID and timestamp
            
        Raises:
            RetryableError: Database connection failures or timeouts (auto-retried)
            
        Database Operations:
            - Creates Message with foreign key to conversation
            - Auto-generates created_at timestamp via model defaults
            - Uses flush() + commit() for immediate persistence
            
        Transaction Safety:
            - Automatic rollback on any database errors
            - Proper exception propagation for error handling
        """
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content
            )

            self.db.add(message)

            try:
                await self.db.flush()  # writes to db without committing
                await self.db.commit()
            except SQLAlchemyError as e:
                await self.db.rollback()
                raise RetryableError(f"Database error saving message: {str(e)}") from e
            except Exception as e:
                await self.db.rollback()
                raise

            return message
        
        except RetryableError:
            # Re-raise retry errors
            raise
        except SQLAlchemyError as e:
            # Convert database errors to retryable
            raise RetryableError(f"Database error in save_message: {str(e)}") from e
        except Exception as e:
            # Log unexpected errors
            logger.error(f"Unexpected error in save_message: {str(e)}", exc_info=True)
            raise

    async def get_conversations(self, user_email: str):
        """
        Retrieves all conversations for a given user.
        
        Args:
            user_email (str): Email address of the user
        """
        
        try:
            stmt = (
                select(Conversation)
                .where(Conversation.user_email == user_email)
                #.options(selectinload(Conversation.messages))
                .order_by(Conversation.updated_at.desc())
            )

            result = await self.db.execute(stmt)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_conversations: {str(e)}", exc_info=True)
            raise 


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
        try:
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(
                    Message.timestamp.asc(),
                    Message.id.asc(),
                )
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_conversation_history: {str(e)}", exc_info=True)
            raise

    @async_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def delete_conversation(self, conversation_id: str, user_email: str):
        """
        Deletes a conversation and all its associated messages.
        
        This method performs complete cleanup of a conversation:
        - Verifies the conversation belongs to the authenticated user (authorization)
        - Deletes all messages associated with the conversation (cascades automatically)
        - Deletes the conversation record itself
        
        Automatically retries on database transient failures with exponential backoff.
        Non-retryable errors (validation, authorization) fail immediately.
        
        Args:
            conversation_id (str): UUID of the conversation to delete
            user_email (str): Email address of the user (for authorization check)
            
        Returns:
            bool: True if conversation was successfully deleted, False if not found
            
        Raises:
            NonRetryableError: Conversation doesn't exist or user not authorized
            RetryableError: Database connection failures (auto-retried)
            
        Database Operations:
            - Fetches conversation for authorization validation
            - Deletes associated messages (via cascade relationship)
            - Deletes the conversation record
            - Uses flush() + commit() for immediate persistence
            
        Transaction Safety:
            - Automatic rollback on any database errors
            - Proper exception propagation for error handling
        """
        try:
            conv = await self.db.get(Conversation, conversation_id)
            if not conv:
                raise NonRetryableError(f"Conversation {conversation_id} not found")
            
            if conv.user_email != user_email:
                raise NonRetryableError(f"Not authorized to delete conversation {conversation_id}")
            
            # Delete conversation (messages will cascade delete due to relationship config)
            await self.db.delete(conv)
            
            try:
                await self.db.flush()  # writes to db without committing
                await self.db.commit()
            except SQLAlchemyError as e:
                await self.db.rollback()
                raise RetryableError(f"Database error deleting conversation: {str(e)}") from e
            except Exception as e:
                await self.db.rollback()
                raise
            
            return True
        
        except (NonRetryableError, RetryableError):
            # Re-raise our custom exceptions
            raise
        except SQLAlchemyError as e:
            raise RetryableError(f"Database error in delete_conversation: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error in delete_conversation: {str(e)}", exc_info=True)
            raise