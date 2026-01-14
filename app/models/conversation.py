from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base
from .user import User


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    user_email: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.email")
    )

    title: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now()
    )

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan"
    )

    user: Mapped[User] = relationship()


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    conversation_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("conversations.id")
    )

    role: Mapped[Literal["user", "agent"]] = mapped_column(
        String,
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(
        back_populates="messages"
    )
