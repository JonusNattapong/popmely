from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import MetaTrader5 as mt5
from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.utils.formatters import format_position, format_order, format_deal
from popmely.config import config

def place_order(
    symbol: str,
    action: str,
    volume: float,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
    deviation: Optional[int] = None,
    comment: str = "AI_MCP_Order",
    magic: Optional[int] = None
) -> Dict[str, Any]:
    """Execute a market BUY or SELL order on MT5 with lot size, SL, and TP."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    action_upper = action.upper()
    if action_upper not in ("BUY", "SELL"):
        return {"status": "error", "message": "Action must be 'BUY' or 'SELL'"}

    if volume > config.MAX_LOT_SIZE:
        return {"status": "error", "message": f"Volume {volume} exceeds safety max lot size {config.MAX_LOT_SIZE}"}

    if config.REQUIRE_SL and (sl is None or sl <= 0):
        return {"status": "error", "message": "Stop Loss (sl) is required by server safety config"}

    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"status": "error", "message": f"Cannot get tick for '{symbol}'"}

    order_type = mt5.ORDER_TYPE_BUY if action_upper == "BUY" else mt5.ORDER_TYPE_SELL
    price = tick.ask if action_upper == "BUY" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": float(price),
        "sl": float(sl) if sl is not None else 0.0,
        "tp": float(tp) if tp is not None else 0.0,
        "deviation": deviation or config.DEFAULT_DEVIATION,
        "magic": magic or config.DEFAULT_MAGIC,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    check = mt5.order_check(request)
    if check is None or check.retcode != mt5.TRADE_RETCODE_DONE:
        request["type_filling"] = mt5.ORDER_FILLING_RETURN
        check = mt5.order_check(request)
        if check is None or check.retcode != mt5.TRADE_RETCODE_DONE:
            request["type_filling"] = mt5.ORDER_FILLING_FOK

    result = mt5.order_send(request)
    if result is None:
        return {"status": "error", "message": f"Order send failed: {mt5.last_error()}"}

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {
            "status": "error",
            "retcode": result.retcode,
            "comment": result.comment,
            "message": f"Order rejected by broker: retcode={result.retcode}, comment='{result.comment}'"
        }

    return {
        "status": "success",
        "order_ticket": result.order,
        "deal_ticket": result.deal,
        "volume": result.volume,
        "price": result.price,
        "comment": result.comment,
        "symbol": symbol,
        "action": action_upper
    }

def place_pending_order(
    symbol: str,
    order_type: str,
    price: float,
    volume: float,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
    deviation: Optional[int] = None,
    comment: str = "AI_MCP_Pending",
    magic: Optional[int] = None
) -> Dict[str, Any]:
    """Place a pending order (BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP)."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    type_map = {
        "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
        "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
        "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
        "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
    }

    type_upper = order_type.upper()
    if type_upper not in type_map:
        return {"status": "error", "message": f"Invalid order_type. Supported: {list(type_map.keys())}"}

    if volume > config.MAX_LOT_SIZE:
        return {"status": "error", "message": f"Volume {volume} exceeds safety max lot size {config.MAX_LOT_SIZE}"}

    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": float(volume),
        "type": type_map[type_upper],
        "price": float(price),
        "sl": float(sl) if sl is not None else 0.0,
        "tp": float(tp) if tp is not None else 0.0,
        "deviation": deviation or config.DEFAULT_DEVIATION,
        "magic": magic or config.DEFAULT_MAGIC,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    if result is None:
        return {"status": "error", "message": f"Pending order send failed: {mt5.last_error()}"}

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {
            "status": "error",
            "retcode": result.retcode,
            "comment": result.comment,
            "message": f"Pending order rejected: retcode={result.retcode}, comment='{result.comment}'"
        }

    return {
        "status": "success",
        "order_ticket": result.order,
        "symbol": symbol,
        "type": type_upper,
        "price": price,
        "volume": volume
    }

