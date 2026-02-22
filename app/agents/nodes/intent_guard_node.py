from typing import Literal
from langchain_core.messages import SystemMessage
from langgraph.types import Command
from agents.state import GraphState
from agents.llm_factory import LLMFactory
from agents.config import PROVIDER
from .config import INTENT_PROMPT

intent_llm = LLMFactory(provider=PROVIDER).get_intent_llm()

async def intent_guard_node(state: GraphState) -> Command[Literal["llm", "error_llm"]]:
    """Node to guard against disallowed user intents.
    
    Routing Logic:
    - Intent blocked: Routes to 'error_llm' for graceful error handling
    - Intent allowed: Routes to 'llm' to proceed with reasoning
    """
    user_input = state.get("user_input", "")
    intent_content = INTENT_PROMPT.format(message=user_input)
    result = await intent_llm.ainvoke([SystemMessage(content=intent_content)])
    intent = get_intent_from_result(result)

    if intent != "allowed":
        return Command(
            update={
                "error": f"User intent blocked. Intent identified: {intent}", 
                "error_node": "intent_guard_node",
                "retry_count": 0
            },
            goto="error_llm"
        )

    # Intent allowed, proceed to llm
    return Command(update={}, goto="llm")


def get_intent_from_result(result):
    content = result.content
    if isinstance(content, str):    
        return content.strip().lower()
    
    return content[0].strip().lower() or "out_of_scope"