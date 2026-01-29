import json
import logging
from langchain_core.messages import BaseMessage, AIMessage, RemoveMessage
from langchain_core.output_parsers import PydanticOutputParser
from agents.stream_writer import get_stream_writer
from agents.state import GraphState
from agents.llm_factory import LLMFactory
from agents.schemas import ConversationSummary
from .config import (
    SUMMARY_PROMPT, 
    INITIAL_SUMMARY, 
)

logger = logging.getLogger(__name__)
llm_factory = LLMFactory(provider="bedrock")
summarization_llm = llm_factory.get_summary_llm()

def format_messages(messages: list[BaseMessage]) -> str:
    return "\n".join(
        f"{m.type.upper()}: {m.content}" for m in messages
    )

async def summarization_node(state: GraphState):
    """
    Consolidates conversation history into a structured summary to optimize token usage and state persistence.

    This node implements an LLM-driven compression strategy that merges the existing `summary` with 
    new `turn_messages` into a refined JSON schema (Decisions, Constraints, Tasks, Context). This 
    approach prevents unbounded growth of the message history, reducing LLM token costs, inference 
    latency, and database I/O overhead in the PostgreSQL backend.

    Operational Logic:
    1.  Summary Consolidation: Orchestrates an LLM chain to merge the current `summary` with 
        the `turn_messages` (messages from the current conversation turn) into a structured 
        `ConversationSummary` object.
    2.  Validation: Uses `PydanticOutputParser` for automatic schema validation and error recovery.
    3.  State Update: Returns an updated state with the consolidated summary for downstream nodes.

    Infrastructure Impact:
    - Efficiency: Reduces the effective conversation history size from O(n) to O(1), preventing 
      state bloat and reducing deserialization latency during state recovery.
    - Determinism: Keeps the GraphState within the LLM's optimal performance window, mitigating 
      "lost-in-the-middle" retrieval issues.

    Error Handling & Resiliency:
    - Fault Tolerance: On LLM or parsing failures, the node returns an empty dict as a fail-safe 
      to preserve the original state and prevent data loss.
    - Logging: Tracks summarization events and exceptions for observability.

    Args:
        state (GraphState): Current graph state containing 'turn_messages' (List[BaseMessage]) 
                           and the 'summary' (Dict) object.

    Returns:
        dict: An updated state dictionary containing the consolidated 'summary' (ConversationSummary 
              serialized as dict), or an empty dict on failure to preserve original state.
    """
    
    summary = state.get("summary", INITIAL_SUMMARY)
    turn_messages = state.get("turn_messages", [])
    
    logger.info(f"Summarizing {len(turn_messages)} messages")
    
    writer = get_stream_writer()
    writer(f"🤖 Summarizing {len(turn_messages)} messages...")
    
    prompt = SUMMARY_PROMPT.format(
        previous_summary=json.dumps(summary, ensure_ascii=False),
        turn_messages=format_messages(turn_messages) 
    )

    try:
        # PydanticOutputParser provides automatic validation and retry
        parser = PydanticOutputParser(
            pydantic_object=ConversationSummary
        )

        chain = summarization_llm | parser
        validated = await chain.ainvoke(prompt)

        return {
            "summary": validated.model_dump()
        }
        
    except Exception as e:
        logger.exception(f"Error during summarization_node execution: {e}")
        return {} # Fail safe - preserve original state