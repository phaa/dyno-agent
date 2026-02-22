from typing import Literal
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langgraph.types import Command
from agents.stream_writer import get_stream_writer
from agents.state import GraphState
from agents.tools import TOOLS
from agents.llm_factory import LLMFactory
from agents.config import PROVIDER
from .config import INITIAL_SUMMARY, SYSTEM
from .utils import get_reset_error_state, get_decrement_retry_count

llm_factory = LLMFactory(provider=PROVIDER)
llm_with_tools = llm_factory.get_llm_with_tools(tools=TOOLS)

import logging
logging.basicConfig(level=logging.CRITICAL)

logger = logging.getLogger(__name__)


async def llm_node(state: GraphState) -> Command[Literal["llm", "tools", "summarize", "error_llm"]]:  
    """
    LLM node with integrated routing logic.
    
    Routing Logic:
    - Tool calls detected: Routes to 'tools' for execution
    - No tool calls: Routes to 'summarize' for context management
    - Error with retries: Routes back to 'llm' for retry
    - Retries exhausted: Routes to 'error_llm' for graceful handling
    
    Args:
        state: Current graph state
        
    Returns:
        Command: State update with next node routing
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
    
    msgs: list[BaseMessage] = [SystemMessage(content=system_content)]
    msgs.extend(messages)
    
    # HumanMessage is needed at the end for proper context
    if user_input:
        msgs.append(HumanMessage(content=user_input))
    
    try:
        response = await llm_with_tools.ainvoke(msgs)
        
        # Check if response contains tool calls
        if isinstance(response, AIMessage) and response.tool_calls:
            next_node = "tools"
        else:
            next_node = "summarize"
        
        return Command(
            update={
                "messages": [response],
                **get_reset_error_state(),
            },
            goto=next_node
        )
    
    except Exception as e:
        logger.warning(f"Retryable error in llm: {str(e)}")
        error_update = get_decrement_retry_count(state, str(e), "llm_node")
        retry_count = error_update.get("retry_count", 0)
        
        next_node = "llm" if retry_count > 0 else "error_llm"
        return Command(update=error_update, goto=next_node)
        
       



