"""Polymarket MCP Integration Suite for popmely.

Provides:
1. Market Discovery & Odds Query (Gamma API)
2. Live Level 2 Orderbook & Pricing (CLOB API)
3. User Portfolio & Open Positions Query (Data API)
4. Historical Trade & Activity Audit (Data API)
5. Order Execution & Order Cancellation (py_clob_client with Paper & Live mode)
"""

from typing import Dict, Any, List, Optional
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GAMMA_BASE_URL = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
CLOB_BASE_URL = os.getenv("CLOB_BASE_URL", "https://clob.polymarket.com")
DATA_API_BASE_URL = "https://data-api.polymarket.com"
DEFAULT_WALLET = os.getenv("FUNDER_ADDRESS", "0x6251f4BfecE66E3c547859915477dF27ef186056")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")


# =====================================================================
# 1. MARKET DISCOVERY & ODDS
# =====================================================================

def poly_get_markets(
    query: Optional[str] = None,
    limit: int = 10,
    active: bool = True
) -> Dict[str, Any]:
    """Search and discover Polymarket prediction markets, odds, volume, and outcome tokens."""
    try:
        url = f"{GAMMA_BASE_URL}/markets"
        params = {"limit": limit, "active": str(active).lower(), "closed": "false"}
        if query:
            # Query by tag or keyword
            params["tag"] = query

        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return {"status": "error", "message": f"Gamma API returned status {resp.status_code}"}

        markets = resp.json()
        results = []
        for m in markets:
            # Parse tokens and prices
            clob_token_ids = m.get("clobTokenIds") or "[]"
            if isinstance(clob_token_ids, str):
                try:
                    import json
                    tokens = json.loads(clob_token_ids)
                except Exception:
                    tokens = []
            else:
                tokens = clob_token_ids

            outcomes = m.get("outcomes") or "[]"
            if isinstance(outcomes, str):
                try:
                    import json
                    outcomes_list = json.loads(outcomes)
                except Exception:
                    outcomes_list = []
            else:
                outcomes_list = outcomes

            outcome_prices = m.get("outcomePrices") or "[]"
            if isinstance(outcome_prices, str):
                try:
                    import json
                    prices_list = json.loads(outcome_prices)
                except Exception:
                    prices_list = []
            else:
                prices_list = outcome_prices

            results.append({
                "condition_id": m.get("conditionId"),
                "question": m.get("question"),
                "slug": m.get("slug"),
                "volume_usd": float(m.get("volume", 0)),
                "liquidity_usd": float(m.get("liquidity", 0) or 0),
                "outcomes": outcomes_list,
                "outcome_prices": prices_list,
                "token_ids": tokens,
                "end_date": m.get("endDate")
            })

        # Filter by keyword if query was provided and tag filter was broad
        if query and not params.get("tag"):
            q_lower = query.lower()
            results = [r for r in results if q_lower in r["question"].lower() or q_lower in r["slug"].lower()]

        return {
            "status": "success",
            "count": len(results),
            "markets": results
        }
    except Exception as e:
        return {"status": "error", "message": f"Market query failed: {e}"}


def poly_get_orderbook(token_id: str) -> Dict[str, Any]:
    """Retrieve the live Level 2 orderbook (Bids and Asks) for a specific Polymarket outcome token."""
    if not token_id:
        return {"status": "error", "message": "token_id is required"}

    try:
        url = f"{CLOB_BASE_URL}/book?token_id={token_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            book = resp.json()
            return {
                "status": "success",
                "token_id": token_id,
                "market": book.get("market"),
                "bids": book.get("bids", [])[:5],
                "asks": book.get("asks", [])[:5],
                "spread": round(float(book.get("asks", [{"price": 0}])[0].get("price", 0)) - float(book.get("bids", [{"price": 0}])[0].get("price", 0)), 4) if book.get("bids") and book.get("asks") else None
            }
        else:
            return {"status": "error", "message": f"CLOB returned {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Orderbook fetch failed: {e}"}


# =====================================================================
# 2. PORTFOLIO & HISTORICAL ACTIVITY
# =====================================================================

