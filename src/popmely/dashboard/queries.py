"""Read-only query layer for the popmely dashboard.

Reads ~/.popmely/popmely.db directly (SELECT only) and shapes it into the JSON
payload the browser renders. Deliberately does NOT import popmely.db: that module
auto-initializes the schema on import, and the dashboard must never write to or
create the trading database.
"""

import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("popmely.dashboard.queries")

DB_DIR = Path.home() / ".popmely"
DB_PATH = DB_DIR / "popmely.db"

# Mirrors TradingCreditScore in popmely.tools.credit_score - kept in sync by hand
# because importing that module pulls in the MT5 runtime, which the dashboard
# does not require.
TIERS = [
    # (min_percent, tier, lot_multiplier, status_role)
    (70.0, "GREEN", 1.0, "good"),
    (50.0, "YELLOW", 0.5, "warning"),
    (30.0, "ORANGE", 0.25, "serious"),
    (0.0, "CRITICAL", 0.0, "critical"),
]


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open the database read-only, falling back to a normal connection.

    The read-only URI is the preferred path, but SQLite cannot open a WAL
    database read-only when the -shm file is absent (no prior writer this boot),
    so fall back rather than showing the user an empty dashboard.
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    except sqlite3.OperationalError as e:
        logger.debug(f"Read-only open failed ({e}); retrying read-write (SELECT only)")
        conn = sqlite3.connect(str(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Run a SELECT and return plain dicts. A missing table yields []."""
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except sqlite3.OperationalError as e:
        logger.warning(f"Query failed ({e}): {sql.strip().splitlines()[0]}")
        return []


def _one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    rows = _rows(conn, sql, params)
    return rows[0] if rows else None


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = _one(conn, f"SELECT COUNT(*) AS n FROM {table}")
    return int(row["n"]) if row else 0


def _tier_for(percent: float) -> Dict[str, Any]:
    for min_pct, tier, mult, role in TIERS:
        if percent >= min_pct:
            return {"tier": tier, "lot_multiplier": mult, "status": role}
    return {"tier": "CRITICAL", "lot_multiplier": 0.0, "status": "critical"}


def _format_bytes(n: int) -> str:
    if n >= 1_048_576:
        return f"{n / 1_048_576:.2f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} bytes"


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _credit_score(conn: sqlite3.Connection) -> Dict[str, Any]:
    state = _one(conn, "SELECT * FROM credit_score_state WHERE id = 1")
    history = _rows(conn, """
        SELECT id, event_type, points_change, score_after, tier, detail, created_at
        FROM credit_score_history ORDER BY id ASC
    """)

    if state is None:
        return {
            "initialized": False,
            "history": history,
            "message": "Credit Score has not been initialized yet (run mt5_score_init).",
        }

    max_score = state["max_score"] or 100.0
    percent = round((state["current_score"] / max_score) * 100, 2) if max_score > 0 else 0.0
    tier = _tier_for(percent)

    return {
        "initialized": True,
        "current_score": round(state["current_score"], 2),
        "max_score": max_score,
        "percent": percent,
        "tier": tier["tier"],
        "status": tier["status"],
        "lot_multiplier": tier["lot_multiplier"],
        "trading_allowed": tier["tier"] != "CRITICAL",
        "losing_streak": state["losing_streak"],
        "winning_streak": state["winning_streak"],
        "total_deductions": round(state["total_deductions"], 2),
        "total_recoveries": round(state["total_recoveries"], 2),
        "net_change": round(state["total_recoveries"] - state["total_deductions"], 2),
        "initial_balance": state["initial_balance"],
        "updated_at": state["updated_at"],
        "history": history,
    }


def _signals(conn: sqlite3.Connection, limit: int = 50) -> Dict[str, Any]:
    recent = _rows(conn, """
        SELECT id, symbol, timeframe, strategy, signal_type, direction, entry_price,
               sl_price, tp_price, confluence_score, executed, execution_ticket,
               outcome, profit_usd, detail, created_at
        FROM bot_signals_log ORDER BY id DESC LIMIT ?
    """, (limit,))

    by_strategy = _rows(conn, """
        SELECT strategy,
               COUNT(*) AS total,
               SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) AS executed,
               SUM(CASE WHEN UPPER(COALESCE(outcome, '')) = 'WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN UPPER(COALESCE(outcome, '')) = 'LOSS' THEN 1 ELSE 0 END) AS losses,
               COALESCE(SUM(profit_usd), 0) AS profit_usd
        FROM bot_signals_log GROUP BY strategy ORDER BY total DESC, strategy ASC
    """)

    by_symbol = _rows(conn, """
        SELECT symbol, COUNT(*) AS total, COALESCE(SUM(profit_usd), 0) AS profit_usd
        FROM bot_signals_log GROUP BY symbol ORDER BY total DESC, symbol ASC
    """)

    totals = _one(conn, """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) AS executed,
               SUM(CASE WHEN UPPER(COALESCE(outcome, '')) = 'WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN UPPER(COALESCE(outcome, '')) = 'LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN outcome IS NULL OR outcome = '' THEN 1 ELSE 0 END) AS pending,
               COALESCE(SUM(profit_usd), 0) AS profit_usd,
               AVG(confluence_score) AS avg_confluence
        FROM bot_signals_log
    """) or {}

    wins = int(totals.get("wins") or 0)
    losses = int(totals.get("losses") or 0)
    decided = wins + losses

    return {
        "total": int(totals.get("total") or 0),
        "executed": int(totals.get("executed") or 0),
        "wins": wins,
        "losses": losses,
        "pending": int(totals.get("pending") or 0),
        "win_rate": round((wins / decided) * 100, 1) if decided else None,
        "profit_usd": round(float(totals.get("profit_usd") or 0), 2),
        "avg_confluence": round(float(totals["avg_confluence"]), 1) if totals.get("avg_confluence") is not None else None,
        "by_strategy": by_strategy,
        "by_symbol": by_symbol,
        "recent": recent,
    }


def _journal(conn: sqlite3.Connection, limit: int = 50) -> Dict[str, Any]:
    recent = _rows(conn, """
        SELECT id, deal_ticket, symbol, action, volume, entry_price, exit_price,
               profit_usd, strategy, note, tags, ai_reflection, created_at
        FROM trade_journal_notes ORDER BY id DESC LIMIT ?
    """, (limit,))

    totals = _one(conn, """
        SELECT COUNT(*) AS total,
               COALESCE(SUM(profit_usd), 0) AS profit_usd,
               SUM(CASE WHEN profit_usd > 0 THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN profit_usd < 0 THEN 1 ELSE 0 END) AS losses
        FROM trade_journal_notes
    """) or {}

    wins = int(totals.get("wins") or 0)
    losses = int(totals.get("losses") or 0)
    decided = wins + losses

    return {
        "total": int(totals.get("total") or 0),
        "profit_usd": round(float(totals.get("profit_usd") or 0), 2),
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / decided) * 100, 1) if decided else None,
        "recent": recent,
    }


def _backtests(conn: sqlite3.Connection, limit: int = 25) -> Dict[str, Any]:
    recent = _rows(conn, """
        SELECT id, symbol, timeframe, strategy, bars_count, start_balance, final_balance,
               total_trades, win_rate, profit_factor, max_drawdown_pct, net_profit,
               risk_percent, rr_ratio, created_at
        FROM backtest_history ORDER BY id DESC LIMIT ?
    """, (limit,))

    totals = _one(conn, """
        SELECT COUNT(*) AS total,
               AVG(win_rate) AS avg_win_rate,
               AVG(profit_factor) AS avg_profit_factor,
               MAX(max_drawdown_pct) AS worst_drawdown,
               COALESCE(SUM(net_profit), 0) AS net_profit
        FROM backtest_history
    """) or {}

    def _r(key: str, digits: int = 2):
        val = totals.get(key)
        return round(float(val), digits) if val is not None else None

    return {
        "total": int(totals.get("total") or 0),
        "avg_win_rate": _r("avg_win_rate", 1),
        "avg_profit_factor": _r("avg_profit_factor"),
        "worst_drawdown": _r("worst_drawdown"),
        "net_profit": _r("net_profit"),
        "recent": recent,
    }


def _database(conn: sqlite3.Connection, db_path: Path) -> Dict[str, Any]:
    tables = [
        "credit_score_state", "credit_score_history", "trade_journal_notes",
        "bot_signals_log", "backtest_history",
    ]
    counts = {t: _count(conn, t) for t in tables}
    size = os.path.getsize(db_path) if db_path.exists() else 0
    return {
        "path": str(db_path),
        "size_bytes": size,
        "size": _format_bytes(size),
        "table_row_counts": counts,
        "total_records": sum(counts.values()),
    }


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def collect(db_path: Path = DB_PATH) -> Dict[str, Any]:
    """Build the full dashboard payload. Never raises - errors ride in the payload."""
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    if not db_path.exists():
        return {
            "status": "empty",
            "generated_at": generated_at,
            "error": (
                f"No database found at {db_path}. It is created the first time a "
                f"popmely tool writes to it (e.g. mt5_score_init)."
            ),
            "database": {"path": str(db_path), "size": "0 bytes", "table_row_counts": {}, "total_records": 0},
        }

    conn = _connect(db_path)
    try:
        return {
            "status": "success",
            "generated_at": generated_at,
            "credit_score": _credit_score(conn),
            "signals": _signals(conn),
            "journal": _journal(conn),
            "backtests": _backtests(conn),
            "database": _database(conn, db_path),
        }
    except Exception as e:  # surfaced in the UI banner rather than a 500 page
        logger.exception("Dashboard payload collection failed")
        return {"status": "error", "generated_at": generated_at, "error": str(e)}
    finally:
        conn.close()
