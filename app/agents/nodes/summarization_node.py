import json
import logging
from typing import Literal
from langchain_core.messages import BaseMessage, AIMessage, RemoveMessage
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.types import Command
from agents.stream_writer import get_stream_writer
from agents.state import GraphState
from agents.llm_factory import LLMFactory
from agents.schemas import ConversationSummary
from agents.config import PROVIDER
from .config import (
    SUMMARY_PROMPT, 
    INITIAL_SUMMARY,
)
from .utils import (
    should_summarize_messages,
    count_user_agent_tokens,
    get_tail_messages,
)

logger = logging.getLogger(__name__)
llm_factory = LLMFactory(provider=PROVIDER)
summarization_llm = llm_factory.get_summary_llm()


async def summarization_node(state: GraphState) -> Command[Literal["__end__"]]:
    """
    Implements sliding window message management with automatic summarization to prevent unbounded token growth.

    This node monitors the total token count of the conversation and triggers compression when it exceeds
    the TOKEN_WINDOW_LIMIT (default: 4500 tokens). When triggered, it:
    1. Compresses old messages into a narrative summary of actions taken
    2. Removes old messages from state using RemoveMessage
    3. Preserves the most recent messages (~TAIL_TOKENS, default: 800)
    
    Sliding Window Strategy:
    - Token Limit: Triggers when messages exceed ~4500 tokens
    - Compression: Old messages → JSON list of action descriptions
    - Preservation: Keeps ~800 tokens of recent conversation intact
    - Efficiency: State drops from 4500 → 800 tokens after compression
    
    This approach ensures:
    - No re-summarization every turn (only when threshold crossed)
    - Fresh context always available in recent messages
    - Long-term memory preserved in structured summary
    - Optimal LLM performance with bounded context window

    Routing Logic:
    - Always ends graph: Always routes to END after summarization

    Args:
        state (GraphState): Current graph state containing 'messages' (List[BaseMessage]) 
                           and 'summary' (Dict with 'actions' list).

    Returns:
        Command: State update with next node routing to END
    """
    
    messages = state.get("messages", [])
    summary = state.get("summary", INITIAL_SUMMARY)
    
    token_count = count_user_agent_tokens(messages)
    
    # Check if we need to summarize based on token count
    if not should_summarize_messages(messages):
        logger.debug(f"Token count within limit ({token_count} tokens), skipping summarization")
        return Command(update={}, goto="__end__")
    
    logger.info(f"Token count ({token_count}) exceeds limit, triggering summarization")
    
    writer = get_stream_writer()
    writer(f"🤖 Compressing conversation history ({token_count} tokens)....")
    
    tail_messages = get_tail_messages(messages)
    
    # Messages to summarize (everything except tail)
    last_message_to_summarize_idx = -len(tail_messages)
    messages_to_summarize = messages[0:last_message_to_summarize_idx] if tail_messages else messages
    
    prompt = SUMMARY_PROMPT.format(
        previous_summary=json.dumps(summary, ensure_ascii=False),
        messages=format_messages(messages_to_summarize) 
    )

    try:
        parser = PydanticOutputParser(
            pydantic_object=ConversationSummary 
        )

        chain = summarization_llm | parser
        validated = await chain.ainvoke(prompt)

        remove_messages = [
            RemoveMessage(id=m.id) 
            for m in messages_to_summarize 
            if m.id
        ]
        
        logger.info(f"Summarization complete: removed {len(remove_messages)} messages, kept {len(tail_messages)} tail messages")

        return Command(
            update={
                "summary": validated.model_dump(),
                "messages": remove_messages,  # RemoveMessage will delete these from state
            },
            goto="__end__"
        )
        
    except Exception as e:
        logger.exception(f"Error during summarization_node execution: {e}")
        # Fail safe - preserve original state and end graph
        return Command(update={}, goto="__end__") 
    
    
def format_messages(messages: list[BaseMessage]) -> str:
    return "\n".join(
        f"{m.type.upper()}: {m.content}" for m in messages
    )