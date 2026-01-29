from langchain_core.messages import SystemMessage
from agents.stream_writer import get_stream_writer
from agents.state import GraphState
from agents.tools import TOOLS
from agents.llm_factory import LLMFactory
from agents.config import PROVIDER
from .config import INITIAL_SUMMARY, SYSTEM
# from .utils import strip_thinking_tags

llm_factory = LLMFactory(provider=PROVIDER)
llm_with_tools = llm_factory.get_llm_with_tools(tools=TOOLS)

""" import logging
logging.basicConfig(level=logging.CRITICAL)

logger = logging.getLogger(__name__) """


async def llm_node(state: GraphState):  
    """Main reasoning node with tool bindings."""
    writer = get_stream_writer()
    writer("🤖 Thinking...")
    
    user_name = state.get("user_name")
    user_input = state.get("user_input", "")
    turn_messages = state.get("turn_messages", [])
    summary = state.get("summary", INITIAL_SUMMARY)
    schema = state.get("schema", "Database schema will be loaded when needed for queries.")

    msgs = [
        SystemMessage(
            content=SYSTEM.format(
                schema=schema, 
                summary=summary,
                user_name=user_name, 
                user_input=user_input
            )
        ),
    ]
    
    ai = await llm_with_tools.ainvoke(msgs)
    turn_messages.append(ai)
    # logger.critical(f"LLM Response: {ai.content}")
    return {"turn_messages": turn_messages}


