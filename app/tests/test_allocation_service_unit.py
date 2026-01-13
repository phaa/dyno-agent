import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from datetime import date

from services.allocation_service import AllocationService
from services.exceptions import InvalidQueryError, AllocationDomainError


@pytest.mark.asyncio
async def test_get_datetime_now_core_returns_datetime():
    db = AsyncMock()
    svc = AllocationService(db)

    # `track_performance` decorator wraps async functions; access the original
    # synchronous implementation via __wrapped__ to avoid awaiting a non-coroutine
    now = svc.get_datetime_now_core.__wrapped__(svc)
    assert hasattr(now, 'year') and hasattr(now, 'month') and hasattr(now, 'day')


def test_handle_exception_core_handles_domain_error():
    db = AsyncMock()
    svc = AllocationService(db)

    e = AllocationDomainError("boom")
    out = svc.handle_exception_core(e)

    assert out["success"] is False
    assert out["error_type"] == e.__class__.__name__
    assert "boom" in out["message"]


@pytest.mark.asyncio
async def test_query_database_core_rejects_non_select():
    db = AsyncMock()
    svc = AllocationService(db)

    with pytest.raises(InvalidQueryError):
        await svc.query_database_core("DROP TABLE users;")


@pytest.mark.asyncio
async def test_query_database_core_empty_and_success():
    db = AsyncMock()
    svc = AllocationService(db)

    # First call for setting timeout, second to execute query
    mock_result_empty = MagicMock()
    mock_result_empty.fetchall.return_value = []
    db.execute.side_effect = [None, mock_result_empty]

    res = await svc.query_database_core("SELECT 1 as a")
    assert res == []

    # Now return some rows
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [(1,)]
    mock_result.keys.return_value = ["a"]
    db.execute.side_effect = [None, mock_result]

    res = await svc.query_database_core("SELECT 1 as a")
    assert isinstance(res, list)
    assert res == [{"a": 1}]


@pytest.mark.asyncio
async def test_completed_tests_count_core():
    db = AsyncMock()
    svc = AllocationService(db)

    # completed_tests_count_core -> scalar()
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 42
    db.execute.return_value = mock_count_result
    count = await svc.completed_tests_count_core()
    assert count == 42
