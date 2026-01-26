from langchain_core.messages import SystemMessage, AIMessage
from langgraph.config import get_stream_writer
from agents.state import GraphState
from agents.tools import TOOLS
from agents.llm_factory import LLMFactory
from .config import SYSTEM
from .utils import strip_thinking_tags

llm_factory = LLMFactory(provider="bedrock")
llm_with_tools = llm_factory.get_llm_with_tools(tools=TOOLS)

""" import logging
logging.basicConfig(level=logging.CRITICAL)

logger = logging.getLogger(__name__) """


async def llm_node(state: GraphState):
    """Main reasoning node with tool bindings."""
    writer = get_stream_writer()
    writer("🤖 Thinking...")
    
    user_name = state.get("user_name")
    schema = state.get("schema", "Database schema will be loaded when needed for queries.")

    msgs = [
        SystemMessage(
            content=SYSTEM.format(schema=schema, user_name=user_name)
        ),
    ]
    
    msgs.extend(state.get("messages", []))
    
    ai = await llm_with_tools.ainvoke(msgs)
    
    # logger.critical(f"LLM Response: {ai.content}")
    
    return {"messages": [ai]}


