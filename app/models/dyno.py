from sqlalchemy import (
    Column, Integer, String, Date, Boolean
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.db import Base


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