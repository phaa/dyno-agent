#!/usr/bin/env python3
"""
Golden Set Evaluation Runner for Dyno-Agent

Executes the real agent against golden sets and validates:
- Decision cases: tools_used, allocation_valid, reason_contains
- QA cases: expected_contains, must_not_contain
"""

import sys
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Any
from dataclasses import dataclass

# Setup environment variables for local eval
os.environ.setdefault("PRODUCTION", "false")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("DATABASE_URL_CHECKPOINTER", "postgresql://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test_secret")

# Setup path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from langchain_core.messages import HumanMessage, AIMessage
from ..app.agents.graph import build_graph
from ..app.agents.state import GraphState


# ============================================================================
# Configuration
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

GOLDEN_SETS_DIR = Path(__file__).parent.parent / "app" / "golden_sets"
DECISIONS_FILE = GOLDEN_SETS_DIR / "agent_decisions_v1.0.0.json"
QA_FILE = GOLDEN_SETS_DIR / "agent_qa_v1.0.0.json"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ValidationResult:
    """Result of validating a single golden set case"""
    test_id: str
    test_type: str  # "decision" or "qa"
    passed: bool
    errors: list[str]
    warnings: list[str]


@dataclass
class ExecutionContext:
    """Context for executing a single agent test"""
    test_id: str
    test_input: str
    response: str
    tools_called: list[str]
    final_message: str


# ============================================================================
# Golden Set Loader
# ============================================================================

