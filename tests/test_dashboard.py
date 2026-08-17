"""Tests for the local data dashboard.

Self-contained: builds a throwaway SQLite database in a temp dir, so these run
without MetaTrader 5 and never touch ~/.popmely/popmely.db.
"""

import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer

from popmely.dashboard import queries
from popmely.dashboard.server import DashboardHandler

SCHEMA = """
CREATE TABLE credit_score_state (
    id INTEGER PRIMARY KEY CHECK (id = 1), current_score REAL, max_score REAL,
    initial_balance REAL, base_multiplier REAL, recovery_rate REAL,
    losing_streak INTEGER, winning_streak INTEGER, total_deductions REAL,
    total_recoveries REAL, updated_at TEXT);
CREATE TABLE credit_score_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, points_change REAL,
    score_after REAL, tier TEXT, detail TEXT, created_at TEXT);
CREATE TABLE trade_journal_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, deal_ticket INTEGER, order_ticket INTEGER,
    symbol TEXT, action TEXT, volume REAL, entry_price REAL, exit_price REAL,
    profit_usd REAL, strategy TEXT, note TEXT, tags TEXT, ai_reflection TEXT, created_at TEXT);
CREATE TABLE bot_signals_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, timeframe TEXT, strategy TEXT,
    signal_type TEXT, direction TEXT, entry_price REAL, sl_price REAL, tp_price REAL,
    confluence_score REAL, executed INTEGER, execution_ticket INTEGER, outcome TEXT,
    profit_usd REAL, detail TEXT, created_at TEXT);
CREATE TABLE backtest_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, timeframe TEXT, strategy TEXT,
    bars_count INTEGER, start_balance REAL, final_balance REAL, total_trades INTEGER,
    win_rate REAL, profit_factor REAL, max_drawdown_pct REAL, net_profit REAL,
    risk_percent REAL, rr_ratio REAL, params_json TEXT, created_at TEXT);
"""


def build_db(path: Path, score: float = 45.0):
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO credit_score_state VALUES (1,?,100.0,10000.0,100.0,0.5,3,0,55.0,0.0,'2026-08-16 10:00:00')",
        (score,))
    conn.executemany(
        "INSERT INTO credit_score_history (event_type,points_change,score_after,tier,detail,created_at)"
        " VALUES (?,?,?,?,?,?)",
        [("INIT", 0.0, 100.0, "GREEN", "init", "2026-08-16 10:00:00"),
         ("DEDUCT", -55.0, score, "ORANGE", "SL Hit", "2026-08-16 10:05:00")])
    conn.executemany(
        "INSERT INTO bot_signals_log (symbol,timeframe,strategy,signal_type,direction,entry_price,"
        "sl_price,tp_price,confluence_score,executed,outcome,profit_usd,created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [("XAUUSD", "M15", "smc_fvg", "BUY", "BUY", 1.0, 0.9, 1.2, 80.0, 1, "WIN", 120.0, "2026-08-16 10:01:00"),
         ("XAUUSD", "M15", "smc_fvg", "SELL", "SELL", 1.0, 1.1, 0.8, 60.0, 1, "LOSS", -40.0, "2026-08-16 10:02:00"),
         ("BTCUSD", "H1", "breakout", "BUY", "BUY", 1.0, 0.9, 1.2, 70.0, 0, None, None, "2026-08-16 10:03:00")])
    conn.execute(
        "INSERT INTO trade_journal_notes (symbol,profit_usd,note,created_at)"
        " VALUES ('XAUUSD',72.5,'test note','2026-08-16 10:04:00')")
    conn.execute(
        "INSERT INTO backtest_history (symbol,timeframe,strategy,bars_count,start_balance,final_balance,"
        "total_trades,win_rate,profit_factor,max_drawdown_pct,net_profit,risk_percent,rr_ratio,created_at)"
        " VALUES ('XAUUSD','M15','smc_fvg',500,10000,11000,14,57.14,2.68,2.97,1000,1.0,2.0,'2026-08-16 10:05:00')")
    conn.commit()
    conn.close()


class TestDashboardQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "popmely.db"
        build_db(cls.db)
        cls.payload = queries.collect(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_status_success(self):
        self.assertEqual(self.payload["status"], "success")

    def test_tier_derived_from_percent(self):
        cs = self.payload["credit_score"]
        self.assertEqual(cs["percent"], 45.0)
        self.assertEqual(cs["tier"], "ORANGE")
        self.assertEqual(cs["lot_multiplier"], 0.25)
        self.assertTrue(cs["trading_allowed"])

    def test_critical_tier_halts_trading(self):
        db = Path(self.tmp.name) / "critical.db"
        build_db(db, score=12.0)
        cs = queries.collect(db)["credit_score"]
        self.assertEqual(cs["tier"], "CRITICAL")
        self.assertEqual(cs["lot_multiplier"], 0.0)
        self.assertFalse(cs["trading_allowed"])

    def test_signal_aggregates(self):
        sig = self.payload["signals"]
        self.assertEqual(sig["total"], 3)
        self.assertEqual(sig["executed"], 2)
        self.assertEqual((sig["wins"], sig["losses"], sig["pending"]), (1, 1, 1))
        self.assertEqual(sig["win_rate"], 50.0)   # pending rows excluded from the rate
        self.assertEqual(sig["profit_usd"], 80.0)
        self.assertEqual(len(sig["by_strategy"]), 2)

    def test_journal_and_backtests(self):
        self.assertEqual(self.payload["journal"]["profit_usd"], 72.5)
        self.assertEqual(self.payload["backtests"]["total"], 1)
        self.assertEqual(self.payload["backtests"]["avg_win_rate"], 57.1)

    def test_database_meta(self):
        db = self.payload["database"]
        self.assertEqual(db["total_records"], 8)
        self.assertIn("KB", db["size"] + " KB")

    def test_missing_database_is_an_empty_state_not_an_error(self):
        res = queries.collect(Path(self.tmp.name) / "nope.db")
        self.assertEqual(res["status"], "empty")
        self.assertIn("No database found", res["error"])

    def test_collect_does_not_create_a_database(self):
        ghost = Path(self.tmp.name) / "ghost.db"
        queries.collect(ghost)
        self.assertFalse(ghost.exists())


class TestDashboardServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "popmely.db"
        build_db(cls.db)
        handler = type("TestHandler", (DashboardHandler,), {"db_path": cls.db})
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.url = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def _get(self, path):
        with urllib.request.urlopen(f"{self.url}{path}", timeout=5) as r:
            return r.status, r.read()

    def test_index_served(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Trading Data Dashboard", body)

    def test_static_assets_served(self):
        for asset in ("/static/dashboard.css", "/static/dashboard.js"):
            status, body = self._get(asset)
            self.assertEqual(status, 200)
            self.assertTrue(body)

    def test_api_data_reflects_the_bound_database(self):
        status, body = self._get("/api/data")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["signals"]["total"], 3)

    def test_unknown_path_404s(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/secrets")
        self.assertEqual(ctx.exception.code, 404)

    def test_static_path_traversal_blocked(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/static/%2e%2e%2f%2e%2e%2fconfig.py")
        self.assertIn(ctx.exception.code, (403, 404))


if __name__ == "__main__":
    unittest.main()
