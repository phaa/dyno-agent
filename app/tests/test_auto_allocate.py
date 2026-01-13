import pytest
from unittest.mock import AsyncMock, MagicMock 
from datetime import date
from fastapi.testclient import TestClient

from services.allocation_service import AllocationService
from core.db import AsyncSessionLocal

# Mock data and functions
class MockVehicle:
    """Simulates a vehicle object"""
    id = 1
    vin = "ABC12345"
    weight_lbs = 5000
    drive_type = "AWD"
    preferred_test_type = "brake"
    days_to_complete = 2

class MockDyno:
    """Simulates a dyno object"""
    id = 101
    name = "Dyno-AWD-01"
    enabled = True

@pytest.mark.asyncio # Force to use asyncio event loop
async def test_auto_allocate_happy_path(mock_async_session):

    # Mocked db session (use shared fixture)
    mock_session = mock_async_session
    mock_dyno = MockDyno()

    # Provide an async context manager for `begin()` since AsyncMock returns a coroutine
    class DummyAsyncCtx:
        def __init__(self, session):
            self.session = session
        async def __aenter__(self):
            return None
        async def __aexit__(self, exc_type, exc, tb):
            # commit on successful exit to mimic AsyncSession.begin() behavior
            await self.session.commit()
            return False

    # Ensure begin() returns an async context manager directly (not a coroutine)
    mock_session.begin = lambda: DummyAsyncCtx(mock_session)

    # `add` should be synchronous on SQLAlchemy session; use MagicMock so tests can inspect call_args
    from unittest.mock import MagicMock as _MagicMock
    mock_session.add = _MagicMock()

    # Configure the mock to return a vehicle
    mock_vehicle_result = MagicMock()
    mock_vehicle_result.scalar_one_or_none.return_value = MockVehicle()

    # Configure the mock to return available dynos
    mock_dyno_candidates_result = MagicMock()
    mock_dyno_candidates_result.scalars.return_value.all.return_value = [
        mock_dyno
    ]

    # Configure the mock for Lock Dyno (select(...).with_for_update())
    mock_dyno_lock_result = MagicMock()
    mock_dyno_lock_result.scalar_one_or_none.return_value = MockDyno()

    # Configure the mock for Conflict Check (must be None for success)
    mock_confilict_result = MagicMock()
    mock_confilict_result.scalar_one_or_none.return_value = None

    # Configure the mock for existing vehicle allocations count (must be 0 for success)
    mock_existing_vehicle_alloc_result = MagicMock()
    mock_existing_vehicle_alloc_result.scalar.return_value = 0
    
    # Configure the mock for existing allocations on dyno after lock (must be 0)
    mock_post_lock_existing_alloc_result = MagicMock()
    mock_post_lock_existing_alloc_result.scalar.return_value = 0

    # The sequence of executions must be the seme as in AllocationService.auto_allocate_vehicle_core
    mock_session.execute.side_effect = [
        mock_vehicle_result,
        mock_existing_vehicle_alloc_result,
        mock_dyno_candidates_result,
        mock_dyno_lock_result,
        mock_post_lock_existing_alloc_result,
        mock_confilict_result,
    ]

    # Mock refresh to simulate the allocation ID creation
    # In this case I prefer to use setattr()
    allocation_id = 999
    # When flush is called, set the allocation id on the object previously added
    def _flush_side_effect():
        alloc_obj = mock_session.add.call_args[0][0]
        setattr(alloc_obj, "id", allocation_id)

    mock_session.flush.side_effect = _flush_side_effect

    service = AllocationService(db=mock_session)

    res = await service.auto_allocate_vehicle_core(
        start_date=date(2025, 9, 20),
        days_to_complete=MockVehicle.days_to_complete,
        vehicle_id=1,
        backup=False
    )

    # Assetions
    assert res["success"] is True
    assert "Allocated in requested window." in res["message"]
    assert res["allocation"]["dyno_id"] == mock_dyno.id
    assert res["allocation"]["allocation_id"] == allocation_id

    # Assert wether the expected SQL commands were called
    assert mock_session.execute.call_count == 5
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.flush.assert_called_once()
