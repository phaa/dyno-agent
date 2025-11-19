from sqlalchemy import Column, String, DateTime, func
from core.db import Base

class User(Base):
    __tablename__ = "allocations"
    email = Column(String, primary_key=True, index=True)
    fullname = Column(String, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())