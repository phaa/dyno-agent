from typing import List, Optional, TypedDict
from langgraph.graph import MessagesState


class AgentSummary(TypedDict):
    decisions: List[str]
    constraints: List[str]
    open_tasks: List[str]
    context: str


class GraphState(MessagesState):
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
    conversation_id: str
    user_name: str
    summary: AgentSummary
    # Error handling fields
    retry_count: int = 2
    error: Optional[str]
    error_node: Optional[str]
    # DB schema info
    schema: Optional[list[str]] = None