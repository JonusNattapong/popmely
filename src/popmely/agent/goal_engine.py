import time
import threading
import logging
from datetime import datetime
import json
from pathlib import Path
from typing import Dict, Any, Optional
import MetaTrader5 as mt5
from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.agent.notifier import notifier
from popmely.config import config
from popmely.tools.trading import execute_rapid_scalp

logger = logging.getLogger("popmely.goal_engine")

class GoalEngine:
    """Autonomous Goal-Driven Trading Engine specifically for Micro-Account Challenges (e.g., $31 to $1000)."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Configuration
        self.symbol = config.DEFAULT_SYMBOL
        self.initial_balance = 31.0
        self.target_balance = 1000.0
        self.scan_interval = 1  # 1 second for rapid scalping
        self.risk_per_trade_usd = 2.0  # Max risk in USD per trade for micro accounts
        
        # Statistics
        self.start_time: Optional[datetime] = None
        self.start_equity = 0.0
        self.current_equity = 0.0
        self.trades_executed = 0
        self.highest_equity = 0.0

    def start(
        self,
        symbol: str = "XAUUSD",
        initial_balance: float = 31.0,
        target_balance: float = 1000.0,
        scan_interval: int = 1,
        risk_per_trade_usd: float = 2.0
    ) -> Dict[str, Any]:
        if self._running:
            return {"status": "warning", "message": "Goal Engine is already running"}

        if not MT5ConnectionManager.ensure_connected():
            return {"status": "error", "message": "Cannot connect to MT5"}

        account_info = mt5.account_info()
        if not account_info:
            return {"status": "error", "message": "Failed to get account info"}

        self.symbol = symbol
        self.initial_balance = initial_balance
        self.target_balance = target_balance
        self.scan_interval = max(1, scan_interval)
        self.risk_per_trade_usd = risk_per_trade_usd

        self.start_equity = account_info.equity
        self.current_equity = self.start_equity
        self.highest_equity = self.start_equity

        self._running = True
        self.start_time = datetime.now()
        self.trades_executed = 0

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        logger.info(f"Goal Engine started for {symbol}. Target: ${target_balance}. Current: ${self.start_equity}")
        
        # Notify start
        notifier.send_alert(f"🚀 Goal Engine Started!\nTarget: ${target_balance}\nStarting Equity: ${self.start_equity}\nSymbol: {symbol}")

        return {
            "status": "success",
            "message": "Goal Engine started",
            "config": {
                "symbol": symbol,
                "initial_balance": initial_balance,
                "target_balance": target_balance,
                "scan_interval": f"{self.scan_interval}s"
            }
        }

    def stop(self) -> Dict[str, Any]:
        if not self._running:
            return {"status": "warning", "message": "Goal Engine is not running"}

        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

        logger.info("Goal Engine stopped.")
        return {"status": "success", "message": "Goal Engine stopped", "summary": self.get_status()}

    def get_status(self) -> Dict[str, Any]:
        uptime = str(datetime.now() - self.start_time).split(".")[0] if self.start_time and self._running else "00:00:00"
        
        # Update equity if connected
        if MT5ConnectionManager.ensure_connected():
            acc = mt5.account_info()
            if acc:
                self.current_equity = acc.equity
                self.highest_equity = max(self.highest_equity, self.current_equity)

        progress_percent = 0.0
        if self.target_balance > self.initial_balance:
            progress_percent = ((self.current_equity - self.initial_balance) / (self.target_balance - self.initial_balance)) * 100.0

        return {
            "running": self._running,
            "symbol": self.symbol,
            "target_balance": self.target_balance,
            "current_equity": self.current_equity,
            "progress_percent": round(progress_percent, 2),
            "highest_equity": self.highest_equity,
            "uptime": uptime,
            "trades_executed": self.trades_executed
        }

    def _write_status_json(self):
        """Write current status to a JSON file for the dashboard to read."""
        try:
            status = self.get_status()
            path = Path.home() / ".popmely" / "challenge.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(status, f)
        except Exception as e:
            logger.error(f"Failed to write challenge JSON: {e}")

    def _run_loop(self):
        while self._running:
            try:
                self._process_cycle()
                self._write_status_json()
            except Exception as e:
                logger.error(f"Error in Goal Engine loop: {e}", exc_info=True)

            for _ in range(self.scan_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _process_cycle(self):
        if not MT5ConnectionManager.ensure_connected():
            return

        # Check account equity to track goal
        acc = mt5.account_info()
        if not acc:
            return
        
        self.current_equity = acc.equity
        self.highest_equity = max(self.highest_equity, self.current_equity)

        if self.current_equity >= self.target_balance:
            logger.info(f"🎉 GOAL REACHED! Equity: ${self.current_equity}")
            notifier.send_alert(f"🎉 GOAL REACHED!\nEquity: ${self.current_equity} >= Target: ${self.target_balance}")
            self._running = False
            return

        # Check max open trades limit
        positions = mt5.positions_get(symbol=self.symbol)
        curr_positions_count = len(positions) if positions else 0
        if curr_positions_count > 0:
            return # Wait for current position to close before opening a new one in scalp mode

        # Calculate dynamic lot size based on equity to compound growth
        base_lot = 0.01
        scaling_factor = max(1.0, self.current_equity / 50.0) 
        target_lot = round(base_lot * scaling_factor, 2)
        max_lot_allowed = round((self.current_equity * 500) / 100000, 2) 
        lot_size = max(0.01, min(target_lot, max(0.01, max_lot_allowed)))

        logger.debug(f"GoalEngine: Scaling Lot Size. Equity=${self.current_equity}, Lot={lot_size}")

        res = execute_rapid_scalp(
            symbol=self.symbol,
            direction="AUTO",
            volume=lot_size,
            sl_points=30.0,
            tp_points=60.0,
            max_spread_points=35.0
        )
        
        if res.get("status") == "success":
            self.trades_executed += 1
            logger.info(f"GoalEngine Rapid Scalp Executed: {res.get('action')} {lot_size} {self.symbol}. Ticket #{res.get('order_ticket')}")
            notifier.send_alert(f"⚡ Challenge Scalp Executed:\n{res.get('action')} {lot_size} {self.symbol}\nTicket: {res.get('order_ticket')}")

goal_engine = GoalEngine()
