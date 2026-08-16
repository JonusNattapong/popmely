import time
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import MetaTrader5 as mt5
from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.agent.position_manager import PositionManager
from popmely.agent.notifier import notifier
from popmely.config import config

logger = logging.getLogger("popmely.bot_engine")

class AutonomousTradingBot:
    """Autonomous AI Trading Agent Engine with strategy evaluation, order execution, and position management."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.symbol = config.DEFAULT_SYMBOL
        self.timeframe = "M15"
        self.strategy = "smc"
        self.scan_interval = 15  # seconds
        self.auto_trade = False  # False = Signal Alert Only, True = Auto-Execute
        self.risk_percent = 1.0
        self.rr_ratio = 2.0
        self.max_open_trades = 2

        self.position_manager = PositionManager()
        
        # Statistics
        self.start_time: Optional[datetime] = None
        self.scan_count = 0
        self.signals_count = 0
        self.trades_executed = 0
        self.last_signal_time: Optional[str] = None
        self.last_candle_time = None

    def start(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
        strategy: str = "smc",
        scan_interval: int = 15,
        auto_trade: bool = False,
        risk_percent: float = 1.0,
        rr_ratio: float = 2.0,
        enable_breakeven: bool = True,
        be_trigger_points: float = 300.0
    ) -> Dict[str, Any]:
        """Start the autonomous trading worker in background."""
        if self._running:
            return {"status": "warning", "message": "Bot is already running", "status_info": self.get_status()}

        if not MT5ConnectionManager.ensure_connected():
            return {"status": "error", "message": "Cannot connect to MT5"}

        self.symbol = symbol
        self.timeframe = timeframe
        self.strategy = strategy
        self.scan_interval = max(5, scan_interval)
        self.auto_trade = auto_trade
        self.risk_percent = risk_percent
        self.rr_ratio = rr_ratio

        self.position_manager.enable_be = enable_breakeven
        self.position_manager.be_trigger_points = be_trigger_points

        self._running = True
        self.start_time = datetime.now()
        self.scan_count = 0
        self.signals_count = 0
        self.trades_executed = 0

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        mode_str = "AUTO-TRADE" if auto_trade else "SIGNAL-ONLY"
        logger.info(f"Autonomous Trading Agent started for {symbol} ({timeframe}) in {mode_str} mode.")

        return {
            "status": "success",
            "message": f"Agent started successfully in {mode_str} mode",
            "config": {
                "symbol": symbol,
                "timeframe": timeframe,
                "strategy": strategy,
                "mode": mode_str,
                "risk_percent": f"{risk_percent}%",
                "rr_ratio": f"1:{rr_ratio}",
                "scan_interval": f"{self.scan_interval}s"
            }
        }

    def stop(self) -> Dict[str, Any]:
        """Stop the autonomous trading agent worker."""
        if not self._running:
            return {"status": "warning", "message": "Bot is not running"}

        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

        logger.info("Autonomous Trading Agent stopped.")
        return {"status": "success", "message": "Bot stopped successfully", "summary": self.get_status()}

    def get_status(self) -> Dict[str, Any]:
        """Get current live status of the autonomous agent."""
        uptime = str(datetime.now() - self.start_time).split(".")[0] if self.start_time and self._running else "00:00:00"
        return {
            "running": self._running,
            "mode": "AUTO-TRADE" if self.auto_trade else "SIGNAL-ONLY",
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "strategy": self.strategy,
            "uptime": uptime,
            "scan_count": self.scan_count,
            "signals_generated": self.signals_count,
            "trades_executed": self.trades_executed,
            "last_signal_time": self.last_signal_time,
            "risk_percent": self.risk_percent,
            "rr_ratio": self.rr_ratio
        }

    def _run_loop(self):
        """Internal background loop running every scan_interval."""
        while self._running:
            try:
                self.scan_count += 1
                self._process_cycle()
            except Exception as e:
                logger.error(f"Error in bot execution loop: {e}", exc_info=True)

            for _ in range(self.scan_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _process_cycle(self):
        """Single scan and evaluation cycle."""
        if not MT5ConnectionManager.ensure_connected():
            return

        # 1. Manage open positions (Auto Breakeven / Trailing Stop)
        self.position_manager.process_positions()

        # 2. Check max open trades limit
        positions = mt5.positions_get(symbol=self.symbol)
        curr_positions_count = len(positions) if positions else 0
        if curr_positions_count >= self.max_open_trades:
            return

        # 3. Fetch recent candles
        from popmely.tools.market_data import TIMEFRAME_MAP
        from popmely.tools.risk import calculate_lot_size
        from popmely.tools.trading import place_order
        import pandas as pd

        tf = TIMEFRAME_MAP.get(self.timeframe.upper(), mt5.TIMEFRAME_M15)
        rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, 80)
        if rates is None or len(rates) < 40:
            return

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        latest_candle_time = df['time'].iloc[-1]

        # Evaluate strategy
        signal = self._evaluate_strategy(df)
        if signal and signal.get("action") and (self.last_candle_time != latest_candle_time):
            self.last_candle_time = latest_candle_time
            self.signals_count += 1
            self.last_signal_time = str(latest_candle_time)

            action = signal["action"]
            entry_p = signal["entry_price"]
            sl_p = signal["sl"]
            tp_p = signal["tp"]
            strat_name = signal["strategy"]
            reason = signal.get("reason", "")

            # Calculate Lot Size
            lot_res = calculate_lot_size(
                symbol=self.symbol,
                entry_price=entry_p,
                stop_loss_price=sl_p,
                take_profit_price=tp_p,
                risk_percent=self.risk_percent
            )
            lot = lot_res.get("recommended_lot", 0.01) if lot_res.get("status") == "success" else 0.01

            # Send Notification
            notifier.notify_signal(
                symbol=self.symbol,
                action=action,
                price=entry_p,
                sl=sl_p,
                tp=tp_p,
                strategy=strat_name,
                lot=lot,
                reason=reason
            )

            # Auto Execute Order if enabled
            if self.auto_trade:
                order_res = place_order(
                    symbol=self.symbol,
                    action=action,
                    volume=lot,
                    sl=sl_p,
                    tp=tp_p,
                    comment=f"AI_{strat_name[:8]}"
                )
                if order_res.get("status") == "success":
                    self.trades_executed += 1
                    logger.info(f"Auto Order Executed: {action} {lot} {self.symbol} Ticket #{order_res.get('order_ticket')}")
                else:
                    logger.warning(f"Auto Order Failed: {order_res.get('message')}")

    def _evaluate_strategy(self, df) -> Optional[Dict[str, Any]]:
        """Evaluate strategy and return signal dictionary if triggered."""
        from popmely.tools.smc import find_swings, detect_market_structure, detect_fvgs
        
        swings = find_swings(df, window=2)
        structure = detect_market_structure(df, swings)
        fvgs = detect_fvgs(df)
        
        bias = structure.get("structure")
        close_p = float(df['close'].iloc[-1])

        if bias == "BULLISH":
            active_bull = [f for f in fvgs if f['type'] == 'BULLISH_FVG' and not f['mitigated']]
            if active_bull:
                fvg = active_bull[-1]
                if fvg['bottom'] <= close_p <= fvg['top']:
                    sl = round(fvg['bottom'] - ((fvg['top'] - fvg['bottom']) * 0.5), 5)
                    sl_dist = abs(close_p - sl)
                    if sl_dist > 0:
                        tp = round(close_p + (sl_dist * self.rr_ratio), 5)
                        return {
                            "action": "BUY",
                            "entry_price": close_p,
                            "sl": sl,
                            "tp": tp,
                            "strategy": "SMC_BULLISH_FVG",
                            "reason": f"Bullish BOS confirmed. Price retested unmitigated Bullish FVG [{fvg['bottom']} - {fvg['top']}]."
                        }

        elif bias == "BEARISH":
            active_bear = [f for f in fvgs if f['type'] == 'BEARISH_FVG' and not f['mitigated']]
            if active_bear:
                fvg = active_bear[-1]
                if fvg['bottom'] <= close_p <= fvg['top']:
                    sl = round(fvg['top'] + ((fvg['top'] - fvg['bottom']) * 0.5), 5)
                    sl_dist = abs(sl - close_p)
                    if sl_dist > 0:
                        tp = round(close_p - (sl_dist * self.rr_ratio), 5)
                        return {
                            "action": "SELL",
                            "entry_price": close_p,
                            "sl": sl,
                            "tp": tp,
                            "strategy": "SMC_BEARISH_FVG",
                            "reason": f"Bearish BOS confirmed. Price retested unmitigated Bearish FVG [{fvg['bottom']} - {fvg['top']}]."
                        }

        return None

bot_agent = AutonomousTradingBot()
