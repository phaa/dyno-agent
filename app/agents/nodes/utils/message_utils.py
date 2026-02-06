"""Message handling and token counting utilities."""

import re
import logging
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from agents.nodes.config import TOKEN_WINDOW_LIMIT, TAIL_TOKENS

logger = logging.getLogger(__name__)


def count_user_agent_tokens(messages: list[BaseMessage]) -> int:
    """
    Count tokens from only AIMessage and HumanMessage.
    Other message types (ToolMessage, SystemMessage) are ignored.
    
    Uses approximate token counting for speed.
    """
    user_agent_messages = [
        msg for msg in messages 
        if isinstance(msg, (AIMessage, HumanMessage))
    ]
    return count_tokens_approximately(user_agent_messages)


def should_summarize_messages(messages: list[BaseMessage]) -> bool:
    """
    Check if messages have exceeded the token window limit.
    Only considers AIMessage and HumanMessage for token counting.
    
    Returns:
        bool: True if summarization is needed
    """
    token_count = count_user_agent_tokens(messages)
    return token_count > TOKEN_WINDOW_LIMIT


def get_tail_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    Extract the tail of messages to keep after summarization.
    Keeps approximately TAIL_TOKENS worth of recent AI/Human messages.
    
    Args:
        messages: All messages from the conversation
        
    Returns:
        list[BaseMessage]: The tail messages to preserve (reversed from newest)
    """
    tail = []
    token_count = 0
    
    # Iterate from end (newest) backwards
    for msg in reversed(messages):
        if isinstance(msg, (AIMessage, HumanMessage)):
            msg_tokens = count_tokens_approximately([msg])
            token_count += msg_tokens
            tail.insert(0, msg)  # Insert at beginning to maintain order
            
            if token_count >= TAIL_TOKENS:
                break
    
    return tail


def should_summarize(messages: list) -> bool:
    """Check if messages should be summarized based on length or token count."""
    tokens_count = count_tokens_approximately(messages)
    return (
        len(messages) >= 10 or
        tokens_count > 8000
    )


def strip_thinking_tags(content: str) -> str:
    """
    Remove all <thinking>...</thinking> segments from content.
    Handles multiple thinking blocks in a single pass for performance.

    Args:
        content: The message content that may contain thinking tags

    Returns:
        Content with thinking tags removed, or empty string if nothing remains
    """
    if not content:
        return ""

    # Fast path: no thinking tags present
    if "<thinking>" not in content:
        cleaned = '\n'.join(line.rstrip() for line in content.split('\n'))
        return re.sub(r'\n\s*\n+', '\n\n', cleaned).strip()

    # Single-pass removal of all segments between <thinking> and </thinking>
    # Avoids regex backtracking overhead on long messages
    result_chars = []
    i = 0
    n = len(content)
    in_thinking = False
    open_tag = "<thinking>"
    close_tag = "</thinking>"

    while i < n:
        if not in_thinking and content.startswith(open_tag, i):
            in_thinking = True
            i += len(open_tag)
            continue
        if in_thinking and content.startswith(close_tag, i):
            in_thinking = False
            i += len(close_tag)
            continue
        if not in_thinking:
            result_chars.append(content[i])
        i += 1

    cleaned = ''.join(result_chars)
    cleaned = '\n'.join(line.rstrip() for line in cleaned.split('\n'))
    cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned).strip()
    return cleaned
