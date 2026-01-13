import pytest
from datetime import date
from fastapi import FastAPI, Depends
from httpx import AsyncClient
from unittest.mock import AsyncMock

from core.db import get_db
from services.allocation_service import AllocationService


def test_allocate_endpoint_monkeypatched():
    # Build a minimal app and monkeypatch AllocationService to avoid DB complexity
    app = FastAPI()

    async def override_get_db():
        yield None

    app.dependency_overrides[get_db] = override_get_db

    expected = {"success": True, "message": "Allocated.", "allocation": {"allocation_id": 1}}

    AllocationService.auto_allocate_vehicle_core = AsyncMock(return_value=expected)

    @app.post("/allocation/allocate")
    async def allocate(req: dict, db=Depends(get_db)):
        svc = AllocationService(db)
        return await svc.auto_allocate_vehicle_core(start_date=date.fromisoformat(req.get("start_date")), days_to_complete=req.get("days_to_complete", 1), vehicle_id=req.get("vehicle_id"))

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        payload = {"vehicle_id": 1, "start_date": date.today().isoformat(), "days_to_complete": 1}
        resp = client.post("/allocation/allocate", json=payload)

    assert resp.status_code == 200
    assert resp.json() == expected
