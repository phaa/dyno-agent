from __future__ import annotations
from  typing import TYPE_CHECKING
from datetime import date

from sqlalchemy import (
    Integer,
    String,
    Date,
    Boolean,
    ARRAY,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base

# Avoid circular imports
# We import Allocation only for type checking purposes
if TYPE_CHECKING:
    from models.allocation import Allocation


class Dyno(Base):
    __tablename__ = "dynos"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    supported_weight_classes: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list
    )

    supported_drives: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list
    )

    supported_test_types: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True
    )

    available_from: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    available_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    allocations: Mapped[list[Allocation]] = relationship(
        back_populates="dyno",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "idx_dyno_availability",
            "enabled",
            "available_from",
            "available_to",
        ),
    )
