"""Add agent conversation tables for persistence

Revision ID: 003
Revises: 002
Create Date: 2026-03-20

This migration adds tables for agent conversation persistence:
- agent_conversations: Stores conversation sessions
- conversation_messages: Stores individual messages within conversations

Database-agnostic - works with both SQLite and PostgreSQL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    """Check if current database is SQLite."""
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    is_sqlite = _is_sqlite()

    # Create agent_conversations table
    if is_sqlite:
        op.create_table(
            "agent_conversations",
            sa.Column("id", sa.String(36), nullable=False, primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("title", sa.String(255), nullable=True),
            sa.Column("extra_data", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        )
    else:
        from sqlalchemy.dialects import postgresql
        op.create_table(
            "agent_conversations",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                server_default=text("now()"),
                nullable=False,
            ),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("title", sa.String(255), nullable=True),
            sa.Column("extra_data", postgresql.JSONB(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create indexes for agent_conversations
    op.create_index(
        "ix_agent_conversations_user_id",
        "agent_conversations",
        ["user_id"],
    )
    op.create_index(
        "ix_agent_conversations_started_at",
        "agent_conversations",
        ["started_at"],
    )
    op.create_index(
        "ix_agent_conversations_user_started",
        "agent_conversations",
        ["user_id", "started_at"],
    )

    # Create conversation_messages table
    if is_sqlite:
        op.create_table(
            "conversation_messages",
            sa.Column("id", sa.String(36), nullable=False, primary_key=True),
            sa.Column("conversation_id", sa.String(36), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "timestamp",
                sa.DateTime(timezone=True),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
            sa.Column("tool_calls", sa.JSON(), nullable=True),
            sa.Column("tokens_used", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["conversation_id"],
                ["agent_conversations.id"],
                ondelete="CASCADE",
            ),
        )
    else:
        from sqlalchemy.dialects import postgresql
        op.create_table(
            "conversation_messages",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "timestamp",
                sa.DateTime(timezone=True),
                server_default=text("now()"),
                nullable=False,
            ),
            sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
            sa.Column("tokens_used", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["conversation_id"],
                ["agent_conversations.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create indexes for conversation_messages
    op.create_index(
        "ix_conversation_messages_conversation_id",
        "conversation_messages",
        ["conversation_id"],
    )
    op.create_index(
        "ix_conversation_messages_timestamp",
        "conversation_messages",
        ["timestamp"],
    )
    op.create_index(
        "ix_conversation_messages_conv_timestamp",
        "conversation_messages",
        ["conversation_id", "timestamp"],
    )


def downgrade() -> None:
    # Drop conversation_messages indexes
    op.drop_index(
        "ix_conversation_messages_conv_timestamp",
        table_name="conversation_messages",
    )
    op.drop_index(
        "ix_conversation_messages_timestamp",
        table_name="conversation_messages",
    )
    op.drop_index(
        "ix_conversation_messages_conversation_id",
        table_name="conversation_messages",
    )

    # Drop conversation_messages table
    op.drop_table("conversation_messages")

    # Drop agent_conversations indexes
    op.drop_index(
        "ix_agent_conversations_user_started",
        table_name="agent_conversations",
    )
    op.drop_index(
        "ix_agent_conversations_started_at",
        table_name="agent_conversations",
    )
    op.drop_index(
        "ix_agent_conversations_user_id",
        table_name="agent_conversations",
    )

    # Drop agent_conversations table
    op.drop_table("agent_conversations")
