"""Finance module for Jarvis - READ-ONLY portfolio tracking and market data.

This module provides tools for:
- Real-time stock price lookups
- Historical stock data
- Portfolio tracking and analysis
- Spending pattern analysis
- Market comparison

IMPORTANT: This is READ-ONLY. No trading capabilities.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import yfinance as yf
except ImportError:
    yf = None  # Handle gracefully if yfinance not installed

from app.models.memory import Fact


# ============ CACHE CONFIGURATION ============

# Stock data cache with 5-minute TTL
_stock_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl_seconds = 300  # 5 minutes


def _get_cache_key(ticker: str, data_type: str) -> str:
    """Generate cache key for stock data."""
    return f"{ticker.upper()}:{data_type}"


def _is_cache_valid(cache_key: str) -> bool:
    """Check if cached data is still valid (within TTL)."""
    if cache_key not in _stock_cache:
        return False
    cached = _stock_cache[cache_key]
    return time.time() - cached.get("timestamp", 0) < _cache_ttl_seconds


def _get_cached(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached data if valid."""
    if _is_cache_valid(cache_key):
        return _stock_cache[cache_key].get("data")
    return None


def _set_cache(cache_key: str, data: Dict[str, Any]) -> None:
    """Set data in cache with timestamp."""
    _stock_cache[cache_key] = {
        "data": data,
        "timestamp": time.time()
    }


def _clear_expired_cache() -> None:
    """Remove expired cache entries."""
    current_time = time.time()
    expired_keys = [
        key for key, value in _stock_cache.items()
        if current_time - value.get("timestamp", 0) >= _cache_ttl_seconds
    ]
    for key in expired_keys:
        del _stock_cache[key]


# ============ TOOL DEFINITIONS ============

FINANCE_TOOLS = [
    {
        "name": "get_stock_price",
        "description": "Get the current stock price for a ticker symbol. Returns real-time price data including current price, day change, volume, and market cap.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., 'AAPL', 'GOOGL', 'MSFT')"
                }
            },
            "required": ["ticker"]
        },
        "requires_confirmation": False
    },
    {
        "name": "get_stock_history",
        "description": "Get historical price data for a stock. Returns open, high, low, close, and volume for the specified period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., 'AAPL', 'GOOGL', 'MSFT')"
                },
                "period": {
                    "type": "string",
                    "enum": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"],
                    "description": "Time period for historical data (default: '1mo')"
                },
                "interval": {
                    "type": "string",
                    "enum": ["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"],
                    "description": "Data interval (default: '1d'). Note: Intraday intervals only available for recent periods."
                }
            },
            "required": ["ticker"]
        },
        "requires_confirmation": False
    },
    {
        "name": "get_portfolio_summary",
        "description": "Get an aggregated summary of the user's tracked portfolio including total value, total gain/loss, and allocation breakdown.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "requires_confirmation": False
    },
    {
        "name": "get_holdings",
        "description": "List all tracked stock holdings with current values, cost basis, and profit/loss for each position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "enum": ["symbol", "value", "gain_loss", "gain_loss_pct"],
                    "description": "How to sort the holdings (default: 'value')"
                }
            },
            "required": []
        },
        "requires_confirmation": False
    },
    {
        "name": "add_holding",
        "description": "Track a new stock holding in the portfolio. This stores position data for tracking purposes only - not actual trading.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                },
                "shares": {
                    "type": "number",
                    "description": "Number of shares held"
                },
                "avg_cost": {
                    "type": "number",
                    "description": "Average cost per share"
                },
                "purchase_date": {
                    "type": "string",
                    "description": "Date of purchase (YYYY-MM-DD format, optional)"
                }
            },
            "required": ["symbol", "shares", "avg_cost"]
        },
        "requires_confirmation": False
    },
    {
        "name": "update_holding",
        "description": "Update an existing tracked holding (e.g., after buying more shares). This updates tracking data only - not actual trading.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                },
                "shares": {
                    "type": "number",
                    "description": "New total number of shares"
                },
                "avg_cost": {
                    "type": "number",
                    "description": "New average cost per share"
                }
            },
            "required": ["symbol"]
        },
        "requires_confirmation": False
    },
    {
        "name": "remove_holding",
        "description": "Remove a stock from the tracked portfolio. This removes tracking data only - not actual selling.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol to remove"
                }
            },
            "required": ["symbol"]
        },
        "requires_confirmation": False
    },
    {
        "name": "analyze_portfolio",
        "description": "Perform AI-powered analysis of portfolio diversification, risk metrics, and recommendations. This provides insights but NOT trading advice.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_recommendations": {
                    "type": "boolean",
                    "description": "Include diversification recommendations (default: true)"
                }
            },
            "required": []
        },
        "requires_confirmation": True  # Requires user confirmation
    },
    {
        "name": "get_spending_insights",
        "description": "Analyze spending patterns from tracked expenses to identify trends, categories, and opportunities for savings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["week", "month", "quarter", "year"],
                    "description": "Time period to analyze (default: 'month')"
                },
                "include_trends": {
                    "type": "boolean",
                    "description": "Include trend analysis comparing to previous periods (default: true)"
                }
            },
            "required": []
        },
        "requires_confirmation": False
    },
    {
        "name": "compare_to_market",
        "description": "Compare portfolio performance against the S&P 500 index over a specified time period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["1mo", "3mo", "6mo", "1y", "ytd"],
                    "description": "Comparison period (default: 'ytd')"
                }
            },
            "required": []
        },
        "requires_confirmation": False
    },
]


