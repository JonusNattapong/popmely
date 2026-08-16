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
from popmely.tools.credit_score import credit_score

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
        self._tracked_tickets: set = set()  # Track open order tickets for score deduction/recovery

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
            "rr_ratio": self.rr_ratio,
            "credit_score": credit_score.get_status() if credit_score.initialized else {"initialized": False}
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

        # 2. Track closed orders for credit score deduction/recovery
        self._check_closed_orders()

        # 3. Check credit score - block trading if CRITICAL
        if credit_score.initialized and not credit_score.is_trading_allowed():
            logger.info(f"[CreditScore] CRITICAL tier ({credit_score.get_score_percent()}%) - trading blocked.")
            return

        # 4. Check max open trades limit
        positions = mt5.positions_get(symbol=self.symbol)
        curr_positions_count = len(positions) if positions else 0
        if curr_positions_count >= self.max_open_trades:
            return

        # Track current open tickets for later close detection
        if positions:
            for pos in positions:
                self._tracked_tickets.add(pos.ticket)

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

            # Apply credit score lot multiplier
            if credit_score.initialized:
                lot_mult = credit_score.get_lot_multiplier()
                original_lot = lot
                lot = round(lot * lot_mult, 2)
                lot = max(0.01, lot)  # Ensure minimum lot
                if lot_mult < 1.0:
                    logger.info(f"[CreditScore] Lot adjusted: {original_lot} × {lot_mult} = {lot} (Tier: {credit_score.get_tier()})")

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

    def _check_closed_orders(self):
        """Check if any tracked orders have been closed and update credit score accordingly."""
        if not credit_score.initialized or not self._tracked_tickets:
            return

        try:
            from datetime import timedelta
            # Check recent deal history (last 24 hours)
            now = datetime.now()
            since = now - timedelta(hours=24)
            since_ts = int(since.timestamp())
            now_ts = int(now.timestamp())

            deals = mt5.history_deals_get(since_ts, now_ts)
            if not deals:
                return

            for deal in deals:
                # Only process deals we haven't seen and that are OUT (closing deals)
                if deal.ticket in self._tracked_tickets:
                    continue
                if deal.entry != 1:  # 1 = DEAL_ENTRY_OUT (closing a position)
                    continue
                if deal.symbol != self.symbol:
                    continue

                # Check if this is a closure of one of our tracked positions
                if deal.position_id not in self._tracked_tickets:
                    continue

                profit = deal.profit
                self._tracked_tickets.discard(deal.position_id)
                self._tracked_tickets.add(deal.ticket)  # Mark this deal as processed

                if profit < 0:
                    # Loss - likely SL hit
                    result = credit_score.deduct(abs(profit), reason=f"SL Hit on {deal.symbol} (Deal #{deal.ticket})")
                    logger.info(f"[CreditScore] Deducted for loss ${abs(profit):.2f}: {result.get('score_after', '?')} pts ({result.get('tier', '?')})")

                    # Send notification if tier changed or critical
                    if result.get("tier_changed"):
                        tier_msg = f"⚠️ Credit Score Tier Changed: {result.get('tier_change')}\nScore: {result.get('score_after')}/{credit_score.max_score} ({result.get('score_percent')}%)"
                        if result.get("tier") == "CRITICAL":
                            tier_msg = f"🔴 CRITICAL: Trading has been STOPPED!\nScore: {result.get('score_after')}/{credit_score.max_score} ({result.get('score_percent')}%)\nReset required to resume trading."
                        notifier.send_alert(tier_msg)

                elif profit > 0:
                    # Profit - likely TP hit
                    result = credit_score.recover(profit)
                    logger.info(f"[CreditScore] Recovered for profit ${profit:.2f}: {result.get('score_after', '?')} pts ({result.get('tier', '?')})")

                    if result.get("tier_changed"):
                        tier_msg = f"✅ Credit Score Recovered: {result.get('tier_change')}\nScore: {result.get('score_after')}/{credit_score.max_score} ({result.get('score_percent')}%)"
                        notifier.send_alert(tier_msg)

        except Exception as e:
            logger.error(f"[CreditScore] Error checking closed orders: {e}")

bot_agent = AutonomousTradingBot()
