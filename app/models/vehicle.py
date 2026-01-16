from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base

# Avoid circular imports
# We import Allocation only for type checking purposes
if TYPE_CHECKING:
    from models.allocation import Allocation


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    vin: Mapped[str | None] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=True
    )

    build_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    program: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    cert_team: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    weight_lbs: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    weight_class: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )  # '<10k' | '>10k'

    drive_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )  # '2WD' | 'AWD' | 'any'

    engine: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )  # powerpack

    build_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    allocations: Mapped[list[Allocation]] = relationship(
        back_populates="vehicle",
        cascade="all, delete-orphan"
    )
