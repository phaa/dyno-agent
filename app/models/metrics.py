from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Integer, String, Float, DateTime, JSON, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class Metrics(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    correlation_id: Mapped[str] = mapped_column(
        String,
        index=True
    )

    service_name: Mapped[str] = mapped_column(
        String,
        index=True
    )

    method_name: Mapped[str] = mapped_column(
        String,
        index=True
    )

    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True
    )

    # Performance metrics
    duration_ms: Mapped[float] = mapped_column(
        Float
    )

    success: Mapped[bool] = mapped_column(
        Boolean
    )

    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    # Business metrics
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )
