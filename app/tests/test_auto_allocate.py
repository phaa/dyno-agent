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
async def test_auto_allocate_happy_path():

    # Mocked db session
    mock_session = AsyncMock()
    mock_dyno = MockDyno()

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

    # The sequence of executions must be the seme as in AllocationService.auto_allocate_vehicle_core
    mock_session.execute.side_effect = [
        mock_vehicle_result,
        mock_dyno_candidates_result,
        mock_dyno_lock_result,
        mock_confilict_result,
    ]

    # Mock refresh to simulate the allocation ID creation
    # In this case I prefer to use setattr()
    allocation_id = 999
    mock_session.refresh.side_effect = lambda allocation: setattr(allocation, "id", allocation_id)

    service = AllocationService(db=mock_session)

    res = await service.auto_allocate_vehicle_core(
        vehicle_id=1, 
        start_date=date(2025, 9, 20), 
        backup=False
    )

    # Assetions
    assert res["success"] is True
    assert "Allocated in requested window." in res["message"]
    assert res["allocation"]["dyno_id"] == mock_dyno.id
    assert res["allocation"]["allocation_id"] == allocation_id

    # Assert wether the expected SQL commands were called
    assert mock_session.execute.call_count == 4
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()
