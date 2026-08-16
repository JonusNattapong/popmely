"""
popmely Database Engine (SQLite)
Persistent storage for Credit Score, Trade Journal Notes, Bot Signal Logs, and Backtest Archives.

Database file: ~/.popmely/popmely.db (auto-created on first use)
"""

import os
import sqlite3
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger("popmely.database")

# ---------------------------------------------------------------------------
# Database location: ~/.popmely/popmely.db
# ---------------------------------------------------------------------------
DB_DIR = Path.home() / ".popmely"
DB_PATH = DB_DIR / "popmely.db"


def _get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database, creating it if needed."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database():
    """Initialize the database schema (idempotent - safe to call multiple times)."""
    conn = _get_connection()
    try:
        conn.executescript("""
            -- Credit Score persistent state
            CREATE TABLE IF NOT EXISTS credit_score_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_score REAL NOT NULL DEFAULT 100.0,
                max_score REAL NOT NULL DEFAULT 100.0,
                initial_balance REAL NOT NULL DEFAULT 10000.0,
                base_multiplier REAL NOT NULL DEFAULT 100.0,
                recovery_rate REAL NOT NULL DEFAULT 0.5,
                losing_streak INTEGER NOT NULL DEFAULT 0,
                winning_streak INTEGER NOT NULL DEFAULT 0,
                total_deductions REAL NOT NULL DEFAULT 0.0,
                total_recoveries REAL NOT NULL DEFAULT 0.0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Credit Score event history
            CREATE TABLE IF NOT EXISTS credit_score_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                points_change REAL NOT NULL,
                score_after REAL NOT NULL,
                tier TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Trade Journal Notes (AI + User annotations per trade)
            CREATE TABLE IF NOT EXISTS trade_journal_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_ticket INTEGER,
                order_ticket INTEGER,
                symbol TEXT NOT NULL,
                action TEXT,
                volume REAL,
                entry_price REAL,
                exit_price REAL,
                profit_usd REAL,
                strategy TEXT,
                note TEXT NOT NULL,
                tags TEXT,
                ai_reflection TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Bot Signal Audit Log
            CREATE TABLE IF NOT EXISTS bot_signals_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT,
                strategy TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                direction TEXT,
                entry_price REAL,
                sl_price REAL,
                tp_price REAL,
                confluence_score REAL,
                executed INTEGER NOT NULL DEFAULT 0,
                execution_ticket INTEGER,
                outcome TEXT,
                profit_usd REAL,
                detail TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Backtest Result Archives
            CREATE TABLE IF NOT EXISTS backtest_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                strategy TEXT NOT NULL,
                bars_count INTEGER,
                start_balance REAL,
                final_balance REAL,
                total_trades INTEGER,
                win_rate REAL,
                profit_factor REAL,
                max_drawdown_pct REAL,
                net_profit REAL,
                risk_percent REAL,
                rr_ratio REAL,
                params_json TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Index for fast lookups
            CREATE INDEX IF NOT EXISTS idx_journal_symbol ON trade_journal_notes(symbol);
            CREATE INDEX IF NOT EXISTS idx_journal_ticket ON trade_journal_notes(deal_ticket);
            CREATE INDEX IF NOT EXISTS idx_signals_symbol ON bot_signals_log(symbol);
            CREATE INDEX IF NOT EXISTS idx_signals_created ON bot_signals_log(created_at);
            CREATE INDEX IF NOT EXISTS idx_backtest_symbol ON backtest_history(symbol);
            CREATE INDEX IF NOT EXISTS idx_score_history_created ON credit_score_history(created_at);
        """)
        conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    finally:
        conn.close()


# =========================================================================
# CREDIT SCORE PERSISTENCE
# =========================================================================

def save_credit_score_state(state: Dict[str, Any]):
    """Persist credit score state to DB."""
    conn = _get_connection()
    try:
        conn.execute("""
            INSERT INTO credit_score_state (id, current_score, max_score, initial_balance, base_multiplier,
                recovery_rate, losing_streak, winning_streak, total_deductions, total_recoveries, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                current_score=excluded.current_score,
                max_score=excluded.max_score,
                initial_balance=excluded.initial_balance,
                base_multiplier=excluded.base_multiplier,
                recovery_rate=excluded.recovery_rate,
                losing_streak=excluded.losing_streak,
                winning_streak=excluded.winning_streak,
                total_deductions=excluded.total_deductions,
                total_recoveries=excluded.total_recoveries,
                updated_at=excluded.updated_at
        """, (
            state["current_score"], state["max_score"], state["initial_balance"],
            state["base_multiplier"], state["recovery_rate"],
            state["losing_streak"], state["winning_streak"],
            state["total_deductions"], state["total_recoveries"]
        ))
        conn.commit()
    finally:
        conn.close()


def load_credit_score_state() -> Optional[Dict[str, Any]]:
    """Load persisted credit score state from DB. Returns None if no saved state."""
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM credit_score_state WHERE id = 1").fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        conn.close()


def save_credit_score_event(event_type: str, points_change: float, score_after: float, tier: str, detail: str):
    """Log a credit score event to the DB."""
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO credit_score_history (event_type, points_change, score_after, tier, detail) VALUES (?, ?, ?, ?, ?)",
            (event_type, round(points_change, 2), round(score_after, 2), tier, detail)
        )
        conn.commit()
    finally:
        conn.close()


