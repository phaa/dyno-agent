from __future__ import annotations

from datetime import datetime
from typing import List, TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, ForeignKey, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base

if TYPE_CHECKING:
    from models.user import User


class Role(Base):
    """Role model for RBAC"""
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True
    )  # USER, POWER_USER, ADMIN

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    # Many-to-many with Permission
    permissions: Mapped[List[Permission]] = relationship(
        secondary="role_permission",
        back_populates="roles"
    )


class Permission(Base):
    """Permission model for fine-grained access control"""
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True
    )  # view:dynos, allocate:vehicle

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    category: Mapped[str] = mapped_column(
        String(50)
    )  # tool, admin, view

    # Many-to-many with Role
    roles: Mapped[List[Role]] = relationship(
        secondary="role_permission",
        back_populates="permissions"
    )


class UserRole(Base):
    """
    Association object between User and Role with metadata.
    """
    __tablename__ = "user_role"

    user_email: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.email"),
        primary_key=True
    )

    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("roles.id"),
        primary_key=True
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    # Relationships
    user: Mapped[User] = relationship(
        back_populates="user_roles"
    )

    role: Mapped[Role] = relationship()


# Association table between Role and Permission
role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id"), primary_key=True),
)