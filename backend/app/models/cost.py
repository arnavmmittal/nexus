"""API Usage Cost tracking model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from sqlalchemy import Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSONType, generate_uuid

if TYPE_CHECKING:
    from app.models.user import User


class APIUsage(Base):
    """Track API usage costs for budget management."""

    __tablename__ = "api_usage"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    operation: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    cost: Mapped[float] = mapped_column(Float(), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONType(),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_usage")

    def __repr__(self) -> str:
        return f"<APIUsage(id={self.id}, operation={self.operation}, cost=${self.cost:.4f})>"
