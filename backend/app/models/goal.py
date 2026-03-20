"""Goal models - Goals, Progress, Streaks, Achievements."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional, Optional, Dict
from uuid import UUID

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, generate_uuid

if TYPE_CHECKING:
    from app.models.user import User


class Goal(Base):
    """User goals with progress tracking."""

    __tablename__ = "goals"

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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'numeric', 'boolean', 'streak'
    target_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_value: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="goals")
    progress_logs: Mapped[list["GoalProgressLog"]] = relationship(
        "GoalProgressLog", back_populates="goal", cascade="all, delete-orphan"
    )

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage (0-100)."""
        if self.target_value is None or self.target_value == 0:
            return 0.0 if self.current_value == 0 else 100.0
        return min((self.current_value / self.target_value) * 100, 100.0)

    @property
    def is_completed(self) -> bool:
        """Check if goal is completed."""
        return self.status == "completed" or self.progress_percentage >= 100


class GoalProgressLog(Base):
    """Log of progress updates for goals."""

    __tablename__ = "goal_progress_log"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    goal_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("goals.id"),
        nullable=False,
    )
    previous_value: Mapped[float] = mapped_column(Float, nullable=False)
    new_value: Mapped[float] = mapped_column(Float, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    goal: Mapped["Goal"] = relationship("Goal", back_populates="progress_logs")


class Streak(Base):
    """User activity streaks."""

    __tablename__ = "streaks"

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
    activity: Mapped[str] = mapped_column(String(255), nullable=False)
    current_count: Mapped[int] = mapped_column(Integer, default=0)
    longest_count: Mapped[int] = mapped_column(Integer, default=0)
    last_logged: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="streaks")


class Achievement(Base):
    """Unlocked achievements."""

    __tablename__ = "achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_key", name="uq_user_achievement"),
    )

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
    achievement_key: Mapped[str] = mapped_column(String(100), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="achievements")
