from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import (
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base

if TYPE_CHECKING:
    from models.vehicle import Vehicle
    from models.dyno import Dyno


class Allocation(Base):
    __tablename__ = "allocations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    vehicle_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vehicles.id"),
        nullable=False,
        index=True
    )

    dyno_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("dynos.id"),
        nullable=True,
        index=True
    )

    test_type: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    status: Mapped[
        Literal["scheduled", "in_progress", "completed", "cancelled"]
    ] = mapped_column(
        String,
        nullable=False,
        default="scheduled",
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    vehicle: Mapped["Vehicle"] = relationship(
        back_populates="allocations"
    )

    dyno: Mapped["Dyno | None"] = relationship(
        back_populates="allocations"
    )

    __table_args__ = (
        Index(
            "idx_allocation_dyno_dates",
            "dyno_id",
            "start_date",
            "end_date",
        ),
        Index(
            "idx_allocation_vehicle_status",
            "vehicle_id",
            "status",
        ),
    )