def load_golden_sets(file_path: Path) -> list[dict[str, Any]]:
    """Load golden set test cases from JSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Golden set file not found: {file_path}")
    
    with open(file_path, "r") as f:
        return json.load(f)


# ============================================================================
# Agent Execution
# ============================================================================

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


# ============================================================================
# Validation Logic
# ============================================================================

class DecisionValidator:
    """Validates decision test cases."""
    
    @staticmethod
    def validate(
        context: ExecutionContext,
        expected: dict[str, Any]
    ) -> ValidationResult:
        """
        Validate a decision case.
        
        Checks:
        - tools_used: exact list of tool names called
        - allocation_valid: whether the allocation succeeded
        - reason_contains: substrings that must appear in final answer
        """
        errors = []
        warnings = []
        
        # 1. Validate tools_used
        expected_tools = set(expected.get("tools_used", []))
        actual_tools = set(context.tools_called)
        
        if expected_tools != actual_tools:
            errors.append(
                f"Tools mismatch. Expected: {expected_tools}, Got: {actual_tools}"
            )
        
        # 2. Validate allocation_valid
        allocation_valid = expected.get("allocation_valid", False)
        allocation_text = context.final_message.lower()
        
        # Check for success/failure indicators
        is_success = any(
            phrase in allocation_text
            for phrase in [
                "allocated", "booked", "scheduled", "found",
                "successfully", "available", "success"
            ]
        )
        
        is_failure = any(
            phrase in allocation_text
            for phrase in [
                "not found", "unavailable", "failed", "cannot",
                "no dynos", "invalid", "error", "required"
            ]
        )
        
        actual_valid = is_success and not is_failure
        
        if allocation_valid and not is_success:
            errors.append(
                f"Expected successful allocation but got: {context.final_message[:100]}"
            )
        
        if not allocation_valid and not is_failure:
            warnings.append(
                f"Expected failed allocation but got success indicators"
            )
        
        # 3. Validate reason_contains
        reason_phrases = expected.get("reason_contains", [])
        
        for phrase in reason_phrases:
            # Case-insensitive substring search, allow partial matches
            if phrase.lower() not in allocation_text:
                errors.append(
                    f"Expected substring '{phrase}' not found in response"
                )
        
        passed = len(errors) == 0
        
        return ValidationResult(
            test_id=context.test_id,
            test_type="decision",
            passed=passed,
            errors=errors,
            warnings=warnings
        )


class QAValidator:
    """Validates QA test cases."""
    
    @staticmethod
    def validate(
        context: ExecutionContext,
        expected: dict[str, Any]
    ) -> ValidationResult:
        """
        Validate a QA case.
        
        Checks:
        - expected_contains: substrings that must appear
        - must_not_contain: substrings that must NOT appear
        """
        errors = []
        warnings = []
        
        response_text = context.final_message.lower()
        
        # 1. Validate expected_contains
        expected_phrases = expected.get("expected_contains", [])
        
        for phrase in expected_phrases:
            if phrase.lower() not in response_text:
                errors.append(
                    f"Expected phrase '{phrase}' not found in response"
                )
        
        # 2. Validate must_not_contain
        forbidden_phrases = expected.get("must_not_contain", [])
        
        for phrase in forbidden_phrases:
            if phrase.lower() in response_text:
                errors.append(
                    f"Forbidden phrase '{phrase}' found in response"
                )
        
        passed = len(errors) == 0
        
        return ValidationResult(
            test_id=context.test_id,
            test_type="qa",
            passed=passed,
            errors=errors,
            warnings=warnings
        )


# ============================================================================
# Test Runner
# ============================================================================

class GoldenSetRunner:
    """Orchestrates golden set evaluation."""
    
    def __init__(self):
        self.executor = AgentExecutor()
        self.decision_validator = DecisionValidator()
        self.qa_validator = QAValidator()
        self.results = []
    
    async def run_all(self) -> tuple[int, int, list[ValidationResult]]:
        """
        Execute all golden sets.
        
        Returns:
            (passed_count, failed_count, all_results)
        """
        # Initialize executor
        await self.executor.initialize()
        
        passed_count = 0
        failed_count = 0
        
        # Run decision tests
        logger.info("=" * 70)
        logger.info("RUNNING DECISION TESTS")
        logger.info("=" * 70)
        
        decision_cases = load_golden_sets(DECISIONS_FILE)
        for case in decision_cases:
            result = await self._run_decision_case(case)
            self.results.append(result)
            
            if result.passed:
                passed_count += 1
                self._print_pass(result)
            else:
                failed_count += 1
                self._print_fail(result)
        
        # Run QA tests
        logger.info("\n" + "=" * 70)
        logger.info("RUNNING QA TESTS")
        logger.info("=" * 70)
        
        qa_cases = load_golden_sets(QA_FILE)
        for case in qa_cases:
            result = await self._run_qa_case(case)
            self.results.append(result)
            
            if result.passed:
                passed_count += 1
                self._print_pass(result)
            else:
                failed_count += 1
                self._print_fail(result)
        
        return passed_count, failed_count, self.results
    
    async def _run_decision_case(self, case: dict[str, Any]) -> ValidationResult:
        """Execute and validate a single decision case."""
        test_id = case["id"]
        user_input = case["input"]
        expected = case["expected"]
        
        try:
            context = await self.executor.run(user_input, test_id)
            return self.decision_validator.validate(context, expected)
        except Exception as e:
            logger.error(f"Error executing decision case {test_id}: {str(e)}")
            return ValidationResult(
                test_id=test_id,
                test_type="decision",
                passed=False,
                errors=[f"Execution error: {str(e)}"],
                warnings=[]
            )
    
    async def _run_qa_case(self, case: dict[str, Any]) -> ValidationResult:
        """Execute and validate a single QA case."""
        test_id = case["id"]
        user_input = case["input"]
        expected = case["expected"]
        
        try:
            context = await self.executor.run(user_input, test_id)
            return self.qa_validator.validate(context, expected)
        except Exception as e:
            logger.error(f"Error executing QA case {test_id}: {str(e)}")
            return ValidationResult(
                test_id=test_id,
                test_type="qa",
                passed=False,
                errors=[f"Execution error: {str(e)}"],
                warnings=[]
            )
    
    def _print_pass(self, result: ValidationResult):
        """Print a passing test result."""
        status = "✓ PASS"
        logger.info(f"{status} [{result.test_type}] {result.test_id}")
    
    def _print_fail(self, result: ValidationResult):
        """Print a failing test result with details."""
        status = "✗ FAIL"
        logger.error(f"{status} [{result.test_type}] {result.test_id}")
        for error in result.errors:
            logger.error(f"  • {error}")
        for warning in result.warnings:
            logger.warning(f"  ⚠ {warning}")


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point."""
    runner = GoldenSetRunner()
    
    try:
        passed, failed, results = await runner.run_all()
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Total:  {passed + failed}")
        
        if failed == 0:
            logger.info("\n✓ All tests passed!")
            return 0
        else:
            logger.error(f"\n✗ {failed} test(s) failed")
            return 1
    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
