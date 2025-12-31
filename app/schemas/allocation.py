from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, timedelta

class AllocateRequest(BaseModel):
    vehicle_id: Optional[int] = None
    vin: Optional[str] = None
    weight_lbs: Optional[int] = Field(None, gt=0, le=80000, description="Weight in pounds")
    drive_type: Optional[str] = Field(None, pattern="^(2WD|AWD)$")  # '2WD' or 'AWD'
    test_type: str
    start_date: date = Field(..., description="Test start date")
    end_date: date = Field(..., description="Test end date")
    
    @field_validator('end_date')
    def end_after_start(cls, v, info):
        start_date = info.data.get('start_date')
        if start_date and v <= start_date:
            raise ValueError('end_date must be after start_date')
        if start_date and (v - start_date).days > 30:
            raise ValueError('Allocation cannot exceed 30 days')
        return v
    
    @field_validator('start_date')
    def not_in_past(cls, v):
        if v < date.today():
            raise ValueError('start_date cannot be in the past')
        return v

class AllocationOut(BaseModel):
    allocation_id: int
    dyno_id: int
    dyno_name: str
    start_date: date
    end_date: date
    status: str

