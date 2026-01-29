from typing import List, Optional, TypedDict
from typing_extensions import Annotated
from langchain_core.messages import BaseMessage
from langgraph.pregel import add_messages


class AgentSummary(TypedDict):
    decisions: List[str]
    constraints: List[str]
    open_tasks: List[str]
    context: str


class GraphState(TypedDict):
    """
    Enhanced graph state with comprehensive error handling and retry control.
    
    Error Handling Architecture:
    - **retry_count**: Remaining retry attempts (default: 2)
    - **error**: Current error message for debugging and user feedback
    - **error_node**: Which node failed (enables targeted retry strategies)
    
    Retry Strategy:
    - RetryableException: Decrements retry_count and attempts again
    - FatalException: Immediately fails without retry
    - Zero retry_count: Routes to graceful error handler
    
    Benefits for Production :
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

    # Turn-scoped (ephemeral)
    turn_messages: Annotated[list[BaseMessage], add_messages]

    # Input (ephemeral)
    user_input: str

    # Errors (ephemeral)
    retry_count: int
    error: Optional[str]
    error_node: Optional[str]

    # DB (ephemeral)
    schema: Optional[dict]