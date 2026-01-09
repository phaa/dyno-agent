from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.db import get_db
from models.vehicle import Vehicle
from schemas.allocation import AllocateRequest, AllocationOut
from services.allocation_service import AllocationService
from services.validators import BusinessRules
from exceptions import ValidationError


router = APIRouter(prefix="/allocation", tags=["vehicles"])

@router.post("/allocate", tags=["vehicles"], response_model=AllocationOut)
async def allocate(req: AllocateRequest, db: AsyncSession = Depends(get_db)):
    # Validate business rules
    BusinessRules.validate_allocation_duration(req.start_date, req.end_date)

    allocation_service = AllocationService(db)
    
    return {"status": "in_progress"}
