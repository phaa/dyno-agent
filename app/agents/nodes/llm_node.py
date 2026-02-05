from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import Overwrite
from agents.stream_writer import get_stream_writer
from agents.state import GraphState
from agents.tools import TOOLS
from agents.llm_factory import LLMFactory
from agents.config import PROVIDER
from .config import INITIAL_SUMMARY, SYSTEM
# from .utils import strip_thinking_tags

llm_factory = LLMFactory(provider=PROVIDER)
llm_with_tools = llm_factory.get_llm_with_tools(tools=TOOLS)

import logging
logging.basicConfig(level=logging.CRITICAL)

logger = logging.getLogger(__name__)


async def llm_node(state: GraphState):  
    """Main reasoning node with tool bindings 

    Note on Overwrite:
    - messages uses the add_messages reducer, which appends by default.
    - We return Overwrite(updated_messages) to avoid duplicate growth
        across llm→tools→llm cycles within the same turn.
    """
        
    writer = get_stream_writer()
    writer("🤖 Thinking...")
    
    user_name = state.get("user_name")
    user_input = state.get("user_input", "")
    messages = state.get("messages", [])
    summary = state.get("summary", INITIAL_SUMMARY)
    schema = state.get("schema", "Database schema will be loaded when needed for queries.")

    system_content = SYSTEM.format(
        schema=schema, 
        summary=summary,
        user_name=user_name,
    )
    
    #logger.critical(f"System prompt length: {len(system_content)} chars")
    
    msgs = [
        SystemMessage(content=system_content),
    ]
    
    if messages:
        msgs.extend(messages)
        
    # We need the HumanMessage at the end for proper context
    if user_input:
        msgs.append(HumanMessage(content=user_input))
    
    try:
        ai = await llm_with_tools.ainvoke(msgs)
        updated_messages = list(messages) + [ai]
        # logger.critical(f"LLM Response: {ai.content}")
        return {"messages": Overwrite(updated_messages)}
    except Exception as e:
        # Log the full exception for debugging
        logger.error(f"Error in LLM node: {str(e)}")
        return {
            "retry_count": 0,  # Force immediate error handling
            "error": str(e),
            "error_node": "llm_node"
        }
        
       



