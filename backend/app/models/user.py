"""User model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Optional, Dict
from uuid import UUID

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSONType, generate_uuid

if TYPE_CHECKING:
    from app.models.goal import Achievement, Goal, Streak
    from app.models.memory import Conversation, Fact, Pattern
    from app.models.skill import Skill


class User(Base):
    """User model - single user system but structured for future expansion."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONType(), default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    facts: Mapped[list["Fact"]] = relationship("Fact", back_populates="user")
    patterns: Mapped[list["Pattern"]] = relationship("Pattern", back_populates="user")
    skills: Mapped[list["Skill"]] = relationship("Skill", back_populates="user")
    goals: Mapped[list["Goal"]] = relationship("Goal", back_populates="user")
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user"
    )
    streaks: Mapped[list["Streak"]] = relationship("Streak", back_populates="user")
    achievements: Mapped[list["Achievement"]] = relationship(
        "Achievement", back_populates="user"
    )
