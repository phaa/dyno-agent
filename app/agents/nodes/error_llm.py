from langchain_core.messages import SystemMessage
from agents.state import GraphState
from agents.llm_factory import LLMFactory
from .config import ERROR_PROMPT

llm_factory = LLMFactory(provider="bedrock")
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

    msgs = [
        SystemMessage(
            content=ERROR_PROMPT.format(
                error=error,
                error_node=error_node,
                user_name=user_name
            )
        ),
    ]
    
    msgs.extend(state.get("messages", []))
    ai = await llm.ainvoke(msgs)
    
    logger.error(
        f"Graceful error handling triggered",
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


