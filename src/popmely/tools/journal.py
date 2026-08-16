"""Trade Journey & Performance Journal Tool for popmely."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import MetaTrader5 as mt5

from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.utils.formatters import format_deal
from popmely.tools.credit_score import credit_score


def get_trade_journal(days: int = 7, symbol: Optional[str] = None) -> Dict[str, Any]:
    """Generate a comprehensive Trading Journey & Performance Journal combining closed deals, win/loss metrics, R:R analytics, and Credit Score health."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    from_date = datetime.now() - timedelta(days=days)
    to_date = datetime.now()

    if symbol:
        deals = mt5.history_deals_get(from_date, to_date, symbol=symbol)
    else:
        deals = mt5.history_deals_get(from_date, to_date)

    if deals is None:
        return {"status": "error", "message": "Failed to fetch deal history"}

    closing_deals = [format_deal(d) for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]

    total_deals = len(closing_deals)
    winning_deals = [d for d in closing_deals if d["profit"] > 0]
    losing_deals = [d for d in closing_deals if d["profit"] < 0]
    breakeven_deals = [d for d in closing_deals if d["profit"] == 0]

    win_count = len(winning_deals)
    loss_count = len(losing_deals)
    win_rate = round((win_count / total_deals) * 100, 2) if total_deals > 0 else 0.0

    total_profit_usd = round(sum(d["profit"] for d in winning_deals), 2)
    total_loss_usd = round(sum(abs(d["profit"]) for d in losing_deals), 2)
    net_pnl_usd = round(sum(d["profit"] + d["swap"] + d["commission"] + d["fee"] for d in closing_deals), 2)

    profit_factor = round(total_profit_usd / total_loss_usd, 2) if total_loss_usd > 0 else (999.0 if total_profit_usd > 0 else 0.0)
    avg_win = round(total_profit_usd / win_count, 2) if win_count > 0 else 0.0
    avg_loss = round(total_loss_usd / loss_count, 2) if loss_count > 0 else 0.0
    payoff_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0.0

    # Build Trade Journey timeline
    trade_journey = []
    for d in closing_deals:
        outcome = "WIN" if d["profit"] > 0 else "LOSS" if d["profit"] < 0 else "BREAKEVEN"
        trade_journey.append({
            "deal_ticket": d["ticket"],
            "order_ticket": d["order"],
            "symbol": d["symbol"],
            "type": d["type"],
            "volume": d["volume"],
            "close_time": d["time"],
            "outcome": outcome,
            "realized_profit_usd": d["profit"],
            "comment": d["comment"],
            "journey_note": f"{d['symbol']} {d['type']} {d['volume']} lots closed with {outcome} (${d['profit']:+.2f}) | Tag: {d['comment'] or 'Standard'}"
        })

    # AI Behavioral Feedback
    if total_deals == 0:
        ai_reflection = "No closed trades recorded in this period. Ready for high-confluence setups."
    elif win_rate >= 65 and net_pnl_usd > 0:
        ai_reflection = f"Excellent trading discipline. Win rate of {win_rate}% with positive net profit (${net_pnl_usd:.2f}). Keep risk consistent."
    elif win_rate < 50 and net_pnl_usd > 0:
        ai_reflection = f"Good R:R execution. Despite {win_rate}% win rate, positive expectancy and high payoff ratio ({payoff_ratio}) kept portfolio profitable."
    else:
        ai_reflection = f"Drawdown observed. Win rate {win_rate}%. Focus on high-confluence SMC setups (80%+) and allow Credit Score system to protect capital."

    return {
        "status": "success",
        "journal_period": f"Past {days} days ({from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')})",
        "executive_summary": {
            "total_trades": total_deals,
            "win_rate": f"{win_rate}%",
            "net_pnl_usd": net_pnl_usd,
            "profit_factor": profit_factor,
            "payoff_ratio": payoff_ratio,
            "avg_win_usd": avg_win,
            "avg_loss_usd": avg_loss
        },
        "credit_score_governance": credit_score.get_status() if credit_score.initialized else {
            "initialized": False,
            "note": "Initialize via mt5_score_init to enable dynamic risk governance."
        },
        "ai_trade_reflection": ai_reflection,
        "trade_journey_timeline": trade_journey
    }
