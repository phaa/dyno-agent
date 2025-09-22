from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, ARRAY, func
from sqlalchemy.orm import relationship
from core.db import Base

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    vin = Column(String, unique=True, nullable=True)
    build_id = Column(String, nullable=True)
    program = Column(String, nullable=True)
    cert_team = Column(String, nullable=True)
    weight_class = Column(String, nullable=True)  # '<10k' | '>10k'
    drive_type = Column(String, nullable=True)  # '2WD' | 'AWD' | 'any'
    engine = Column(String, nullable=True)  # powerpack
    build_type = Column(String, nullable=True)
    allocations = relationship("Allocation", back_populates="vehicle")