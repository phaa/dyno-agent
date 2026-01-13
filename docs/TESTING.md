# Testing Guide — Dyno-Agent

        This document describes how to run and reason about the project's automated test suite.

        ## Quick summary

        - Test framework: `pytest` + `pytest-asyncio`
        - Lightweight local execution: uses `AsyncMock` and fakes for heavy components (for example LangGraph and LangChain)
        - Real PostgreSQL integration: recommended for tests that exercise array operators and row-level locking
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

## CI

- The repository includes a basic CI workflow at `.github/workflows/ci.yml`. To run the full test suite in CI consider:
        - adding a job that provisions PostgreSQL as a service/container for Postgres-specific integration tests;
        - separating LangGraph/langchain-dependent tests into a job that uses a pinned, compatible environment.

## Known limitations

- The suite currently relies on fakes for LangGraph; deeper graph integration tests will require a pinned environment or a dedicated CI job.

If something goes wrong when running tests locally, include the `pytest -q -r a` output and we will help diagnose.

        ## Running the tests
