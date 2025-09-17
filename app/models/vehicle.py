from sqlalchemy import (
    Column, Integer, String
)
from core.db import Base


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    vin = Column(String, unique=True, nullable=True)
    weight_lbs = Column(Integer, nullable=False)
    drive_type = Column(String, nullable=False)  # '2WD' or 'AWD'
