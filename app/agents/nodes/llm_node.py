from langchain_core.messages import SystemMessage, HumanMessage
from agents.stream_writer import get_stream_writer
from agents.state import GraphState
from agents.tools import TOOLS
from agents.llm_factory import LLMFactory
from agents.config import PROVIDER
from .config import INITIAL_SUMMARY, SYSTEM
from .utils import reset_error_state, decrement_retry_count
# from .utils import strip_thinking_tags

llm_factory = LLMFactory(provider=PROVIDER)
llm_with_tools = llm_factory.get_llm_with_tools(tools=TOOLS)

import logging
logging.basicConfig(level=logging.CRITICAL)

logger = logging.getLogger(__name__)


async def llm_node(state: GraphState):  
    """
    Main reasoning node with tool bindings and robust error handling.
    """
        
    writer = get_stream_writer()
    writer("🤖 Thinking...")
    
    user_name = state.get("user_name", "")
    user_input = state.get("user_input", "")
    messages = state.get("messages", [])
    summary = state.get("summary", INITIAL_SUMMARY)
    schema = state.get("schema", "Database schema will be loaded when needed for queries.")

    system_content = SYSTEM.format(
        schema=schema, # Dynamic schema injected for context 
        summary=summary, # Inject previous user actions for context (if any)
        user_name=user_name,
    )
    
    msgs = [SystemMessage(content=system_content)]
    msgs.extend(messages)
    
    # We need the HumanMessage at the end for proper context
    if user_input:
        msgs.append(HumanMessage(content=user_input))
    
    try:
        response = await llm_with_tools.ainvoke(msgs)
        # logger.critical(f"LLM Response: {response.content}")
        return {
            "messages": [response],
            **reset_error_state(),
        }
    
    except Exception as e:
        # Log the full exception for debugging
        logger.warning(f"Retryable error in tools: {str(e)}")
        return {
            **decrement_retry_count(state, str(e), "llm_node")
        }
        
       



