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

def smart_order(
    symbol: str,
    action: str,
    sl_price: float,
    tp_price: Optional[float] = None,
    rr_ratio: float = 2.0,
    risk_percent: float = 1.0,
    comment: str = "AI_SmartOrder"
) -> Dict[str, Any]:
    """Smart Order: Automatically computes exact Lot Size by risk % of account equity, checks Credit Score, calculates TP by R:R ratio, and executes market order in one step."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    from popmely.tools.credit_score import credit_score
    from popmely.tools.risk import calculate_lot_size

    # 1. Check Credit Score
    if credit_score.initialized and not credit_score.is_trading_allowed():
        return {
            "status": "error",
            "message": f"Trading BLOCKED by Credit Score (Tier: {credit_score.get_tier()}, Score: {credit_score.get_score_percent()}%). Reset score or improve performance before trading."
        }

    # 2. Get Current Quote
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"status": "error", "message": f"Cannot get price quote for {symbol}"}

    action_upper = action.upper()
    entry_price = tick.ask if action_upper == "BUY" else tick.bid

    # 3. Calculate TP if not provided
    sl_dist = abs(entry_price - sl_price)
    if sl_dist <= 0:
        return {"status": "error", "message": "Stop Loss price cannot equal entry price"}

    if tp_price is None or tp_price <= 0:
        if action_upper == "BUY":
            tp_price = round(entry_price + (sl_dist * rr_ratio), 5)
        else:
            tp_price = round(entry_price - (sl_dist * rr_ratio), 5)

    # 4. Calculate Risk-Weighted Lot Size
    lot_res = calculate_lot_size(
        symbol=symbol,
        entry_price=entry_price,
        stop_loss_price=sl_price,
        take_profit_price=tp_price,
        risk_percent=risk_percent
    )

    if lot_res.get("status") != "success":
        return {"status": "error", "message": f"Lot calculation failed: {lot_res.get('message')}"}

    base_lot = lot_res.get("recommended_lot", 0.01)

    # 5. Apply Credit Score multiplier
    lot_multiplier = 1.0
    if credit_score.initialized:
        lot_multiplier = credit_score.get_lot_multiplier()

    final_lot = max(0.01, round(base_lot * lot_multiplier, 2))

    # 6. Execute Order
    order_res = place_order(
        symbol=symbol,
        action=action_upper,
        volume=final_lot,
        sl=sl_price,
        tp=tp_price,
        comment=comment
    )

    if order_res.get("status") == "success":
        order_res["smart_details"] = {
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "risk_percent": f"{risk_percent}%",
            "base_lot": base_lot,
            "credit_score_multiplier": lot_multiplier,
            "executed_lot": final_lot,
            "risk_reward": f"1:{rr_ratio}"
        }

    return order_res

def place_bracket_order(
    symbol: str,
    distance_points: float = 200.0,
    volume: float = 0.01,
    sl_points: float = 150.0,
    tp_points: float = 300.0,
    comment: str = "AI_Bracket"
) -> Dict[str, Any]:
    """Place a Straddle Bracket Order (Both BUY_STOP above and SELL_STOP below market price) for breakout/news trading."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if tick is None or info is None:
        return {"status": "error", "message": f"Cannot get symbol info for {symbol}"}

    point = info.point
    dist_price = distance_points * point
    sl_price_dist = sl_points * point
    tp_price_dist = tp_points * point

    # Buy Stop above ask
    buy_price = round(tick.ask + dist_price, info.digits)
    buy_sl = round(buy_price - sl_price_dist, info.digits)
    buy_tp = round(buy_price + tp_price_dist, info.digits)

    # Sell Stop below bid
    sell_price = round(tick.bid - dist_price, info.digits)
    sell_sl = round(sell_price + sl_price_dist, info.digits)
    sell_tp = round(sell_price - tp_price_dist, info.digits)

    res_buy = place_pending_order(symbol, "BUY_STOP", buy_price, volume, buy_sl, buy_tp, comment=f"{comment}_Buy")
    res_sell = place_pending_order(symbol, "SELL_STOP", sell_price, volume, sell_sl, sell_tp, comment=f"{comment}_Sell")

    return {
        "status": "success",
        "symbol": symbol,
        "buy_stop": res_buy,
        "sell_stop": res_sell,
        "message": f"Bracket orders placed: BUY_STOP @ {buy_price} and SELL_STOP @ {sell_price}"
    }

