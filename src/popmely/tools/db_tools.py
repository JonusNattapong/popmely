"""MCP Tool wrappers for the popmely Database system."""

from typing import Dict, Any, Optional
import popmely.db as db


def db_add_trade_note(
    symbol: str = "XAUUSD",
    note: str = "",
    deal_ticket: Optional[int] = None,
    order_ticket: Optional[int] = None,
    action: Optional[str] = None,
    volume: Optional[float] = None,
    entry_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    profit_usd: Optional[float] = None,
    strategy: Optional[str] = None,
    tags: Optional[str] = None,
    ai_reflection: Optional[str] = None
) -> Dict[str, Any]:
    """Add a trade journal note with optional deal details, strategy tag, and AI reflection."""
    if not note:
        return {"status": "error", "message": "Note text is required"}

    note_id = db.add_trade_note(
        symbol=symbol, note=note, deal_ticket=deal_ticket,
        order_ticket=order_ticket, action=action, volume=volume,
        entry_price=entry_price, exit_price=exit_price,
        profit_usd=profit_usd, strategy=strategy, tags=tags,
        ai_reflection=ai_reflection
    )

    return {
        "status": "success",
        "note_id": note_id,
        "message": f"Trade note #{note_id} saved to journal for {symbol}"
    }


def db_get_journal_notes(
    symbol: Optional[str] = None,
    deal_ticket: Optional[int] = None,
    days: int = 30,
    limit: int = 50
) -> Dict[str, Any]:
    """Retrieve trade journal notes, optionally filtered by symbol or deal ticket."""
    notes = db.get_trade_notes(symbol=symbol, deal_ticket=deal_ticket, days=days, limit=limit)
    return {
        "status": "success",
        "count": len(notes),
        "notes": notes
    }


def db_get_signal_history(
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """Retrieve bot signal audit history from the database."""
    signals = db.get_signal_history(symbol=symbol, strategy=strategy, limit=limit)
    return {
        "status": "success",
        "count": len(signals),
        "signals": signals
    }


def db_get_backtest_archive(
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Retrieve archived backtest results for comparison and review."""
    results = db.get_backtest_history(symbol=symbol, strategy=strategy, limit=limit)
    return {
        "status": "success",
        "count": len(results),
        "backtest_results": results
    }


def db_stats() -> Dict[str, Any]:
    """Get database file size, location, and row counts for all tables."""
    return db.get_db_stats()
