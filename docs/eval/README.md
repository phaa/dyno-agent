# Golden Set Evaluation Runner

Local evaluation runner for the Dyno-Agent LangGraph agent against golden sets.

## Overview

`run_agent_golden.py` executes the **real agent** (no mocks) against two types of golden sets:

- **Decision Cases** (`agent_decisions_v1.0.0.json`) - Allocation and tool use validation
- **QA Cases** (`agent_qa_v1.0.0.json`) - Knowledge and reasoning validation

## Golden Set Format

### Decision Cases

Test that the agent correctly:
- Calls expected tools
- Produces valid/invalid allocations
- Includes required reasoning in responses

```json
{
  "id": "alloc_awd_brake_backup_ok",
  "input": "Allocate vehicle 42 (AWD, 4800 lbs) for a brake test...",
  "expected": {
    "tools_used": ["auto_allocate_vehicle"],
    "allocation_valid": true,
    "reason_contains": [
      "Allocated in requested window",
      "Allocated with backup shift"
    ]
  }
}
```

### QA Cases

Test that the agent provides accurate knowledge:
- Must include expected phrases
- Must not include forbidden phrases

```json
{
  "id": "compatibility_basis",
  "input": "What determines whether a dyno can handle a vehicle?",
  "expected_contains": [
    "supported_weight_classes",
    "supported_drives"
  ],
  "must_not_contain": ["guess", "hallucinate"]
}
```

## Validation Rules

### Decision Validation

1. **tools_used** - Exact match of tool names called
2. **allocation_valid** - True if response contains success indicators, False if failure indicators
3. **reason_contains** - All substrings must appear (case-insensitive) in final response

### QA Validation

1. **expected_contains** - All phrases must appear (case-insensitive) in response
2. **must_not_contain** - No forbidden phrases should appear

## Design Principles

- **No Assertions on Exact Text** - Uses substring matching for flexibility
- **No Hardcoded IDs** - Works with any vehicle/dyno IDs in data
- **Fail Fast** - Clear error messages per case
- **Simple and Readable** - ~400 lines, easy to extend
- **Real Agent Execution** - Uses actual agent code, not mocks

## Running Locally

### Prerequisites

```bash
cd /home/pedro/projects/ai-engineering/dyno-agent

# Install dependencies if needed
pip install -r requirements-dev.txt

# Ensure .env is configured (or database is available)
# For local eval without DB, use mock context
```

### Execute

```bash
cd eval
python run_agent_golden.py
```

### Output

```
======================================================================
RUNNING DECISION TESTS
======================================================================
✓ PASS [decision] alloc_awd_brake_backup_ok
✓ PASS [decision] alloc_missing_vehicle_identifier
✗ FAIL [decision] alloc_vehicle_not_found
  • Expected substring 'Vehicle not found' not found in response

======================================================================
RUNNING QA TESTS
======================================================================
✓ PASS [qa] compatibility_basis
...

======================================================================
SUMMARY
======================================================================
Passed: 28
Failed: 2
Total:  30

✗ 2 test(s) failed
```

### Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

## Implementation Details

### ExecutionContext

Captures what the agent did:
- `test_id` - Case identifier
- `test_input` - User prompt
- `response` - Full LLM response
- `tools_called` - List of tool names invoked
- `final_message` - Extracted answer text

### Validators

**DecisionValidator**
- Checks tools_used matches expected
- Detects allocation success/failure from response keywords
- Verifies all reason_contains substrings present

**QAValidator**
- Checks expected_contains substrings present
- Checks must_not_contain substrings absent

## Extending

### Add New Test Cases

Edit golden set files:
```json
{
  "id": "unique_id",
  "input": "Your test prompt here",
  "expected": { ... }
}
```

### Modify Validation Rules

Edit `DecisionValidator.validate()` or `QAValidator.validate()`:
- Adjust success/failure keyword detection
- Change substring matching behavior
- Add new validation fields

### Integration with CI/CD

```bash
# In Makefile or CI pipeline
test-golden:
	python eval/run_agent_golden.py
	@test $$? -eq 0
```

## Limitations

1. **Database Context** - Local eval may fail on tools requiring actual DB queries
   - Mock context provided, but real allocation operations won't work
   - Tests still validate agent reasoning and tool selection

2. **Streaming** - Uses direct `ainvoke()` rather than streaming
   - Simpler for testing, captures full final response

3. **Tool Execution** - Tools don't actually execute without DB
   - Agent still selects correct tools (validates routing)
   - May see errors from tool invocation (captured in response)