def place_grid_orders(
    symbol: str,
    action: str,
    levels: int = 3,
    step_points: float = 150.0,
    volume_per_order: float = 0.01,
    tp_points: float = 300.0,
    comment: str = "AI_Grid"
) -> Dict[str, Any]:
    """Place DCA/Grid Pending Limit Orders stepping down (for BUY) or stepping up (for SELL) to average into positions."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    action_upper = action.upper()
    if action_upper not in ("BUY", "SELL"):
        return {"status": "error", "message": "Action must be BUY or SELL"}

    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if tick is None or info is None:
        return {"status": "error", "message": f"Cannot get symbol info for {symbol}"}

    point = info.point
    order_type = "BUY_LIMIT" if action_upper == "BUY" else "SELL_LIMIT"
    base_price = tick.bid if action_upper == "BUY" else tick.ask

    results = []
    for i in range(1, levels + 1):
        step = (step_points * i) * point
        price = round(base_price - step if action_upper == "BUY" else base_price + step, info.digits)
        tp = round(price + (tp_points * point) if action_upper == "BUY" else price - (tp_points * point), info.digits)
        sl = 0.0

        res = place_pending_order(
            symbol=symbol,
            order_type=order_type,
            price=price,
            volume=volume_per_order,
            sl=sl,
            tp=tp,
            comment=f"{comment}_L{i}"
        )
        results.append({"level": i, "price": price, "tp": tp, "result": res})

    return {
        "status": "success",
        "symbol": symbol,
        "grid_type": order_type,
        "levels_count": len(results),
        "grid_orders": results
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
        results.append({"ticket": pos.ticket, "symbol": pos.symbol, "profit": pos.profit, "result": res})

    return {
        "status": "success",
        "closed_count": len(results),
        "details": results
    }

def close_profitable_positions(symbol: Optional[str] = None, min_profit_usd: float = 0.0) -> Dict[str, Any]:
    """Close only profitable open positions (floating profit > min_profit_usd) to lock in gains."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None or len(positions) == 0:
        return {"status": "success", "message": "No open positions found", "closed_count": 0}

    profitable = [p for p in positions if p.profit > min_profit_usd]
    if not profitable:
        return {
            "status": "success",
            "message": f"No positions found with profit > ${min_profit_usd:.2f}",
            "closed_count": 0
        }

    results = []
    total_locked_profit = 0.0
    for pos in profitable:
        res = close_position(pos.ticket)
        if res.get("status") == "success":
            total_locked_profit += pos.profit
        results.append({"ticket": pos.ticket, "symbol": pos.symbol, "profit": pos.profit, "result": res})

    return {
        "status": "success",
        "message": f"Closed {len(results)} profitable positions. Total profit locked: ${total_locked_profit:.2f}",
        "closed_count": len(results),
        "total_profit_locked": round(total_locked_profit, 2),
        "details": results
    }

def close_losing_positions(symbol: Optional[str] = None, max_loss_usd: float = 0.0) -> Dict[str, Any]:
    """Close only losing open positions (floating loss < -abs(max_loss_usd)) to cut losses immediately."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None or len(positions) == 0:
        return {"status": "success", "message": "No open positions found", "closed_count": 0}

    threshold = -abs(max_loss_usd)
    losing = [p for p in positions if p.profit < threshold]
    if not losing:
        return {
            "status": "success",
            "message": f"No losing positions found with loss beyond ${abs(max_loss_usd):.2f}",
            "closed_count": 0
        }

    results = []
    total_loss_cut = 0.0
    for pos in losing:
        res = close_position(pos.ticket)
        if res.get("status") == "success":
            total_loss_cut += pos.profit
        results.append({"ticket": pos.ticket, "symbol": pos.symbol, "loss": pos.profit, "result": res})

    return {
        "status": "success",
        "message": f"Cut losses on {len(results)} positions. Total loss: ${total_loss_cut:.2f}",
        "closed_count": len(results),
        "total_loss_cut": round(total_loss_cut, 2),
        "details": results
    }

def close_by_comment(comment_query: str, symbol: Optional[str] = None) -> Dict[str, Any]:
    """Close open positions matching a specific comment / order name tag (e.g. 'AI_SMC', 'Manual', 'Breakout')."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    if not comment_query:
        return {"status": "error", "message": "comment_query is required"}

    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None or len(positions) == 0:
        return {"status": "success", "message": "No open positions found", "closed_count": 0}

    query_lower = comment_query.lower()
    matching = [p for p in positions if query_lower in (p.comment or "").lower()]
    if not matching:
        return {
            "status": "success",
            "message": f"No positions found with comment containing '{comment_query}'",
            "closed_count": 0
        }

    results = []
    for pos in matching:
        res = close_position(pos.ticket)
        results.append({"ticket": pos.ticket, "symbol": pos.symbol, "comment": pos.comment, "profit": pos.profit, "result": res})

    return {
        "status": "success",
        "message": f"Closed {len(results)} positions matching comment '{comment_query}'",
        "closed_count": len(results),
        "details": results
    }

def close_by_magic(magic_number: int, symbol: Optional[str] = None) -> Dict[str, Any]:
    """Close open positions matching a specific Magic Number (Bot ID)."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None or len(positions) == 0:
        return {"status": "success", "message": "No open positions found", "closed_count": 0}

    matching = [p for p in positions if p.magic == magic_number]
    if not matching:
        return {
            "status": "success",
            "message": f"No positions found with Magic Number {magic_number}",
            "closed_count": 0
        }

    results = []
    for pos in matching:
        res = close_position(pos.ticket)
        results.append({"ticket": pos.ticket, "symbol": pos.symbol, "magic": pos.magic, "profit": pos.profit, "result": res})

    return {
        "status": "success",
        "message": f"Closed {len(results)} positions matching Magic Number {magic_number}",
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

def cancel_all_pending_orders(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Cancel all active pending orders (BUY_STOP, SELL_STOP, BUY_LIMIT, SELL_LIMIT) or filter by symbol."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    orders = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
    if orders is None or len(orders) == 0:
        return {"status": "success", "message": "No pending orders to cancel", "cancelled_count": 0}

    results = []
    for ord_item in orders:
        res = cancel_pending_order(ord_item.ticket)
        results.append({"ticket": ord_item.ticket, "symbol": ord_item.symbol, "type": ord_item.type, "result": res})

    return {
        "status": "success",
        "message": f"Cancelled {len(results)} pending orders",
        "cancelled_count": len(results),
        "details": results
    }

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
