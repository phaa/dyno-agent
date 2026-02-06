from langchain_core.messages import SystemMessage
from agents.state import GraphState
from agents.llm_factory import LLMFactory
from agents.config import PROVIDER
from .config import ERROR_PROMPT

llm_factory = LLMFactory(provider=PROVIDER)
llm = llm_factory.get_summary_llm()

import logging
logging.basicConfig(level=logging.CRITICAL)

logger = logging.getLogger(__name__)


async def error_llm(state: GraphState):
    """LLM node for error handling."""
    
    error = state.get("error")
    error_node = state.get("error_node")
    user_name = state.get("user_name")
    retry_count = state.get("retry_count", 0)
    user_input = state.get("user_input", "")

    msgs = [
        SystemMessage(
            content=ERROR_PROMPT.format(
                error=error,
                error_node=error_node,
                user_name=user_name,
                user_input=user_input,
            )
        ),
    ]
    
    try:
        ai = await llm.ainvoke(msgs)
        
        logger.error(
            f"Graceful error handling triggered after '{error_node}' with message: {error} . Error llm response: {ai.content}",
            extra={
                "error_message": error,
                "failed_node": error_node,  
                "retry_attempts_left": retry_count
            }
        )
        
        return {
            "messages": [ai],
            "error": None,  # Clear error state
            "error_node": None,
            "retry_count": 2 
        }
    except Exception as e:
        logger.error(f"Error in error_llm node: {str(e)}")