def get_credit_score_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent credit score history from DB."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM credit_score_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# =========================================================================
# TRADE JOURNAL NOTES
# =========================================================================

def add_trade_note(
    symbol: str,
    note: str,
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
) -> int:
    """Add a trade journal note. Returns the note ID."""
    conn = _get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO trade_journal_notes
                (deal_ticket, order_ticket, symbol, action, volume, entry_price, exit_price,
                 profit_usd, strategy, note, tags, ai_reflection)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (deal_ticket, order_ticket, symbol, action, volume, entry_price, exit_price,
              profit_usd, strategy, note, tags, ai_reflection))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_trade_notes(
    symbol: Optional[str] = None,
    deal_ticket: Optional[int] = None,
    days: int = 30,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get trade journal notes, optionally filtered by symbol or ticket."""
    conn = _get_connection()
    try:
        query = "SELECT * FROM trade_journal_notes WHERE created_at >= datetime('now', ?)"
        params: list = [f"-{days} days"]

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if deal_ticket:
            query += " AND deal_ticket = ?"
            params.append(deal_ticket)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# =========================================================================
# BOT SIGNAL AUDIT LOG
# =========================================================================

def log_bot_signal(
    symbol: str,
    strategy: str,
    signal_type: str,
    direction: Optional[str] = None,
    timeframe: Optional[str] = None,
    entry_price: Optional[float] = None,
    sl_price: Optional[float] = None,
    tp_price: Optional[float] = None,
    confluence_score: Optional[float] = None,
    executed: bool = False,
    execution_ticket: Optional[int] = None,
    detail: Optional[str] = None
) -> int:
    """Log a bot signal to the audit log. Returns the signal ID."""
    conn = _get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO bot_signals_log
                (symbol, timeframe, strategy, signal_type, direction, entry_price, sl_price, tp_price,
                 confluence_score, executed, execution_ticket, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, timeframe, strategy, signal_type, direction, entry_price, sl_price, tp_price,
              confluence_score, 1 if executed else 0, execution_ticket, detail))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_signal_outcome(signal_id: int, outcome: str, profit_usd: float):
    """Update a signal's outcome after the trade closes."""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE bot_signals_log SET outcome = ?, profit_usd = ? WHERE id = ?",
            (outcome, round(profit_usd, 2), signal_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_signal_history(
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get bot signal audit history."""
    conn = _get_connection()
    try:
        query = "SELECT * FROM bot_signals_log WHERE 1=1"
        params: list = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# =========================================================================
# BACKTEST ARCHIVES
# =========================================================================

def save_backtest_result(
    symbol: str, timeframe: str, strategy: str,
    bars_count: int, start_balance: float, final_balance: float,
    total_trades: int, win_rate: float, profit_factor: float,
    max_drawdown_pct: float, net_profit: float,
    risk_percent: float, rr_ratio: float,
    params: Optional[Dict] = None
) -> int:
    """Archive a backtest result. Returns the record ID."""
    conn = _get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO backtest_history
                (symbol, timeframe, strategy, bars_count, start_balance, final_balance,
                 total_trades, win_rate, profit_factor, max_drawdown_pct, net_profit,
                 risk_percent, rr_ratio, params_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, timeframe, strategy, bars_count, start_balance, final_balance,
              total_trades, win_rate, profit_factor, max_drawdown_pct, net_profit,
              risk_percent, rr_ratio, json.dumps(params) if params else None))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_backtest_history(
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Get archived backtest results."""
    conn = _get_connection()
    try:
        query = "SELECT * FROM backtest_history WHERE 1=1"
        params: list = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# =========================================================================
# DATABASE STATISTICS
# =========================================================================

def get_db_stats() -> Dict[str, Any]:
    """Get database file size and row counts for all tables."""
    conn = _get_connection()
    try:
        tables = {
            "credit_score_state": "SELECT COUNT(*) FROM credit_score_state",
            "credit_score_history": "SELECT COUNT(*) FROM credit_score_history",
            "trade_journal_notes": "SELECT COUNT(*) FROM trade_journal_notes",
            "bot_signals_log": "SELECT COUNT(*) FROM bot_signals_log",
            "backtest_history": "SELECT COUNT(*) FROM backtest_history",
        }
        counts = {}
        for table, sql in tables.items():
            counts[table] = conn.execute(sql).fetchone()[0]

        db_size_bytes = os.path.getsize(DB_PATH) if DB_PATH.exists() else 0
        if db_size_bytes >= 1_048_576:
            db_size_str = f"{db_size_bytes / 1_048_576:.2f} MB"
        elif db_size_bytes >= 1024:
            db_size_str = f"{db_size_bytes / 1024:.1f} KB"
        else:
            db_size_str = f"{db_size_bytes} bytes"

        return {
            "status": "success",
            "database_path": str(DB_PATH),
            "database_size": db_size_str,
            "table_row_counts": counts,
            "total_records": sum(counts.values())
        }
    finally:
        conn.close()


# Auto-initialize on import
init_database()
