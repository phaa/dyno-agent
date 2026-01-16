from __future__ import annotations

from datetime import datetime
from typing import Set

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base
from models.rbac import Role, UserRole


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        index=True
    )

    fullname: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    password: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # One-to-many with UserRole (association object)
    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Many-to-many convenience relationship with Role
    roles: Mapped[list[Role]] = relationship(
        secondary="user_role",
        lazy="selectin",
        overlaps="user,user_roles"
    )

    # Helper method to get all permissions
    def get_permissions(self) -> Set[str]:
        """Get all permissions for this user across all roles"""
        perms: Set[str] = set()
        for role in self.roles:
            perms.update(p.name for p in role.permissions)
        return perms

    # Helper method for checks
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        return permission in self.get_permissions()
