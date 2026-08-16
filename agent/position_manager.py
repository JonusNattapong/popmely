import logging
from typing import Dict, Any, List
import MetaTrader5 as mt5
from utils.mt5_connection import MT5ConnectionManager
from utils.formatters import format_position
from agent.notifier import notifier

logger = logging.getLogger("mt5_position_manager")

class PositionManager:
    """Monitors open positions, manages Auto-Breakeven and Trailing Stop."""

    def __init__(self, be_trigger_points: float = 300.0, trail_points: float = 400.0, enable_be: bool = True, enable_trail: bool = False):
        self.be_trigger_points = be_trigger_points
        self.trail_points = trail_points
        self.enable_be = enable_be
        self.enable_trail = enable_trail
        self.breakeven_tickets = set()

    def process_positions(self) -> List[Dict[str, Any]]:
        """Check all open positions and apply BE / Trailing Stop rules."""
        if not MT5ConnectionManager.ensure_connected():
            return []

        positions = mt5.positions_get()
        if positions is None:
            return []

        updates = []
        for pos in positions:
            symbol = pos.symbol
            info = mt5.symbol_info(symbol)
            if info is None:
                continue

            point = info.point
            open_price = pos.price_open
            current_price = pos.price_current
            current_sl = pos.sl
            ticket = pos.ticket
            pos_type = pos.type

            # Calculate profit distance in points
            if pos_type == mt5.ORDER_TYPE_BUY:
                profit_points = (current_price - open_price) / point
                
                # 1. Auto Breakeven check
                if self.enable_be and ticket not in self.breakeven_tickets:
                    if profit_points >= self.be_trigger_points:
                        # Move SL to open_price
                        if current_sl < open_price:
                            res = self._modify_sl(pos, open_price)
                            if res:
                                self.breakeven_tickets.add(ticket)
                                notifier.notify_breakeven(symbol, ticket, open_price, open_price)
                                updates.append({"ticket": ticket, "action": "BREAKEVEN", "new_sl": open_price})

                # 2. Trailing Stop check
                if self.enable_trail:
                    new_trail_sl = round(current_price - (self.trail_points * point), info.digits)
                    if new_trail_sl > open_price and new_trail_sl > current_sl:
                        res = self._modify_sl(pos, new_trail_sl)
                        if res:
                            updates.append({"ticket": ticket, "action": "TRAIL_SL", "new_sl": new_trail_sl})

            elif pos_type == mt5.ORDER_TYPE_SELL:
                profit_points = (open_price - current_price) / point
                
                # 1. Auto Breakeven check
                if self.enable_be and ticket not in self.breakeven_tickets:
                    if profit_points >= self.be_trigger_points:
                        # Move SL to open_price
                        if current_sl == 0.0 or current_sl > open_price:
                            res = self._modify_sl(pos, open_price)
                            if res:
                                self.breakeven_tickets.add(ticket)
                                notifier.notify_breakeven(symbol, ticket, open_price, open_price)
                                updates.append({"ticket": ticket, "action": "BREAKEVEN", "new_sl": open_price})

                # 2. Trailing Stop check
                if self.enable_trail:
                    new_trail_sl = round(current_price + (self.trail_points * point), info.digits)
                    if new_trail_sl < open_price and (current_sl == 0.0 or new_trail_sl < current_sl):
                        res = self._modify_sl(pos, new_trail_sl)
                        if res:
                            updates.append({"ticket": ticket, "action": "TRAIL_SL", "new_sl": new_trail_sl})

        return updates

    def _modify_sl(self, pos: Any, new_sl: float) -> bool:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": float(new_sl),
            "tp": float(pos.tp)
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
