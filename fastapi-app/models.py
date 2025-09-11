from sqlalchemy import (
    Column, Integer, String, Date, 
    Boolean, ForeignKey, DateTime
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .db import Base


class Dyno(Base):
    __tablename__ = "dynos"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    max_weight_lbs = Column(Integer, nullable=False)
    supported_drive = Column(String, nullable=False, default="any")  # '2WD', 'AWD', 'any'
    supported_test_types = Column(ARRAY(String), nullable=False, default=[])  # Postgres array
    available_from = Column(Date, nullable=True)
    available_to = Column(Date, nullable=True)
    enabled = Column(Boolean, default=True)
    allocations = relationship("Allocation", back_populates="dyno")


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    vin = Column(String, unique=True, nullable=True)
    weight_lbs = Column(Integer, nullable=False)
    drive_type = Column(String, nullable=False)  # '2WD' or 'AWD'


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