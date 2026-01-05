from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean
from datetime import datetime
from core.db import Base

class Metrics(Base):
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    correlation_id = Column(String, index=True)
    service_name = Column(String, index=True)
    method_name = Column(String, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    
    # Performance metrics
    duration_ms = Column(Float)
    success = Column(Boolean)
    error_message = Column(String, nullable=True)
    
    # Business metrics
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)