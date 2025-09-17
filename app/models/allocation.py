from sqlalchemy import (
    Column, Integer, String, Date, 
    ForeignKey, DateTime
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.db import Base


class Allocation(Base):
    __tablename__ = "allocations"
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    dyno_id = Column(Integer, ForeignKey("dynos.id"), nullable=False)
    test_type = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="scheduled")  # scheduled | completed | cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vehicle = relationship("Vehicle")
    dyno = relationship("Dyno", back_populates="allocations")