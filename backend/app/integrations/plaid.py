"""Plaid integration for banking and investment data.

This module provides integration with Plaid API to:
- Connect bank accounts via Plaid Link
- Retrieve account balances for net worth calculation
- Fetch recent transactions
- Access investment holdings

Plaid sandbox mode is free and provides test data for development.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from plaid.api import plaid_api
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid import Configuration, ApiClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class PlaidIntegration:
    """Plaid API client wrapper for banking integration."""

    def __init__(self):
        """Initialize Plaid client with configuration."""
        self.client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Plaid API client."""
        if not settings.plaid_client_id or not settings.plaid_secret:
            logger.warning("Plaid credentials not configured")
            return

        # Determine Plaid environment
        env_mapping = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com",
        }
        host = env_mapping.get(settings.plaid_env, "https://sandbox.plaid.com")

        configuration = Configuration(
            host=host,
            api_key={
                "clientId": settings.plaid_client_id,
                "secret": settings.plaid_secret,
            },
        )

        api_client = ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)
        logger.info(f"Plaid client initialized for environment: {settings.plaid_env}")

    @property
    def is_configured(self) -> bool:
        """Check if Plaid is properly configured."""
        return self.client is not None

    async def create_link_token(self, user_id: str) -> dict[str, Any]:
        """
        Create a Link token for Plaid Link initialization.

        The Link token is used to initialize Plaid Link in the frontend,
        which handles the bank connection UI flow.

        Args:
            user_id: Unique identifier for the user

        Returns:
            dict containing link_token and expiration
        """
        if not self.is_configured:
            raise ValueError("Plaid is not configured. Check your API credentials.")

        try:
            request = LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(client_user_id=user_id),
                client_name="Nexus",
                products=[Products("transactions"), Products("investments")],
                country_codes=[CountryCode("US")],
                language="en",
            )

            response = self.client.link_token_create(request)
            return {
                "link_token": response["link_token"],
                "expiration": response["expiration"],
            }
        except Exception as e:
            logger.error(f"Failed to create link token: {e}")
            raise

    async def exchange_public_token(self, public_token: str) -> dict[str, Any]:
        """
        Exchange a public token for an access token.

        After a user completes Plaid Link, we receive a public_token
        which must be exchanged for a permanent access_token.

        Args:
            public_token: The temporary public token from Plaid Link

        Returns:
            dict containing access_token and item_id
        """
        if not self.is_configured:
            raise ValueError("Plaid is not configured. Check your API credentials.")

        try:
            request = ItemPublicTokenExchangeRequest(public_token=public_token)
            response = self.client.item_public_token_exchange(request)

            return {
                "access_token": response["access_token"],
                "item_id": response["item_id"],
            }
        except Exception as e:
            logger.error(f"Failed to exchange public token: {e}")
            raise

    async def get_accounts(self, access_token: str) -> list[dict[str, Any]]:
        """
        Get all accounts associated with an access token.

        Args:
            access_token: The Plaid access token

        Returns:
            List of account objects with id, name, type, subtype, and mask
        """
        if not self.is_configured:
            raise ValueError("Plaid is not configured. Check your API credentials.")

        try:
            request = AccountsGetRequest(access_token=access_token)
            response = self.client.accounts_get(request)

            return [
                {
                    "id": account["account_id"],
                    "name": account["name"],
                    "official_name": account.get("official_name"),
                    "type": account["type"],
                    "subtype": account.get("subtype"),
                    "mask": account.get("mask"),
                }
                for account in response["accounts"]
            ]
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            raise

    async def get_balances(self, access_token: str) -> dict[str, Any]:
        """
        Get account balances for calculating net worth.

        Args:
            access_token: The Plaid access token

        Returns:
            dict with accounts and total net worth calculation
        """
        if not self.is_configured:
            raise ValueError("Plaid is not configured. Check your API credentials.")

        try:
            request = AccountsBalanceGetRequest(access_token=access_token)
            response = self.client.accounts_balance_get(request)

            accounts = []
            total_assets = 0.0
            total_liabilities = 0.0

            for account in response["accounts"]:
                balance = account.get("balances", {})
                current = balance.get("current") or 0.0
                available = balance.get("available")
                account_type = str(account.get("type", ""))

                account_data = {
                    "id": account["account_id"],
                    "name": account["name"],
                    "type": account_type,
                    "subtype": str(account.get("subtype", "")),
                    "current_balance": current,
                    "available_balance": available,
                    "currency": balance.get("iso_currency_code", "USD"),
                }
                accounts.append(account_data)

                # Calculate net worth
                # Assets: depository, investment, brokerage
                # Liabilities: credit, loan
                if account_type in ["depository", "investment", "brokerage", "other"]:
                    total_assets += current
                elif account_type in ["credit", "loan"]:
                    total_liabilities += current

            net_worth = total_assets - total_liabilities

            return {
                "accounts": accounts,
                "total_assets": round(total_assets, 2),
                "total_liabilities": round(total_liabilities, 2),
                "net_worth": round(net_worth, 2),
                "last_updated": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to get balances: {e}")
            raise

    async def get_transactions(
        self, access_token: str, days: int = 30
    ) -> dict[str, Any]:
        """
        Get recent transactions.

        Args:
            access_token: The Plaid access token
            days: Number of days of transaction history (default 30)

        Returns:
            dict with transactions and summary statistics
        """
        if not self.is_configured:
            raise ValueError("Plaid is not configured. Check your API credentials.")

        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            request = TransactionsGetRequest(
                access_token=access_token,
                start_date=start_date,
                end_date=end_date,
                options=TransactionsGetRequestOptions(count=100, offset=0),
            )
            response = self.client.transactions_get(request)

            transactions = []
            total_spending = 0.0
            total_income = 0.0
            by_category: dict[str, float] = {}

            for txn in response["transactions"]:
                amount = txn.get("amount", 0.0)
                categories = txn.get("category", [])
                primary_category = categories[0] if categories else "Uncategorized"

                transaction_data = {
                    "id": txn["transaction_id"],
                    "date": txn["date"].isoformat() if txn.get("date") else None,
                    "name": txn.get("name", ""),
                    "merchant_name": txn.get("merchant_name"),
                    "amount": amount,
                    "category": primary_category,
                    "categories": categories,
                    "pending": txn.get("pending", False),
                    "account_id": txn.get("account_id"),
                }
                transactions.append(transaction_data)

                # Aggregate spending/income
                # Positive amounts are debits (spending), negative are credits (income)
                if amount > 0:
                    total_spending += amount
                    by_category[primary_category] = (
                        by_category.get(primary_category, 0) + amount
                    )
                else:
                    total_income += abs(amount)

            # Sort categories by spending
            top_categories = sorted(
                by_category.items(), key=lambda x: x[1], reverse=True
            )[:5]

            return {
                "transactions": transactions,
                "total_count": response.get("total_transactions", len(transactions)),
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days,
                },
                "summary": {
                    "total_spending": round(total_spending, 2),
                    "total_income": round(total_income, 2),
                    "net": round(total_income - total_spending, 2),
                    "top_categories": [
                        {"category": cat, "amount": round(amt, 2)}
                        for cat, amt in top_categories
                    ],
                },
            }
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            raise

    async def get_investments(self, access_token: str) -> dict[str, Any]:
        """
        Get investment holdings.

        Args:
            access_token: The Plaid access token

        Returns:
            dict with investment accounts, holdings, and total value
        """
        if not self.is_configured:
            raise ValueError("Plaid is not configured. Check your API credentials.")

        try:
            request = InvestmentsHoldingsGetRequest(access_token=access_token)
            response = self.client.investments_holdings_get(request)

            # Build security lookup
            securities = {
                sec["security_id"]: sec for sec in response.get("securities", [])
            }

            holdings = []
            total_value = 0.0
            by_type: dict[str, float] = {}

            for holding in response.get("holdings", []):
                security_id = holding.get("security_id")
                security = securities.get(security_id, {})
                value = holding.get("institution_value") or 0.0

                holding_data = {
                    "security_id": security_id,
                    "account_id": holding.get("account_id"),
                    "name": security.get("name", "Unknown"),
                    "ticker_symbol": security.get("ticker_symbol"),
                    "type": security.get("type", "other"),
                    "quantity": holding.get("quantity", 0),
                    "price": security.get("close_price"),
                    "value": value,
                    "cost_basis": holding.get("cost_basis"),
                }
                holdings.append(holding_data)

                total_value += value
                security_type = security.get("type", "other")
                by_type[security_type] = by_type.get(security_type, 0) + value

            # Get investment accounts
            investment_accounts = [
                {
                    "id": acc["account_id"],
                    "name": acc["name"],
                    "type": str(acc.get("type", "")),
                    "subtype": str(acc.get("subtype", "")),
                    "balance": acc.get("balances", {}).get("current", 0),
                }
                for acc in response.get("accounts", [])
            ]

            return {
                "accounts": investment_accounts,
                "holdings": holdings,
                "total_value": round(total_value, 2),
                "allocation": {
                    asset_type: {
                        "value": round(value, 2),
                        "percentage": round(value / total_value * 100, 2)
                        if total_value > 0
                        else 0,
                    }
                    for asset_type, value in by_type.items()
                },
                "last_updated": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to get investments: {e}")
            # Investments might not be available for all accounts
            return {
                "accounts": [],
                "holdings": [],
                "total_value": 0,
                "allocation": {},
                "error": str(e),
            }


# Singleton instance
_plaid_integration: PlaidIntegration | None = None


def get_plaid_integration() -> PlaidIntegration:
    """Get or create the Plaid integration instance."""
    global _plaid_integration
    if _plaid_integration is None:
        _plaid_integration = PlaidIntegration()
    return _plaid_integration
