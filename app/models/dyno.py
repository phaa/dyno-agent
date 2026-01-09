from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, ARRAY, func, Index
from sqlalchemy.orm import relationship
from core.db import Base


class Dyno(Base):
    __tablename__ = "dynos"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    supported_weight_classes = Column(ARRAY(String), nullable=False, default=[])
    supported_drives = Column(ARRAY(String), nullable=False, default=[])
    supported_test_types = Column(ARRAY(String), nullable=False, default=[])
    enabled = Column(Boolean, default=True, index=True)
    available_from = Column(Date, nullable=True)
    available_to = Column(Date, nullable=True)
    allocations = relationship("Allocation", back_populates="dyno")
    
    __table_args__ = (
        Index('idx_dyno_availability', 'enabled', 'available_from', 'available_to'),
    )