def poly_get_portfolio(user_address: Optional[str] = None) -> Dict[str, Any]:
    """Query active open positions and portfolio value on Polymarket for a given wallet address."""
    addr = user_address or DEFAULT_WALLET
    if not addr:
        return {"status": "error", "message": "Wallet address not provided or configured in FUNDER_ADDRESS"}

    try:
        url = f"{DATA_API_BASE_URL}/positions?user={addr}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return {"status": "error", "message": f"Data API returned status {resp.status_code}"}

        positions = resp.json()
        total_val = sum(float(p.get("currentValue", 0)) for p in positions)

        return {
            "status": "success",
            "wallet_address": addr,
            "open_positions_count": len(positions),
            "total_portfolio_value_usd": round(total_val, 2),
            "positions": positions
        }
    except Exception as e:
        return {"status": "error", "message": f"Portfolio fetch failed: {e}"}


def poly_get_trade_history(
    user_address: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Query on-chain closed trade history and executed fills on Polymarket."""
    addr = user_address or DEFAULT_WALLET
    if not addr:
        return {"status": "error", "message": "Wallet address not provided"}

    try:
        url = f"{DATA_API_BASE_URL}/trades?user={addr}&limit={limit}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return {"status": "error", "message": f"Data API returned status {resp.status_code}"}

        trades = resp.json()
        return {
            "status": "success",
            "wallet_address": addr,
            "total_trades_fetched": len(trades),
            "trades": trades
        }
    except Exception as e:
        return {"status": "error", "message": f"Trade history fetch failed: {e}"}


# =====================================================================
# 3. LIVE ORDER EXECUTION & MANAGEMENT (REAL MAINNET CLOB)
# =====================================================================

def poly_place_order(
    token_id: str,
    side: str = "BUY",
    price: float = 0.50,
    size_usd: float = 10.0
) -> Dict[str, Any]:
    """Place a real live limit order directly on Polymarket CLOB Mainnet using your wallet Private Key."""
    side_clean = side.upper()
    if side_clean not in ("BUY", "SELL"):
        return {"status": "error", "message": "Side must be 'BUY' or 'SELL'"}

    if not (0.01 <= price <= 0.99):
        return {"status": "error", "message": "Price must be between 0.01 and 0.99 (representing 1% to 99% probability)"}

    shares = round(size_usd / price, 2)
    if shares <= 0:
        return {"status": "error", "message": "Order size too small to purchase shares"}

    pk = PRIVATE_KEY
    if not pk:
        return {"status": "error", "message": "PRIVATE_KEY not configured in .env for live Polymarket execution"}

    if not pk.startswith("0x"):
        pk = f"0x{pk}"

    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import OrderArgs, OrderType

        client = ClobClient(
            host=CLOB_BASE_URL,
            chain_id=137,
            key=pk
        )
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)

        order_args = OrderArgs(
            price=price,
            size=shares,
            side=side_clean,
            token_id=token_id
        )
        signed_order = client.create_order(order_args)
        resp = client.post_order(signed_order, OrderType.GTC)

        return {
            "status": "success",
            "mode": "LIVE_MAINNET",
            "order_id": resp.get("orderID"),
            "token_id": token_id,
            "side": side_clean,
            "price": price,
            "shares": shares,
            "size_usd": size_usd,
            "raw_response": resp,
            "message": f"Real order placed on Polymarket: {side_clean} {shares} shares @ {price} (${size_usd} USD)"
        }
    except Exception as e:
        return {"status": "error", "mode": "LIVE_MAINNET", "message": f"Live Polymarket order execution failed: {e}"}


def poly_cancel_order(order_id: str) -> Dict[str, Any]:
    """Cancel an active open order on Polymarket CLOB Mainnet."""
    if not order_id:
        return {"status": "error", "message": "order_id is required"}

    pk = PRIVATE_KEY
    if not pk:
        return {"status": "error", "message": "PRIVATE_KEY not configured in .env"}

    if not pk.startswith("0x"):
        pk = f"0x{pk}"

    try:
        from py_clob_client.client import ClobClient

        client = ClobClient(
            host=CLOB_BASE_URL,
            chain_id=137,
            key=pk
        )
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)

        resp = client.cancel(order_id)
        return {
            "status": "success",
            "mode": "LIVE_MAINNET",
            "canceled_order_id": order_id,
            "response": resp
        }
    except Exception as e:
        return {"status": "error", "message": f"Cancel order failed: {e}"}
