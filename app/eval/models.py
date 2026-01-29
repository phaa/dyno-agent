
from dataclasses import dataclass

# Data Models
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
