import logging
from dataclasses import dataclass
from langchain_core.messages import AIMessage
from agents.graph import build_graph
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from .models import ExecutionContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


@dataclass
class MockContext:
    """Mock runtime context."""
    db: AsyncSession

# Agent Execution
class AgentExecutor:
    """Executes the real agent without mocks."""
    
    def __init__(self):
        self.graph = None
    
    async def initialize(self):
        """Initialize the graph (without checkpointer for local eval)."""
        try:
            self.graph = await build_graph(checkpointer=None)
        except Exception as e:
            logger.warning(f"Graph initialization warning (may fail gracefully): {e}")
            # Continue - we'll try to execute anyway
    
    async def run(self, user_input: str, test_id: str) -> ExecutionContext:
        """
        Execute the agent with the given input.
        
        Returns:
            ExecutionContext with response, tools called, and final message
        """
        if self.graph is None:
            # Try to initialize if not already done
            await self.initialize()
            if self.graph is None:
                logger.error(f"[{test_id}] Graph is still None after initialization")
                return ExecutionContext(
                    test_id=test_id,
                    test_input=user_input,
                    response="Graph initialization failed",
                    tools_called=[],
                    final_message="Graph initialization failed"
                )
        
        logger.info(f"[{test_id}] Executing agent with input: {user_input[:80]}...")
        
        # Build input state 
        inputs = {
            "user_input": user_input,
            "user_name": "TestUser",
            "conversation_id": f"eval_{test_id}",
        }

        context = MockContext(db=get_db())

        config = {
            "configurable": {
                "thread_id": f"eval_{test_id}"
            }
        }
        
        tools_called = []
        final_message = ""
        response_text = ""
        
        try:
            # Try to invoke the graph
            result = await self.graph.ainvoke(
                inputs,
                config=config,
                context=context
            )
            
            # Extract messages from result
            # Handle different result types (dict or direct message list)
            if isinstance(result, dict):
                messages = result.get("messages", [])
            elif isinstance(result, list):
                messages = result
            else:
                messages = []
                
            if messages:
                last_msg = messages[-1]
                if isinstance(last_msg, AIMessage):
                    response_text = last_msg.content or ""
                    # Extract tool calls if present
                    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                        tools_called = []
                        for call in last_msg.tool_calls:
                            # tool_calls items are dicts with 'name' key
                            if isinstance(call, dict) and "name" in call:
                                tool_name = call.get("name", "")
                                if tool_name:
                                    tools_called.append(tool_name)
                        tools_called = [t for t in tools_called if t]  # Filter out empty strings
        
        except Exception as e:
            # Capture error message
            error_msg = str(e)
            logger.warning(f"[{test_id}] Graph execution error: {error_msg[:200]}")
            response_text = error_msg
        
        # Extract final message from response
        final_message = response_text
        
        return ExecutionContext(
            test_id=test_id,
            test_input=user_input,
            response=response_text,
            tools_called=tools_called,
            final_message=final_message
        )

