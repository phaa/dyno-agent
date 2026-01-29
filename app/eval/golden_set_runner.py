import json
import logging
from pathlib import Path
from typing import Any
from app.eval.agent_executor import AgentExecutor
from app.eval.decision_validator import DecisionValidator
from app.eval.qa_validator import QAValidator
from .models import ValidationResult

logger = logging.getLogger(__name__)

GOLDEN_SETS_DIR = Path(__file__).parent / "golden_sets"
DECISIONS_FILE = GOLDEN_SETS_DIR / "agent_decisions_v1.0.0.json"
QA_FILE = GOLDEN_SETS_DIR / "agent_qa_v1.0.0.json"

# Golden Set Loader


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
        
        decision_cases = self._load_golden_sets(DECISIONS_FILE)
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
        
        qa_cases = self._load_golden_sets(QA_FILE)
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

    def _load_golden_sets(self, file_path: Path) -> list[dict[str, Any]]:
        """Load golden set test cases from JSON file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Golden set file not found: {file_path}")
        
        with open(file_path, "r") as f:
            return json.load(f)