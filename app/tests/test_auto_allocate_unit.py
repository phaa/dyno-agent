import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from datetime import date, timedelta

from services.allocation_service import AllocationService
from services.exceptions import VehicleAlreadyAllocatedError


@pytest.mark.asyncio
async def test_auto_allocate_requires_vehicle_id_or_vin():
    db = AsyncMock()
    svc = AllocationService(db)

    res = await svc.auto_allocate_vehicle_core(start_date=date.today(), days_to_complete=1)
    assert res["success"] is False
    assert "vehicle_id or vin" in res["message"]


@pytest.mark.asyncio
async def test_auto_allocate_vehicle_not_found():
    db = AsyncMock()
    # vehicle select returns result whose scalar_one_or_none() is None
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_res

    svc = AllocationService(db)
    res = await svc.auto_allocate_vehicle_core(start_date=date.today(), days_to_complete=1, vehicle_id=123)
    assert res["success"] is False
    assert "Vehicle not found" in res["message"]


@pytest.mark.asyncio
async def test_auto_allocate_success_primary_window():
    db = AsyncMock()

    # 1) vehicle select -> returns vehicle
    vehicle = SimpleNamespace(id=10, weight_lbs=3500, drive_type="AWD", vin="VIN123")
    mock_vehicle_res = MagicMock()
    mock_vehicle_res.scalar_one_or_none.return_value = vehicle

    # 2) existing_vehicle_alloc count -> return 0
    mock_count = MagicMock()
    mock_count.scalar.return_value = 0

    # Provide sequence of execute() returns used by the method prior to _try_window
    db.execute.side_effect = [mock_vehicle_res, mock_count]

    svc = AllocationService(db)
    svc._try_window = AsyncMock(return_value={"allocation_id": 99})

    res = await svc.auto_allocate_vehicle_core(start_date=date.today(), days_to_complete=2, vehicle_id=10)
    assert res["success"] is True
    assert "allocation" in res and res["allocation"]["allocation_id"] == 99


@pytest.mark.asyncio
async def test_auto_allocate_with_backup_shift():
    db = AsyncMock()

    vehicle = SimpleNamespace(id=11, weight_lbs=3000, drive_type="FWD", vin="VIN-B")
    mock_vehicle_res = MagicMock()
    mock_vehicle_res.scalar_one_or_none.return_value = vehicle
    mock_count = MagicMock()
    mock_count.scalar.return_value = 0
    db.execute.side_effect = [mock_vehicle_res, mock_count]

    svc = AllocationService(db)
    # First try window fails, second (backup) succeeds
    svc._try_window = AsyncMock(side_effect=[None, {"allocation_id": 77}])

    res = await svc.auto_allocate_vehicle_core(start_date=date.today(), days_to_complete=1, vehicle_id=11, backup=True, max_backup_days=2)
    assert res["success"] is True
    assert res["allocation"]["allocation_id"] == 77


@pytest.mark.asyncio
async def test_auto_allocate_vehicle_already_allocated_raises():
    db = AsyncMock()

    vehicle = SimpleNamespace(id=12, weight_lbs=3000, drive_type="RWD", vin="VIN-C")
    mock_vehicle_res = MagicMock()
    mock_vehicle_res.scalar_one_or_none.return_value = vehicle

    # existing_vehicle_alloc scalar() > 0 triggers exception
    mock_count = MagicMock()
    mock_count.scalar.return_value = 2

    db.execute.side_effect = [mock_vehicle_res, mock_count]

    svc = AllocationService(db)

    with pytest.raises(VehicleAlreadyAllocatedError):
        await svc.auto_allocate_vehicle_core(start_date=date.today(), days_to_complete=1, vehicle_id=12)
