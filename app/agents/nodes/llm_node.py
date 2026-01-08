from langchain_core.messages import SystemMessage
from langgraph.config import get_stream_writer
from ..state import GraphState
from .config import (
    SYSTEM, 
    CONVERSATION_SUMMARY_PROMPT, 
    INITIAL_SUMMARY, 
    get_model_with_tools
)

async def llm_node(state: GraphState):
    """Main reasoning node with tool bindings."""
    writer = get_stream_writer()
    writer("🤖 Thinking...")
    
    summary = state.get("summary", INITIAL_SUMMARY)
    user_name = state.get("user_name")
    schema = state.get("schema")

    msgs = [
        SystemMessage(
            content=SYSTEM.format(schema=schema, user_name=user_name)
        ),
        SystemMessage(
            content=CONVERSATION_SUMMARY_PROMPT.format(
                decisions="\n".join(summary["decisions"]),
                constraints="\n".join(summary["constraints"]),
                open_tasks="\n".join(summary["open_tasks"]),
                context=summary["context"]
            )
        )
    ]
    
    msgs.extend(state.get("messages", []))

    model_with_tools = get_model_with_tools()
    ai = await model_with_tools.ainvoke(msgs)

    return {"messages": [ai]}