def get_positions(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Get all open active positions or filter by symbol."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None:
        return {"status": "error", "message": "Failed to get positions"}

    data = [format_position(pos) for pos in positions]
    total_profit = round(sum(p["profit"] for p in data), 2)

    return {
        "status": "success",
        "count": len(data),
        "total_unrealized_profit": total_profit,
        "positions": data
    }

def modify_position(ticket: int, sl: Optional[float] = None, tp: Optional[float] = None) -> Dict[str, Any]:
    """Modify Stop Loss and/or Take Profit for an open position by Ticket ID."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    positions = mt5.positions_get(ticket=ticket)
    if positions is None or len(positions) == 0:
        return {"status": "error", "message": f"Position ticket #{ticket} not found"}

    pos = positions[0]
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol": pos.symbol,
        "sl": float(sl) if sl is not None else pos.sl,
        "tp": float(tp) if tp is not None else pos.tp
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        err = result.comment if result else str(mt5.last_error())
        return {"status": "error", "message": f"Failed to modify position #{ticket}: {err}"}

    return {
        "status": "success",
        "ticket": ticket,
        "sl": request["sl"],
        "tp": request["tp"]
    }

def close_position(ticket: int, volume: Optional[float] = None) -> Dict[str, Any]:
    """Close an open position (or partially close if volume is specified) by Ticket ID."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    positions = mt5.positions_get(ticket=ticket)
    if positions is None or len(positions) == 0:
        return {"status": "error", "message": f"Position ticket #{ticket} not found"}

    pos = positions[0]
    close_volume = float(volume) if volume is not None and volume > 0 else pos.volume
    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY

    tick = mt5.symbol_info_tick(pos.symbol)
    if tick is None:
        return {"status": "error", "message": f"Cannot get tick price for {pos.symbol}"}

    close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": ticket,
        "symbol": pos.symbol,
        "volume": close_volume,
        "type": close_type,
        "price": close_price,
        "deviation": config.DEFAULT_DEVIATION,
        "magic": pos.magic,
        "comment": "AI_MCP_Close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    check = mt5.order_check(request)
    if check is None or check.retcode != mt5.TRADE_RETCODE_DONE:
        request["type_filling"] = mt5.ORDER_FILLING_RETURN

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        err = result.comment if result else str(mt5.last_error())
        return {"status": "error", "message": f"Failed to close position #{ticket}: {err}"}

    return {
        "status": "success",
        "closed_ticket": ticket,
        "closed_volume": close_volume,
        "close_price": result.price,
        "comment": result.comment
    }

def close_all_positions(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Emergency close all open positions or all positions for a specific symbol."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None or len(positions) == 0:
        return {"status": "success", "message": "No open positions to close", "closed_count": 0}

    results = []
    for pos in positions:
        res = close_position(pos.ticket)
        results.append({"ticket": pos.ticket, "symbol": pos.symbol, "result": res})

    return {
        "status": "success",
        "closed_count": len(results),
        "details": results
    }

def get_pending_orders(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Get all active pending orders or filter by symbol."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    orders = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
    if orders is None:
        return {"status": "error", "message": "Failed to get pending orders"}

    data = [format_order(o) for o in orders]
    return {
        "status": "success",
        "count": len(data),
        "orders": data
    }

def cancel_pending_order(ticket: int) -> Dict[str, Any]:
    """Cancel a pending order by ticket ID."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    request = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": ticket
    }
    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        err = result.comment if result else str(mt5.last_error())
        return {"status": "error", "message": f"Failed to cancel order #{ticket}: {err}"}

    return {"status": "success", "cancelled_ticket": ticket}

def get_trade_history(days: int = 7, symbol: Optional[str] = None) -> Dict[str, Any]:
    """Get closed trade deals and profit history for the past N days."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    from_date = datetime.now() - timedelta(days=days)
    to_date = datetime.now()

    if symbol:
        deals = mt5.history_deals_get(from_date, to_date, symbol=symbol)
    else:
        deals = mt5.history_deals_get(from_date, to_date)

    if deals is None:
        return {"status": "error", "message": "Failed to fetch trade history"}

    data = [format_deal(d) for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
    total_profit = round(sum(d["profit"] + d["swap"] + d["commission"] + d["fee"] for d in data), 2)

    return {
        "status": "success",
        "days": days,
        "count": len(data),
        "total_realized_pnl": total_profit,
        "deals": data
    }
