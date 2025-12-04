from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, ARRAY, func
from sqlalchemy.orm import relationship
from core.db import Base


class Dyno(Base):
    __tablename__ = "dynos"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    supported_weight_classes = Column(ARRAY(String), nullable=False, default=[])  # '<10k' | '>10k' | 'any'
    supported_drives = Column(ARRAY(String), nullable=False, default=[])  # '2WD' | 'AWD' | 'any'
    supported_test_types = Column(ARRAY(String), nullable=False, default=[])
    enabled = Column(Boolean, default=True)
    available_from = Column(Date, nullable=True)
    available_to = Column(Date, nullable=True)
    allocations = relationship("Allocation", back_populates="dyno")