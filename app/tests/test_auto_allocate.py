import pytest
from datetime import date
from agents.tools import auto_allocate_vehicle
import asyncio

@pytest.mark.asyncio
async def test_auto_allocate_happy_path(async_db_setup):
    # async_db_setup fixture deve criar DB e popular dynos/vehicles
    res = await auto_allocate_vehicle(vehicle_id=1, start_date=date(2025,9,20), backup=False)
    assert res["success"] is True
    assert "allocation" in res
