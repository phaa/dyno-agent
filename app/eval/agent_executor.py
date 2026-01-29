import logging
from langchain_core.messages import HumanMessage, AIMessage
from agents.graph import build_graph
from .models import ExecutionContext

logger = logging.getLogger(__name__)

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
            "messages": [HumanMessage(content=user_input)],
            "user_name": "TestUser",
            "conversation_id": f"eval_{test_id}",
        }
        
        config = {
            "configurable": {
                "thread_id": f"eval_{test_id}"
            }
        }
        
        # Mock context for tools that need runtime access
        class MockDB:
            """Mock database for local evaluation."""
            async def execute(self, *args, **kwargs):
                raise RuntimeError("Database not available in local eval mode")
        
        class MockContext:
            """Mock runtime context."""
            db = MockDB()
        
        tools_called = []
        final_message = ""
        response_text = ""
        
        try:
            # Try to invoke the graph
            result = await self.graph.ainvoke(
                inputs,
                config=config,
                context=MockContext()
            )
            
            # Extract messages from result
            messages = result.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if isinstance(last_msg, AIMessage):
                    response_text = last_msg.content or ""
                    # Extract tool calls if present
                    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                        tools_called = [
                            call.get("name", call.get("function", {}).get("name", ""))
                            for call in last_msg.tool_calls
                            if call.get("name") or (call.get("function") and call.get("function", {}).get("name"))
                        ]
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

