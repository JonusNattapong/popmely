from typing import Dict, Any
import MetaTrader5 as mt5
from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.utils.formatters import format_account_info

def get_account_info() -> Dict[str, Any]:
    """Retrieve detailed information about the current MT5 trading account (Balance, Equity, Margin, Leverage)."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": f"Cannot connect to MT5: {mt5.last_error()}"}

    account = mt5.account_info()
    if account is None:
        return {"status": "error", "message": f"Failed to get account info: {mt5.last_error()}"}

    return {
        "status": "success",
        "data": format_account_info(account)
    }

def get_terminal_status() -> Dict[str, Any]:
    """Check MetaTrader 5 terminal status, connection to broker, and whether automated trading is enabled."""
    status = MT5ConnectionManager.get_status()
    return {
        "status": "success" if status.get("connected") else "error",
        "data": status
    }
