from fastapi import FastAPI, Depends, HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from models.vehicle import Vehicle

from schemas.allocation import AllocateRequest, AllocationOut
from schemas.chat import ChatRequest

from services.allocator import find_available_dynos, allocate_dyno_transactional

from agents.agent import agent_executor


import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("langchain").setLevel(logging.DEBUG)

app = FastAPI(title="Dyno Allocator API")


@app.get("/hello")
def hello():
    return {"message": "Hello, World!"}

@app.post("/chat")
def chat(request: ChatRequest):
    result = agent_executor.invoke({"input": request.message})
    return {"response": result["output"]}

@app.post("/allocate", response_model=AllocationOut)
async def allocate(req: AllocateRequest, db: AsyncSession = Depends(get_db)):
    # 1) Resolve vehicle: must have weight_lbs and drive_type (either via vehicle_id or payload)
    if req.vehicle_id:
        veh = (await db.execute(select(Vehicle).where(Vehicle.id == req.vehicle_id))).scalar_one_or_none()
        if not veh:
            raise HTTPException(status_code=404, detail="Vehicle not found.")
        weight = veh.weight_lbs
        drive = veh.drive_type
        vehicle_id = veh.id
    else:
        if not (req.weight_lbs and req.drive_type):
            raise HTTPException(status_code=400, detail="Vehicle data missing: provide vehicle_id or weight_lbs+drive_type.")
        # Optional: upsert vehicle if vin provided
        vehicle_id = None
        weight = req.weight_lbs
        drive = req.drive_type

    # 2) find candidates
    candidates = await find_available_dynos(db, req.start_date, req.end_date, weight, drive, req.test_type)
    if not candidates:
        raise HTTPException(status_code=404, detail="No available dynos match constraints.")

    # 3) choose one (heuristic: first candidate)
    chosen = candidates[0]
    # If vehicle_id is None, create vehicle row to record allocation
    if vehicle_id is None:
        newv = Vehicle(vin=req.vin, weight_lbs=req.weight_lbs, drive_type=req.drive_type)
        db.add(newv)
        await db.flush()  # get id
        vehicle_id = newv.id

    # 4) transactional allocation
    try:
        alloc = await allocate_dyno_transactional(db, chosen.id, vehicle_id, req.test_type, req.start_date, req.end_date)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))

    return AllocationOut(
        allocation_id=alloc.id,
        dyno_id=chosen.id,
        dyno_name=chosen.name,
        start_date=alloc.start_date,
        end_date=alloc.end_date,
        status=alloc.status,
    )