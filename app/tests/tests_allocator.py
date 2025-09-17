import pytest
from httpx import AsyncClient
from ..models import Dyno, Vehicle

@pytest.mark.asyncio
async def test_allocate_happy_path(async_db_session, async_client: AsyncClient):
    db = async_db_session
    # create dyno
    dyno = Dyno(name="dyno-A", max_weight_lbs=15000, supported_drive=["any"], supported_test_types=["brake"], enabled=True)
    db.add(dyno)
    veh = Vehicle(vin="VIN123", weight_lbs=12000, drive_type="2WD")
    db.add(veh)
    await db.commit()

    payload = {
        "vehicle_id": veh.id,
        "test_type": "brake",
        "start_date": "2025-09-20",
        "end_date": "2025-09-21"
    }
    resp = await async_client.post("/allocate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["dyno_id"] == dyno.id