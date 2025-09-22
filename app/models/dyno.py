from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, ARRAY, func
from sqlalchemy.orm import relationship
from core.db import Base


class Dyno(Base):
    __tablename__ = "dynos"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    max_weight_class = Column(String, nullable=True)  # '<10k' | '>10k' | 'any'
    supported_drive = Column(String, nullable=False, default="any")  # '2WD' | 'AWD' | 'any'
    supported_test_types = Column(ARRAY(String), nullable=False, default=[])
    enabled = Column(Boolean, default=True)
    allocations = relationship("Allocation", back_populates="dyno")