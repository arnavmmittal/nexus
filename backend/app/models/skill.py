"""Skill models - Skills and XP logging."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Optional, Dict
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, generate_uuid

if TYPE_CHECKING:
    from app.models.user import User


class Skill(Base):
    """User skills with XP tracking."""

    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_skill_name"),)

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    current_level: Mapped[int] = mapped_column(Integer, default=1)
    current_xp: Mapped[int] = mapped_column(Integer, default=0)
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_practiced: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="skills")
    xp_logs: Mapped[list["SkillXPLog"]] = relationship(
        "SkillXPLog", back_populates="skill", cascade="all, delete-orphan"
    )

    @property
    def xp_for_next_level(self) -> int:
        """Calculate XP required for next level (using exponential curve)."""
        return int(100 * (1.5 ** (self.current_level - 1)))

    @property
    def level_progress(self) -> float:
        """Calculate progress towards next level (0-1)."""
        required = self.xp_for_next_level
        return min(self.current_xp / required, 1.0) if required > 0 else 0.0


class SkillXPLog(Base):
    """Log of XP gains for skills."""

    __tablename__ = "skill_xp_log"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    skill_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("skills.id"),
        nullable=False,
    )
    xp_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # 'claude_session', 'manual', 'integration'
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    skill: Mapped["Skill"] = relationship("Skill", back_populates="xp_logs")