# ============ TOOL EXECUTOR ============

class FinanceToolExecutor:
    """Executes finance tools on behalf of the AI."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a finance tool and return the result as a string."""
        try:
            method = getattr(self, f"_tool_{tool_name}", None)
            if method is None:
                return json.dumps({
                    "success": False,
                    "error": f"Unknown finance tool '{tool_name}'"
                })
            result = await method(**tool_input)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error executing {tool_name}: {str(e)}"
            })

    def _check_yfinance(self) -> Optional[Dict[str, Any]]:
        """Check if yfinance is available."""
        if yf is None:
            return {
                "success": False,
                "error": "yfinance library not installed. Please install with: pip install yfinance"
            }
        return None

    # ============ STOCK DATA TOOLS ============

    async def _tool_get_stock_price(self, ticker: str) -> Dict[str, Any]:
        """Get current stock price for a ticker."""
        error = self._check_yfinance()
        if error:
            return error

        ticker = ticker.upper().strip()
        cache_key = _get_cache_key(ticker, "price")

        # Check cache first
        cached = _get_cached(cache_key)
        if cached:
            cached["from_cache"] = True
            return cached

        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Validate ticker exists
            if not info or info.get("regularMarketPrice") is None:
                # Try getting historical data as fallback
                hist = stock.history(period="1d")
                if hist.empty:
                    return {
                        "success": False,
                        "error": f"Invalid ticker symbol: {ticker}"
                    }
                # Use historical data
                current_price = float(hist["Close"].iloc[-1])
                previous_close = float(hist["Open"].iloc[0])
            else:
                current_price = info.get("regularMarketPrice") or info.get("currentPrice")
                previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

            if current_price is None:
                return {
                    "success": False,
                    "error": f"Unable to fetch price data for {ticker}"
                }

            # Calculate change
            change = current_price - previous_close if previous_close else 0
            change_pct = (change / previous_close * 100) if previous_close else 0

            result = {
                "success": True,
                "ticker": ticker,
                "name": info.get("shortName") or info.get("longName") or ticker,
                "current_price": round(current_price, 2),
                "previous_close": round(previous_close, 2) if previous_close else None,
                "change": round(change, 2),
                "change_percent": round(change_pct, 2),
                "currency": info.get("currency", "USD"),
                "market_cap": info.get("marketCap"),
                "volume": info.get("regularMarketVolume") or info.get("volume"),
                "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
                "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "pe_ratio": info.get("trailingPE"),
                "dividend_yield": info.get("dividendYield"),
                "timestamp": datetime.now().isoformat(),
                "from_cache": False,
                "message": f"{ticker} is currently trading at ${current_price:.2f} ({'+' if change >= 0 else ''}{change_pct:.2f}%)"
            }

            # Cache the result
            _set_cache(cache_key, result)

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch stock price: {str(e)}"
            }

    async def _tool_get_stock_history(
        self,
        ticker: str,
        period: str = "1mo",
        interval: str = "1d"
    ) -> Dict[str, Any]:
        """Get historical stock data."""
        error = self._check_yfinance()
        if error:
            return error

        ticker = ticker.upper().strip()
        cache_key = _get_cache_key(ticker, f"history_{period}_{interval}")

        # Check cache first
        cached = _get_cached(cache_key)
        if cached:
            cached["from_cache"] = True
            return cached

        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)

            if hist.empty:
                return {
                    "success": False,
                    "error": f"No historical data available for {ticker}"
                }

            # Convert to list of dicts
            data_points = []
            for idx, row in hist.iterrows():
                data_points.append({
                    "date": idx.strftime("%Y-%m-%d %H:%M:%S") if hasattr(idx, 'strftime') else str(idx),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"])
                })

            # Calculate period statistics
            first_close = float(hist["Close"].iloc[0])
            last_close = float(hist["Close"].iloc[-1])
            period_change = last_close - first_close
            period_change_pct = (period_change / first_close * 100) if first_close else 0

            result = {
                "success": True,
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "data_points": len(data_points),
                "history": data_points[-30:] if len(data_points) > 30 else data_points,  # Limit response size
                "full_data_available": len(data_points),
                "period_high": round(float(hist["High"].max()), 2),
                "period_low": round(float(hist["Low"].min()), 2),
                "period_open": round(first_close, 2),
                "period_close": round(last_close, 2),
                "period_change": round(period_change, 2),
                "period_change_percent": round(period_change_pct, 2),
                "average_volume": int(hist["Volume"].mean()),
                "from_cache": False,
                "message": f"{ticker} has {'gained' if period_change >= 0 else 'lost'} {abs(period_change_pct):.2f}% over the {period} period"
            }

            # Cache the result
            _set_cache(cache_key, result)

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch stock history: {str(e)}"
            }

    # ============ PORTFOLIO TOOLS ============

    async def _get_all_holdings(self) -> List[Dict[str, Any]]:
        """Helper to get all portfolio holdings from the database."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "portfolio",
                Fact.key.like("holding_%")
            )
        )
        facts = result.scalars().all()

        holdings = []
        for fact in facts:
            try:
                data = json.loads(fact.value)
                data["key"] = fact.key
                holdings.append(data)
            except json.JSONDecodeError:
                continue

        return holdings

    async def _tool_get_portfolio_summary(self) -> Dict[str, Any]:
        """Get aggregated portfolio summary."""
        holdings = await self._get_all_holdings()

        if not holdings:
            return {
                "success": True,
                "message": "No holdings tracked. Use 'add_holding' to start tracking your portfolio.",
                "total_value": 0,
                "total_cost": 0,
                "total_gain_loss": 0,
                "total_gain_loss_pct": 0,
                "holdings_count": 0
            }

        total_value = 0
        total_cost = 0
        sector_allocation = {}
        holdings_with_prices = []

        for holding in holdings:
            symbol = holding.get("symbol", "").upper()
            shares = float(holding.get("shares", 0))
            avg_cost = float(holding.get("avg_cost", 0))

            cost_basis = shares * avg_cost
            total_cost += cost_basis

            # Get current price
            price_result = await self._tool_get_stock_price(symbol)
            if price_result.get("success"):
                current_price = price_result.get("current_price", 0)
                current_value = shares * current_price
                total_value += current_value

                holdings_with_prices.append({
                    "symbol": symbol,
                    "shares": shares,
                    "current_price": current_price,
                    "current_value": current_value,
                    "cost_basis": cost_basis,
                    "gain_loss": current_value - cost_basis,
                    "gain_loss_pct": ((current_value - cost_basis) / cost_basis * 100) if cost_basis > 0 else 0
                })

        total_gain_loss = total_value - total_cost
        total_gain_loss_pct = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0

        # Calculate allocation percentages
        allocation = []
        for h in holdings_with_prices:
            pct = (h["current_value"] / total_value * 100) if total_value > 0 else 0
            allocation.append({
                "symbol": h["symbol"],
                "value": round(h["current_value"], 2),
                "percentage": round(pct, 2)
            })

        allocation.sort(key=lambda x: x["percentage"], reverse=True)

        return {
            "success": True,
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_gain_loss": round(total_gain_loss, 2),
            "total_gain_loss_pct": round(total_gain_loss_pct, 2),
            "holdings_count": len(holdings_with_prices),
            "allocation": allocation,
            "timestamp": datetime.now().isoformat(),
            "message": f"Portfolio value: ${total_value:,.2f} ({'+' if total_gain_loss >= 0 else ''}{total_gain_loss_pct:.2f}% overall)"
        }

    async def _tool_get_holdings(self, sort_by: str = "value") -> Dict[str, Any]:
        """List all holdings with current values and P&L."""
        holdings = await self._get_all_holdings()

        if not holdings:
            return {
                "success": True,
                "message": "No holdings tracked. Use 'add_holding' to start tracking your portfolio.",
                "holdings": [],
                "count": 0
            }

        detailed_holdings = []

        for holding in holdings:
            symbol = holding.get("symbol", "").upper()
            shares = float(holding.get("shares", 0))
            avg_cost = float(holding.get("avg_cost", 0))
            purchase_date = holding.get("purchase_date")

            cost_basis = shares * avg_cost

            # Get current price
            price_result = await self._tool_get_stock_price(symbol)
            if price_result.get("success"):
                current_price = price_result.get("current_price", 0)
                current_value = shares * current_price
                gain_loss = current_value - cost_basis
                gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0

                detailed_holdings.append({
                    "symbol": symbol,
                    "name": price_result.get("name", symbol),
                    "shares": shares,
                    "avg_cost": round(avg_cost, 2),
                    "current_price": round(current_price, 2),
                    "cost_basis": round(cost_basis, 2),
                    "current_value": round(current_value, 2),
                    "gain_loss": round(gain_loss, 2),
                    "gain_loss_pct": round(gain_loss_pct, 2),
                    "day_change_pct": price_result.get("change_percent", 0),
                    "purchase_date": purchase_date
                })
            else:
                detailed_holdings.append({
                    "symbol": symbol,
                    "shares": shares,
                    "avg_cost": round(avg_cost, 2),
                    "cost_basis": round(cost_basis, 2),
                    "error": f"Unable to fetch current price for {symbol}",
                    "purchase_date": purchase_date
                })

        # Sort holdings
        sort_key_map = {
            "symbol": lambda x: x.get("symbol", ""),
            "value": lambda x: x.get("current_value", 0),
            "gain_loss": lambda x: x.get("gain_loss", 0),
            "gain_loss_pct": lambda x: x.get("gain_loss_pct", 0)
        }
        sort_fn = sort_key_map.get(sort_by, sort_key_map["value"])
        detailed_holdings.sort(key=sort_fn, reverse=(sort_by != "symbol"))

        return {
            "success": True,
            "holdings": detailed_holdings,
            "count": len(detailed_holdings),
            "sorted_by": sort_by,
            "timestamp": datetime.now().isoformat()
        }

    async def _tool_add_holding(
        self,
        symbol: str,
        shares: float,
        avg_cost: float,
        purchase_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a new holding to track."""
        symbol = symbol.upper().strip()

        # Validate ticker exists
        price_check = await self._tool_get_stock_price(symbol)
        if not price_check.get("success"):
            return {
                "success": False,
                "error": f"Invalid ticker symbol: {symbol}"
            }

        # Check if already exists
        holding_key = f"holding_{symbol}"
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.key == holding_key
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            return {
                "success": False,
                "error": f"Holding for {symbol} already exists. Use 'update_holding' to modify."
            }

        holding_data = {
            "symbol": symbol,
            "shares": shares,
            "avg_cost": avg_cost,
            "purchase_date": purchase_date,
            "added_at": datetime.now().isoformat()
        }

        fact = Fact(
            user_id=self.user_id,
            category="portfolio",
            key=holding_key,
            value=json.dumps(holding_data),
            source="jarvis_finance",
        )
        self.db.add(fact)
        await self.db.flush()

        current_value = shares * price_check.get("current_price", 0)
        cost_basis = shares * avg_cost

        return {
            "success": True,
            "message": f"Added {shares} shares of {symbol} at ${avg_cost:.2f}/share to portfolio tracking",
            "holding": {
                "symbol": symbol,
                "shares": shares,
                "avg_cost": avg_cost,
                "cost_basis": round(cost_basis, 2),
                "current_price": price_check.get("current_price"),
                "current_value": round(current_value, 2)
            }
        }

    async def _tool_update_holding(
        self,
        symbol: str,
        shares: Optional[float] = None,
        avg_cost: Optional[float] = None
    ) -> Dict[str, Any]:
        """Update an existing holding."""
        symbol = symbol.upper().strip()
        holding_key = f"holding_{symbol}"

        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.key == holding_key
            )
        )
        fact = result.scalar_one_or_none()

        if not fact:
            return {
                "success": False,
                "error": f"No holding found for {symbol}. Use 'add_holding' first."
            }

        try:
            data = json.loads(fact.value)
        except json.JSONDecodeError:
            data = {}

        if shares is not None:
            data["shares"] = shares
        if avg_cost is not None:
            data["avg_cost"] = avg_cost
        data["updated_at"] = datetime.now().isoformat()

        fact.value = json.dumps(data)
        await self.db.flush()

        return {
            "success": True,
            "message": f"Updated {symbol} holding",
            "holding": {
                "symbol": symbol,
                "shares": data.get("shares"),
                "avg_cost": data.get("avg_cost")
            }
        }

    async def _tool_remove_holding(self, symbol: str) -> Dict[str, Any]:
        """Remove a holding from tracking."""
        symbol = symbol.upper().strip()
        holding_key = f"holding_{symbol}"

        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.key == holding_key
            )
        )
        fact = result.scalar_one_or_none()

        if not fact:
            return {
                "success": False,
                "error": f"No holding found for {symbol}"
            }

        await self.db.delete(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"Removed {symbol} from portfolio tracking"
        }

    async def _tool_analyze_portfolio(
        self,
        include_recommendations: bool = True
    ) -> Dict[str, Any]:
        """Analyze portfolio diversification and provide insights."""
        holdings = await self._get_all_holdings()

        if not holdings:
            return {
                "success": True,
                "message": "No holdings to analyze. Add holdings first.",
                "analysis": None
            }

        # Get detailed holdings with sector info
        total_value = 0
        sectors = {}
        holdings_detail = []

        for holding in holdings:
            symbol = holding.get("symbol", "").upper()
            shares = float(holding.get("shares", 0))
            avg_cost = float(holding.get("avg_cost", 0))

            # Get stock info
            try:
                stock = yf.Ticker(symbol)
                info = stock.info
                current_price = info.get("regularMarketPrice") or info.get("currentPrice", 0)
                sector = info.get("sector", "Unknown")
                industry = info.get("industry", "Unknown")
                beta = info.get("beta", 1.0)
            except Exception:
                current_price = avg_cost  # Fallback
                sector = "Unknown"
                industry = "Unknown"
                beta = 1.0

            current_value = shares * current_price
            total_value += current_value

            sectors[sector] = sectors.get(sector, 0) + current_value

            holdings_detail.append({
                "symbol": symbol,
                "value": current_value,
                "sector": sector,
                "industry": industry,
                "beta": beta
            })

        # Calculate sector allocation
        sector_allocation = [
            {"sector": k, "value": round(v, 2), "percentage": round(v / total_value * 100, 2)}
            for k, v in sectors.items()
        ]
        sector_allocation.sort(key=lambda x: x["percentage"], reverse=True)

        # Calculate portfolio beta (weighted average)
        weighted_beta = sum(
            h["value"] / total_value * (h.get("beta") or 1.0)
            for h in holdings_detail
        ) if total_value > 0 else 1.0

        # Concentration risk (largest position)
        max_position_pct = max(
            (h["value"] / total_value * 100 for h in holdings_detail),
            default=0
        ) if total_value > 0 else 0

        # Diversification score (0-100, higher is better)
        num_sectors = len(sectors)
        num_holdings = len(holdings)
        diversification_score = min(100, (
            (num_sectors * 10) +  # Sector diversity
            (num_holdings * 5) +  # Number of holdings
            (100 - max_position_pct)  # Concentration penalty
        ) / 2)

        analysis = {
            "total_value": round(total_value, 2),
            "holdings_count": num_holdings,
            "sectors_count": num_sectors,
            "sector_allocation": sector_allocation,
            "portfolio_beta": round(weighted_beta, 2),
            "largest_position_pct": round(max_position_pct, 2),
            "diversification_score": round(diversification_score, 1),
            "risk_level": (
                "High" if weighted_beta > 1.3 or max_position_pct > 40
                else "Medium" if weighted_beta > 1.0 or max_position_pct > 25
                else "Low"
            )
        }

        result = {
            "success": True,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }

        # Add recommendations if requested
        if include_recommendations:
            recommendations = []

            if max_position_pct > 30:
                recommendations.append(
                    f"Consider reducing concentration - your largest position is {max_position_pct:.1f}% of portfolio"
                )

            if num_sectors < 3:
                recommendations.append(
                    f"Portfolio is concentrated in {num_sectors} sector(s). Consider diversifying across more sectors."
                )

            if weighted_beta > 1.3:
                recommendations.append(
                    "Portfolio has high beta (>1.3), indicating higher volatility than the market. Consider adding defensive stocks."
                )

            if num_holdings < 5:
                recommendations.append(
                    "Consider adding more positions to reduce single-stock risk."
                )

            if not recommendations:
                recommendations.append(
                    "Portfolio appears well-diversified. Continue monitoring sector allocation and rebalancing as needed."
                )

            result["recommendations"] = recommendations
            result["disclaimer"] = "This analysis is for informational purposes only and should not be considered financial advice."

        return result

    # ============ SPENDING ANALYSIS TOOLS ============

    async def _tool_get_spending_insights(
        self,
        period: str = "month",
        include_trends: bool = True
    ) -> Dict[str, Any]:
        """Analyze spending patterns from expense data."""
        # Get all expense facts
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "finance_expense"
            )
        )
        facts = result.scalars().all()

        if not facts:
            return {
                "success": True,
                "message": "No expense data found. Log expenses using 'log_expense' to see spending insights.",
                "insights": None
            }

        # Parse expenses
        expenses = []
        for fact in facts:
            try:
                data = json.loads(fact.value)
                timestamp = data.get("timestamp")
                if timestamp:
                    expense_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                else:
                    expense_date = fact.created_at if hasattr(fact, 'created_at') else datetime.now()

                expenses.append({
                    "amount": float(data.get("amount", 0)),
                    "category": data.get("category", "other"),
                    "description": data.get("description", ""),
                    "date": expense_date,
                    "recurring": data.get("recurring", False)
                })
            except (json.JSONDecodeError, ValueError):
                continue

        if not expenses:
            return {
                "success": True,
                "message": "No valid expense data found.",
                "insights": None
            }

        # Determine date range based on period
        now = datetime.now()
        if period == "week":
            start_date = now - timedelta(days=7)
            previous_start = start_date - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
            previous_start = start_date - timedelta(days=30)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
            previous_start = start_date - timedelta(days=90)
        else:  # year
            start_date = now - timedelta(days=365)
            previous_start = start_date - timedelta(days=365)

        # Filter to current period
        current_period_expenses = [e for e in expenses if e["date"] >= start_date]
        previous_period_expenses = [e for e in expenses if previous_start <= e["date"] < start_date]

        # Calculate totals by category
        category_totals = {}
        for expense in current_period_expenses:
            cat = expense["category"]
            category_totals[cat] = category_totals.get(cat, 0) + expense["amount"]

        total_spending = sum(e["amount"] for e in current_period_expenses)
        recurring_total = sum(e["amount"] for e in current_period_expenses if e["recurring"])

        # Sort categories by amount
        category_breakdown = [
            {
                "category": k,
                "amount": round(v, 2),
                "percentage": round(v / total_spending * 100, 2) if total_spending > 0 else 0
            }
            for k, v in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        ]

        # Calculate averages
        days_in_period = (now - start_date).days or 1
        daily_average = total_spending / days_in_period
        weekly_average = daily_average * 7
        monthly_average = daily_average * 30

        insights = {
            "period": period,
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": now.strftime("%Y-%m-%d")
            },
            "total_spending": round(total_spending, 2),
            "transaction_count": len(current_period_expenses),
            "recurring_expenses": round(recurring_total, 2),
            "category_breakdown": category_breakdown,
            "daily_average": round(daily_average, 2),
            "weekly_average": round(weekly_average, 2),
            "monthly_projected": round(monthly_average, 2),
            "top_category": category_breakdown[0]["category"] if category_breakdown else None
        }

        # Add trend analysis
        if include_trends and previous_period_expenses:
            previous_total = sum(e["amount"] for e in previous_period_expenses)
            if previous_total > 0:
                change = total_spending - previous_total
                change_pct = (change / previous_total * 100)
                insights["trends"] = {
                    "previous_period_total": round(previous_total, 2),
                    "change": round(change, 2),
                    "change_percent": round(change_pct, 2),
                    "trend": "up" if change > 0 else "down" if change < 0 else "flat"
                }

        # Generate insights message
        top_cat = category_breakdown[0] if category_breakdown else None
        message = f"You've spent ${total_spending:.2f} over the past {period}"
        if top_cat:
            message += f", with {top_cat['category']} being your largest category at ${top_cat['amount']:.2f} ({top_cat['percentage']:.1f}%)"

        return {
            "success": True,
            "insights": insights,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

    # ============ MARKET COMPARISON TOOLS ============

    async def _tool_compare_to_market(self, period: str = "ytd") -> Dict[str, Any]:
        """Compare portfolio performance to S&P 500."""
        error = self._check_yfinance()
        if error:
            return error

        holdings = await self._get_all_holdings()

        if not holdings:
            return {
                "success": True,
                "message": "No holdings to compare. Add holdings first.",
                "comparison": None
            }

        # Get S&P 500 data (using SPY as proxy)
        try:
            spy = yf.Ticker("SPY")
            spy_hist = spy.history(period=period)
            if spy_hist.empty:
                return {
                    "success": False,
                    "error": "Unable to fetch S&P 500 data"
                }

            spy_start = float(spy_hist["Close"].iloc[0])
            spy_end = float(spy_hist["Close"].iloc[-1])
            spy_return = ((spy_end - spy_start) / spy_start) * 100

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch S&P 500 data: {str(e)}"
            }

        # Calculate portfolio performance
        portfolio_weighted_return = 0
        total_value = 0
        holding_returns = []

        for holding in holdings:
            symbol = holding.get("symbol", "").upper()
            shares = float(holding.get("shares", 0))
            avg_cost = float(holding.get("avg_cost", 0))

            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period=period)

                if not hist.empty:
                    start_price = float(hist["Close"].iloc[0])
                    end_price = float(hist["Close"].iloc[-1])
                    stock_return = ((end_price - start_price) / start_price) * 100

                    current_value = shares * end_price
                    total_value += current_value

                    holding_returns.append({
                        "symbol": symbol,
                        "return_pct": round(stock_return, 2),
                        "current_value": round(current_value, 2),
                        "vs_market": round(stock_return - spy_return, 2)
                    })

            except Exception:
                continue

        if total_value > 0:
            for hr in holding_returns:
                weight = hr["current_value"] / total_value
                portfolio_weighted_return += weight * hr["return_pct"]

        alpha = portfolio_weighted_return - spy_return

        # Sort by performance
        holding_returns.sort(key=lambda x: x["return_pct"], reverse=True)

        comparison = {
            "period": period,
            "portfolio_return": round(portfolio_weighted_return, 2),
            "sp500_return": round(spy_return, 2),
            "alpha": round(alpha, 2),
            "outperforming": alpha > 0,
            "holdings_breakdown": holding_returns,
            "best_performer": holding_returns[0] if holding_returns else None,
            "worst_performer": holding_returns[-1] if holding_returns else None
        }

        performance_msg = "outperforming" if alpha > 0 else "underperforming"
        message = f"Your portfolio {'has returned' if portfolio_weighted_return >= 0 else 'is down'} {abs(portfolio_weighted_return):.2f}% vs S&P 500's {'+' if spy_return >= 0 else ''}{spy_return:.2f}% ({performance_msg} by {abs(alpha):.2f}%)"

        return {
            "success": True,
            "comparison": comparison,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }


# ============ MODULE EXPORTS ============

__all__ = [
    "FINANCE_TOOLS",
    "FinanceToolExecutor",
]
