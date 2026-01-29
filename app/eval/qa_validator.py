from typing import Any

from .models import ValidationResult, ExecutionContext

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

