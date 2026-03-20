"""Add API usage cost tracking table

Revision ID: 002
Revises: 001
Create Date: 2026-03-20

This migration adds the api_usage table for tracking API costs.
Database-agnostic - works with both SQLite and PostgreSQL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    """Check if current database is SQLite."""
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    is_sqlite = _is_sqlite()

    if is_sqlite:
        op.create_table(
            "api_usage",
            sa.Column("id", sa.String(36), nullable=False, primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("operation", sa.String(100), nullable=False),
            sa.Column("cost", sa.Float(), nullable=False),
            sa.Column(
                "timestamp",
                sa.DateTime(timezone=True),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        )
    else:
        from sqlalchemy.dialects import postgresql
        op.create_table(
            "api_usage",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("operation", sa.String(100), nullable=False),
            sa.Column("cost", sa.Float(), nullable=False),
            sa.Column(
                "timestamp",
                sa.DateTime(timezone=True),
                server_default=text("now()"),
                nullable=False,
            ),
            sa.Column("details", postgresql.JSONB(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create indexes for common queries
    op.create_index("ix_api_usage_user_id", "api_usage", ["user_id"])
    op.create_index("ix_api_usage_operation", "api_usage", ["operation"])
    op.create_index("ix_api_usage_timestamp", "api_usage", ["timestamp"])
    # Composite index for daily queries
    op.create_index(
        "ix_api_usage_user_timestamp",
        "api_usage",
        ["user_id", "timestamp"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_api_usage_user_timestamp", table_name="api_usage")
    op.drop_index("ix_api_usage_timestamp", table_name="api_usage")
    op.drop_index("ix_api_usage_operation", table_name="api_usage")
    op.drop_index("ix_api_usage_user_id", table_name="api_usage")

    # Drop table
    op.drop_table("api_usage")
