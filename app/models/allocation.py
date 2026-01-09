from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, ARRAY, func, Index
from sqlalchemy.orm import relationship
from core.db import Base

class Allocation(Base):
    __tablename__ = "allocations"
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    dyno_id = Column(Integer, ForeignKey("dynos.id"), nullable=True, index=True)
    test_type = Column(String, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    status = Column(String, nullable=False, default="scheduled", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="allocations")
    dyno = relationship("Dyno", back_populates="allocations")
    
    __table_args__ = (
        Index('idx_allocation_dyno_dates', 'dyno_id', 'start_date', 'end_date'),
        Index('idx_allocation_vehicle_status', 'vehicle_id', 'status'),
    )