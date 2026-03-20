"""Plaid integration models for storing tokens and account data."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSONType, generate_uuid


class PlaidItem(Base):
    """
    Plaid Item - represents a connection to a financial institution.

    Each Item can have multiple accounts (checking, savings, credit cards, etc.)
    associated with it.

    Security Note: Access tokens are stored encrypted. In production,
    use a proper encryption service (e.g., AWS KMS, HashiCorp Vault).
    """

    __tablename__ = "plaid_items"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Plaid identifiers
    item_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Access token - should be encrypted in production
    # Using Text for flexibility with encryption overhead
    access_token: Mapped[str] = mapped_column(Text, nullable=False)

    # Institution info (cached from Plaid)
    institution_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    institution_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Connection status
    status: Mapped[str] = mapped_column(
        String(50), default="active"
    )  # active, error, pending_expiration

    # Last sync timestamps
    last_accounts_sync: Mapped[datetime | None] = mapped_column(nullable=True)
    last_transactions_sync: Mapped[datetime | None] = mapped_column(nullable=True)
    last_investments_sync: Mapped[datetime | None] = mapped_column(nullable=True)

    # Error tracking
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    accounts: Mapped[list["PlaidAccount"]] = relationship(
        "PlaidAccount", back_populates="item", cascade="all, delete-orphan"
    )


class PlaidAccount(Base):
    """
    Plaid Account - represents an individual bank/investment account.

    Accounts are associated with Items and store cached balance information.
    """

    __tablename__ = "plaid_accounts"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    item_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("plaid_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Plaid account identifier
    account_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Account info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    official_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mask: Mapped[str | None] = mapped_column(String(10), nullable=True)  # Last 4 digits

    # Account type (depository, credit, loan, investment, etc.)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Cached balances (updated on sync)
    current_balance: Mapped[float | None] = mapped_column(nullable=True)
    available_balance: Mapped[float | None] = mapped_column(nullable=True)
    limit: Mapped[float | None] = mapped_column(nullable=True)  # For credit accounts
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    # User preferences
    include_in_net_worth: Mapped[bool] = mapped_column(default=True)
    custom_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    balance_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    item: Mapped["PlaidItem"] = relationship("PlaidItem", back_populates="accounts")


class PlaidTransaction(Base):
    """
    Cached Plaid Transaction for historical analysis.

    Transactions are cached locally for faster access and offline analysis.
    They are synced periodically from Plaid.
    """

    __tablename__ = "plaid_transactions"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # Plaid transaction identifier
    transaction_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )

    # Transaction details
    date: Mapped[datetime] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    amount: Mapped[float] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    # Categories (from Plaid)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    categories: Mapped[list[str]] = mapped_column(JSONType(), default=list)

    # Status
    pending: Mapped[bool] = mapped_column(default=False)

    # User customization
    custom_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    excluded_from_analysis: Mapped[bool] = mapped_column(default=False)

    # Metadata
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONType(), default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
