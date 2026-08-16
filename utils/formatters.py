from datetime import datetime
from typing import Any, Dict, List, Optional
import MetaTrader5 as mt5

def format_account_info(account: Any) -> Dict[str, Any]:
    if account is None:
        return {}
    return {
        "login": account.login,
        "name": account.name,
        "server": account.server,
        "currency": account.currency,
        "leverage": account.leverage,
        "balance": round(account.balance, 2),
        "equity": round(account.equity, 2),
        "profit": round(account.profit, 2),
        "margin": round(account.margin, 2),
        "margin_free": round(account.margin_free, 2),
        "margin_level": round(account.margin_level, 2) if account.margin_level else 0.0,
        "trade_allowed": account.trade_allowed,
        "trade_expert": account.trade_expert,
        "limit_orders": account.limit_orders
    }

def format_tick(tick: Any, symbol: str) -> Dict[str, Any]:
    if tick is None:
        return {}
    spread = round((tick.ask - tick.bid), 5)
    return {
        "symbol": symbol,
        "bid": tick.bid,
        "ask": tick.ask,
        "spread": spread,
        "last": tick.last,
        "volume": tick.volume,
        "time": datetime.fromtimestamp(tick.time).isoformat()
    }

def format_position(pos: Any) -> Dict[str, Any]:
    type_str = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL" if pos.type == mt5.ORDER_TYPE_SELL else str(pos.type)
    return {
        "ticket": pos.ticket,
        "symbol": pos.symbol,
        "type": type_str,
        "volume": pos.volume,
        "price_open": pos.price_open,
        "price_current": pos.price_current,
        "sl": pos.sl,
        "tp": pos.tp,
        "profit": round(pos.profit, 2),
        "swap": round(pos.swap, 2),
        "comment": pos.comment,
        "magic": pos.magic,
        "time_open": datetime.fromtimestamp(pos.time).isoformat()
    }

def format_order(order: Any) -> Dict[str, Any]:
    types = {
        mt5.ORDER_TYPE_BUY: "BUY",
        mt5.ORDER_TYPE_SELL: "SELL",
        mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
        mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
        mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
        mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
    }
    return {
        "ticket": order.ticket,
        "symbol": order.symbol,
        "type": types.get(order.type, str(order.type)),
        "volume_initial": order.volume_initial,
        "volume_current": order.volume_current,
        "price_open": order.price_open,
        "sl": order.sl,
        "tp": order.tp,
        "state": order.state,
        "comment": order.comment,
        "magic": order.magic,
        "time_setup": datetime.fromtimestamp(order.time_setup).isoformat()
    }

def format_deal(deal: Any) -> Dict[str, Any]:
    return {
        "ticket": deal.ticket,
        "order": deal.order,
        "symbol": deal.symbol,
        "type": "BUY" if deal.type == mt5.DEAL_TYPE_BUY else "SELL" if deal.type == mt5.DEAL_TYPE_SELL else str(deal.type),
        "volume": deal.volume,
        "price": deal.price,
        "profit": round(deal.profit, 2),
        "commission": round(deal.commission, 2),
        "swap": round(deal.swap, 2),
        "fee": round(deal.fee, 2),
        "comment": deal.comment,
        "time": datetime.fromtimestamp(deal.time).isoformat()
    }
