from pydantic import BaseModel
from typing import Optional
from datetime import date

class AllocateRequest(BaseModel):
    vehicle_id: Optional[int] = None
    vin: Optional[str] = None
    weight_lbs: Optional[int] = None
    drive_type: Optional[str] = None  # '2WD' or 'AWD'
    test_type: str
    start_date: date
    end_date: date

class AllocationOut(BaseModel):
    allocation_id: int
    dyno_id: int
    dyno_name: str
    start_date: date
    end_date: date
    status: str