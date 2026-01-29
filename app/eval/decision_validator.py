from typing import Any

from .models import ValidationResult, ExecutionContext

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

