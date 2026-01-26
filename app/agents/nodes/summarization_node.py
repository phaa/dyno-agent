import json
import logging
from langchain_core.messages import BaseMessage, SystemMessage, RemoveMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.config import get_stream_writer
from agents.state import GraphState
from agents.llm_factory import LLMFactory
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
    Performs structured state compression and history pruning to optimize context window and persistence.

    This node implements a "Garbage Collection" strategy for the conversation state. It prevents 
    unbounded growth of the message history, which directly impacts LLM token costs, inference 
    latency, and checkpointer I/O overhead within the PostgreSQL backend.

    Operational Logic:
    1.  State Consolidation: Orchestrates an LLM chain to merge the existing `summary` with 
        new `messages` into a refined JSON schema (Decisions, Constraints, Tasks, Context).
    2.  Checkpointer Optimization (Pruning): Generates `RemoveMessage` instructions for all 
        processed messages. This signals the `AsyncPostgresSaver` to exclude these message 
        IDs from the active state in subsequent checkpoints.
    3.  State Re-entry: Injects a `SystemMessage` with the `[CONVERSATION_SUMMARIZED]` tag, 
        ensuring downstream nodes operate on a high-signal, low-noise context.

    Infrastructure Impact:
    - PostgreSQL Efficiency: By pruning messages, the serialized state size is reduced from 
      O(n) to O(1) relative to the pruned history, preventing database bloat and reducing 
      deserialization latency during state recovery.
    - Determinism: Ensures the GraphState remains within the LLM's optimal performance 
      window, mitigating "lost-in-the-middle" retrieval issues.

    Error Handling & Resiliency:
    - Fault Tolerance: On LLM or Parsing failures, the node implements a fail-safe return 
      of the original state to prevent data loss.
    - ID Validation: Monitors for messages lacking unique identifiers. Messages without 
      IDs cannot be pruned via `RemoveMessage` and will trigger a system warning to 
      alert for potential state corruption or misconfiguration.

    Args:
        state (GraphState): Current graph state containing 'messages' (List[BaseMessage]) 
                           and the 'summary' (Dict) object.

    Returns:
        GraphState: An updated state dictionary containing the consolidated 'summary' 
                   and a list of `RemoveMessage` + `SystemMessage` objects.
    """
    
    messages = state.get("messages", [])
    summary = state.get("summary", INITIAL_SUMMARY)
    conversation_id = state.get("conversation_id", "unknown")
    
    logger.info(f"Summarizing {len(messages)} messages")
    
    writer = get_stream_writer()
    writer(f"🤖 Summarizing {len(messages)} messages...")
    
    prompt = SUMMARY_PROMPT.format(
        previous_summary=json.dumps(summary, ensure_ascii=False),
        messages=format_messages(messages) 
    )

    try:
        chain = summarization_llm | JsonOutputParser()
        new_summary = await chain.ainvoke(prompt)
        
        # Validate summary structure before committing
        required_keys = {"decisions", "constraints", "open_tasks", "context"}
        if not isinstance(new_summary, dict) or not required_keys.issubset(new_summary.keys()):
            raise ValueError(f"Invalid summary structure. Expected keys: {required_keys}")
        
        logger.info(f"Summarization completed successfully for conversation_id: {conversation_id}")
        
        # Checkpointer optimization: Replace all messages with single summary marker
        ids_to_delete = [m.id for m in messages if m.id]
        if len(ids_to_delete) != len(messages):
            logger.warning(f"Some messages do not have ID and could not be removed from state in {conversation_id}")

        delete_messages = [RemoveMessage(id=mid) for mid in ids_to_delete]
        summary_marker = SystemMessage(
            content=f"[CONVERSATION_SUMMARIZED] \n{json.dumps(new_summary, ensure_ascii=False)}"
        )
        
        return {
            "messages": delete_messages + [summary_marker]  # Single message for checkpointer efficiency
        }
        
    except Exception as e:
        logger.exception(
            "Error during summarization_node execution",
            extra={
                "conversation_id": conversation_id,
                "node": "summarization_node"
            }
        )
        return {} # Fail safe - preserve original state