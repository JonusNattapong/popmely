"""AI Memory Recall & Emergency Order Revocation Tools for popmely.

Provides:
1. AI Memory & Setup Recall (Similar past setups, Win Rate by strategy, Key lessons)
2. Trade Mistake Recall (Pre-trade safety reflection to prevent recurring errors)
3. Strategy Performance Rankings across history
4. Emergency Order Recall (Undo/cancel recent accidental market order within N seconds)
5. Revoke all pending orders
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import MetaTrader5 as mt5

from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.tools.trading import get_positions, close_position, cancel_all_pending_orders
from popmely.tools.journal import get_trade_journal
from popmely.db import get_trade_notes, get_signal_history, get_backtest_history


# =====================================================================
# 1. AI MEMORY & SETUP RECALL
# =====================================================================

def recall_similar_trades(
    symbol: Optional[str] = "XAUUSD",
    strategy: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Recall past setups matching the symbol or strategy from SQLite memory, summarizing historical win rate, average profit, and AI lessons learned."""
    notes = get_trade_notes(symbol=symbol, days=90, limit=limit * 2)

    if strategy:
        s_lower = strategy.lower()
        notes = [n for n in notes if s_lower in (n.get("strategy") or "").lower() or s_lower in (n.get("tags") or "").lower()]

    matched_notes = notes[:limit]
    
    total_trades = len(matched_notes)
    winning_trades = [n for n in matched_notes if (n.get("profit_usd") or 0.0) > 0]
    losing_trades = [n for n in matched_notes if (n.get("profit_usd") or 0.0) < 0]
    
    win_rate = round((len(winning_trades) / total_trades) * 100, 2) if total_trades > 0 else 0.0
    total_pnl = round(sum(n.get("profit_usd") or 0.0 for n in matched_notes), 2)
    avg_pnl = round(total_pnl / total_trades, 2) if total_trades > 0 else 0.0
    
    # Extract AI reflections/lessons
    lessons = [n.get("ai_reflection") for n in matched_notes if n.get("ai_reflection")]

    return {
        "status": "success",
        "symbol_query": symbol or "ALL",
        "strategy_query": strategy or "ALL",
        "historical_memory_count": total_trades,
        "historical_win_rate": f"{win_rate}%",
        "total_historical_pnl_usd": total_pnl,
        "average_trade_pnl_usd": avg_pnl,
        "winning_setups_count": len(winning_trades),
        "losing_setups_count": len(losing_trades),
        "recalled_lessons": lessons[-5:],
        "recalled_trade_samples": matched_notes[:5]
    }


def recall_trading_mistakes(
    symbol: Optional[str] = None,
    days: int = 30,
    limit: int = 5
) -> Dict[str, Any]:
    """Recall recent losing trades and AI reflections to serve as a pre-trade psychological and risk safety checklist."""
    notes = get_trade_notes(symbol=symbol, days=days, limit=50)
    losing_notes = [n for n in notes if (n.get("profit_usd") or 0.0) < 0]

    recalled_mistakes = []
    for n in losing_notes[:limit]:
        recalled_mistakes.append({
            "ticket": n.get("deal_ticket"),
            "symbol": n.get("symbol"),
            "loss_usd": n.get("profit_usd"),
            "strategy": n.get("strategy") or "Standard",
            "reflection_note": n.get("ai_reflection") or n.get("note"),
            "date": n.get("created_at")
        })

    advice = (
        "💡 Review these past errors before executing new orders: ensure full FVG/Liquidity sweep confirmation and respect Credit Score position sizing."
        if recalled_mistakes else
        "🟢 No recent recorded losses found in this period. Maintain consistent risk discipline."
    )

    return {
        "status": "success",
        "total_losing_trades_recalled": len(losing_notes),
        "pre_trade_safety_advice": advice,
        "recent_mistakes": recalled_mistakes
    }


def recall_strategy_rankings(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Rank historical strategy performance across all recorded setups in SQLite memory."""
    notes = get_trade_notes(symbol=symbol, days=180, limit=200)

    strat_map: Dict[str, List[float]] = {}
    for n in notes:
        strat = n.get("strategy") or "Unspecified"
        profit = n.get("profit_usd") or 0.0
        if strat not in strat_map:
            strat_map[strat] = []
        strat_map[strat].append(profit)

    rankings = []
    for strat, profits in strat_map.items():
        total = len(profits)
        wins = sum(1 for p in profits if p > 0)
        net_profit = round(sum(profits), 2)
        wr = round((wins / total) * 100, 2) if total > 0 else 0.0
        rankings.append({
            "strategy": strat,
            "total_trades": total,
            "win_rate": f"{wr}%",
            "net_profit_usd": net_profit,
            "expectancy_per_trade": round(net_profit / total, 2) if total > 0 else 0.0
        })

    # Sort by Net Profit descending
    rankings.sort(key=lambda x: x["net_profit_usd"], reverse=True)

    return {
        "status": "success",
        "symbol": symbol or "ALL",
        "strategies_evaluated": len(rankings),
        "strategy_rankings": rankings
    }


# =====================================================================
# 2. EMERGENCY ORDER RECALL & UNDO
# =====================================================================

def recall_recent_order(
    symbol: Optional[str] = None,
    max_age_seconds: int = 120
) -> Dict[str, Any]:
    """Emergency Undo Button: Immediately close/recall the most recently opened market position (within max_age_seconds) to reverse an accidental trade."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None or len(positions) == 0:
        return {"status": "warning", "message": "No active open positions to recall"}

    # Sort by open time descending (most recent first)
    sorted_pos = sorted(positions, key=lambda p: p.time, reverse=True)
    latest_pos = sorted_pos[0]

    now_ts = int(datetime.now().timestamp())
    age_seconds = now_ts - latest_pos.time

    if age_seconds > max_age_seconds:
        return {
            "status": "warning",
            "message": f"Most recent position #{latest_pos.ticket} was opened {age_seconds}s ago (exceeds {max_age_seconds}s recall window). Use mt5_close_position to close normally.",
            "ticket": latest_pos.ticket,
            "age_seconds": age_seconds
        }

    # Execute Emergency Close
    res = close_position(latest_pos.ticket)

    return {
        "status": "success" if res.get("status") == "success" else "error",
        "action": "EMERGENCY_ORDER_RECALL",
        "recalled_ticket": latest_pos.ticket,
        "symbol": latest_pos.symbol,
        "type": "BUY" if latest_pos.type == mt5.ORDER_TYPE_BUY else "SELL",
        "volume": latest_pos.volume,
        "age_seconds": age_seconds,
        "close_result": res,
        "message": f"Successfully recalled and closed position #{latest_pos.ticket} ({latest_pos.symbol} {latest_pos.volume} lots) opened {age_seconds}s ago."
    }


def recall_all_pending_orders(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Instantly revoke and cancel all active pending orders across the terminal."""
    return cancel_all_pending_orders(symbol)
