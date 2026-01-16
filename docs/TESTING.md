# Testing Guide — Dyno-Agent

This document describes how to run and reason about the project's automated test suite.

## Quick summary

- Test framework: `pytest` + `pytest-asyncio`
- Lightweight local execution: uses `AsyncMock` and fakes for heavy components (for example LangGraph and LangChain)
- Real PostgreSQL integration: recommended for tests that exercise array operators and row-level locking

## Running the tests

- Run the whole suite (fast in a dev environment):

```bash
pytest -q
```

- Run a single test file:

```bash
pytest -q path/to/test_file.py
```

- Run a specific test with verbose output:

```bash
pytest -q tests/test_agents_graph_deterministic.py -k test_graph_deterministic_tool_execution -s
```

## Fakes and isolation

- To avoid heavyweight dependencies in CI and local runs, many tests inject fakes for `langgraph` and agent modules (see `app/tests/*`).
- If you need to run tests that exercise real LangGraph or LangChain behavior, create a dedicated environment with pinned, compatible versions or run a separate CI job.

## Postgres for integration tests

- Some integration tests (concurrency checks, PostgreSQL array operators, row-level locking) require a real PostgreSQL instance.
- Recommended approach: use `docker-compose` to run a temporary `postgres` service for this subset of tests:

```bash
# Example (from repo root, if `docker-compose.yml` is configured):
docker-compose up -d db
pytest -q tests/integration --maxfail=1
docker-compose down
```

## Best practices

- Centralize shared fixtures in `app/tests/conftest.py` (fixtures for async clients, in-memory engines, and standardized test doubles are provided).
- Keep tests deterministic: mock LLMs and tool nodes with controlled responses whenever possible.
- For end-to-end scenarios with LLMs, prefer deterministic replayed responses (fixtures or recorded responses) instead of calling production LLMs.

## Shared fixtures

The repository provides common fixtures in `app/tests/conftest.py` to standardize fakes and doubles used across the suite:

- `mock_async_session`: a test-double that behaves like an `AsyncSession`:
        - `begin()` returns an async context manager that calls `commit()` on exit
        - `add` is a `MagicMock` (synchronous)
        - `flush`, `commit`, `refresh`, and `execute` are `AsyncMock`
        - Use it by declaring the fixture in your test signature: `async def test_x(mock_async_session):`

- `install_langgraph_fakes`: a fixture that injects minimal `langgraph` fakes (StateGraph, checkpointer, prebuilt ToolNode). Use it as a fixture to ensure isolation:
        - Example: `def test_graph(install_langgraph_fakes):` — fake modules are removed after the test.

- `install_agents_nodes`: a helper to dynamically inject a fake `agents.nodes` module with controlled functions:
        - Example:

```python
def test_my_graph(install_langgraph_fakes, install_agents_nodes):
    fake = install_agents_nodes({
        'llm_node': lambda s: {'messages': ['ok']},
        'tool_node': lambda s: {'tools': {}}
    })
    
    import importlib
    importlib.reload(importlib.import_module('agents.graph'))
    # ... perform assertions
```

These fixtures reduce duplication and help keep agent tests deterministic.

## Testing Retry System

The retry system (`core/retry.py`) is comprehensively tested to ensure production-grade resilience:

### Retry Decorator Tests (`test_retry_system.py`)

Tests for the `@async_retry` decorator cover:

- **Basic Functionality**:
  - Success on first attempt (no retry)
  - Automatic retry on transient failures
  - Exception classification (retryable vs non-retryable)
  - Immediate failure on non-retryable errors
  - Exponential backoff timing validation
  - Backoff capping at `max_delay`

- **Exception Handling**:
  - `RetryableError`: Triggers retry with backoff
  - `NonRetryableError`: Fails immediately without retry
  - `SQLAlchemyError`: Automatically treated as retryable
  - `asyncio.TimeoutError`: Automatically treated as retryable
  - Unknown exceptions: Treated as retryable with logging

- **Observability**:
  - Retry attempts are logged as warnings
  - Exhausted retries logged as errors
  - Exception chains preserved for debugging

Run retry decorator tests:

```bash
pytest -q tests/test_retry_system.py
```

### Service Integration Tests (`test_conversation_service_retry.py`)

Tests for retry behavior in `ConversationService`:

- **Database Retry**:
  - Retry on connection timeouts and pool exhaustion
  - Success after transient failures
  - Immediate failure on validation errors (non-retryable)
  - Rollback on all retry attempts

- **Authorization Tests**:
  - User not found → immediate failure (non-retryable)
  - Access denied → immediate failure (non-retryable)

- **Persistence Tests**:
  - Message save with automatic retry
  - Conversation creation and retrieval
  - Retry exhaustion with appropriate error

- **Error Handling**:
  - Error messages preserved through retries
  - Logging of transient failures
  - Rollback on database errors

Run service retry tests:

```bash
pytest -q tests/test_conversation_service_retry.py
```

### Retry Configuration Testing

When testing your own services with `@async_retry`, configure the decorator based on use case:

```python
# Database operations - tolerant to transient failures
@async_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
async def get_or_create_conversation(self, user_email: str):
    try:
        return await self.db.get(User, user_email)
    except SQLAlchemyError as e:
        raise RetryableError(f"Database error: {str(e)}") from e
    except ValueError as e:
        raise NonRetryableError(f"Validation error: {str(e)}") from e

# Critical path - fail fast
@async_retry(max_attempts=2, base_delay=0.1, max_delay=1.0)
async def authenticate_user(self, token: str):
    try:
        return await verify_token(token)
    except AuthError as e:
        raise NonRetryableError(str(e)) from e
```

### Testing Retry Behavior in Custom Code

When testing services with retry decorators, use mocking to simulate transient failures:

```python
@pytest.mark.asyncio
async def test_service_retries_on_db_timeout(mock_async_session):
    db = mock_async_session
    user = MagicMock(email="user@test.com")

    # First call raises error, second succeeds
    db.get.side_effect = [
        SQLAlchemyError("connection timeout"),
        user
    ]

    service = MyService(db)
    result = await service.get_or_create(user_email="user@test.com")

    assert result is not None
    assert db.get.call_count == 2  # Called twice (first failed, second succeeded)
```



## CI

- The repository includes a basic CI workflow at `.github/workflows/ci.yml`. To run the full test suite in CI consider:
        - adding a job that provisions PostgreSQL as a service/container for Postgres-specific integration tests;
        - separating LangGraph/langchain-dependent tests into a job that uses a pinned, compatible environment.

## Known limitations

- The suite currently relies on fakes for LangGraph; deeper graph integration tests will require a pinned environment or a dedicated CI job.

If something goes wrong when running tests locally, include the `pytest -q -r a` output and we will help diagnose.

