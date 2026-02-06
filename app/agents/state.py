from typing import List, Optional, TypedDict
from typing_extensions import Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentSummary(TypedDict):
    """
    Conversation summary tracking user actions in narrative format.
    
    Instead of structured fields, stores a chronological list of user actions:
    - "User allocated vehicle VIN123 to dyno 2"
    - "User asked for all AWD vehicles" 
    - "User checked conflicts for dyno 3"
    
    This format is more natural and easier to inject into LLM context
    """
    actions: List[str]


class GraphState(TypedDict):
    """
    Enhanced graph state with sliding window message management.
    
    Message Management:
    - **messages**: Full conversation history with sliding window
      - Grows until ~4-5K tokens (AI + Human messages only)
      - Auto-summarizes when limit exceeded
      - Maintains ~800 token tail for context after summarization
    
    Error Handling:
    - **retry_count**: Remaining retry attempts (default: 2)
    - **error**: Current error message for debugging and user feedback
    - **error_node**: Which node failed (enables targeted retry strategies)
    
    Retry Strategy:
    - RetryableException: Decrements retry_count and attempts again
    - FatalException: Immediately fails without retry
    - Zero retry_count: Routes to graceful error handler
    
    Benefits:
    - Automatic recovery from transient failures (network, timeouts)
    - Fast failure for permanent errors (auth, validation)
    - Comprehensive error tracking for monitoring and debugging
    - Graceful degradation when all retries exhausted
    """
    # Identity
    conversation_id: str
    user_name: str

    # Memory (persisted)
    summary: AgentSummary

    # Messages (persisted with sliding window)
    messages: Annotated[list[BaseMessage], add_messages]

    # Input (ephemeral)
    user_input: str

    # Errors (ephemeral) - retry_count com default é gerenciado no graph
    retry_count: Optional[int]
    error: Optional[str]
    error_node: Optional[str]

    # DB (ephemeral)
    schema: Optional[dict]