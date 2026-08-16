import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("popmely.credit_score")

class TradingCreditScore:
    """Trading Credit Score System - Risk management scoring that controls bot behavior based on cumulative SL hits."""

    TIER_GREEN = "GREEN"
    TIER_YELLOW = "YELLOW"
    TIER_ORANGE = "ORANGE"
    TIER_CRITICAL = "CRITICAL"

    def __init__(self):
        self.max_score: float = 100.0
        self.current_score: float = 100.0
        self.initial_balance: float = 10000.0
        self.base_multiplier: float = 100.0
        self.recovery_rate: float = 0.5  # Recovery is slower than deduction
        self.losing_streak: int = 0
        self.winning_streak: int = 0
        self.total_deductions: float = 0.0
        self.total_recoveries: float = 0.0
        self.initialized: bool = False
        self.history: List[Dict[str, Any]] = []

    # ---- Tier Thresholds ----

    def get_tier(self) -> str:
        """Determine current tier based on score percentage."""
        pct = self.get_score_percent()
        if pct >= 70:
            return self.TIER_GREEN
        elif pct >= 50:
            return self.TIER_YELLOW
        elif pct >= 30:
            return self.TIER_ORANGE
        else:
            return self.TIER_CRITICAL

    def get_score_percent(self) -> float:
        """Get score as percentage of max."""
        if self.max_score <= 0:
            return 0.0
        return round((self.current_score / self.max_score) * 100, 2)

    def get_lot_multiplier(self) -> float:
        """Get lot size multiplier based on current tier."""
        tier = self.get_tier()
        if tier == self.TIER_GREEN:
            return 1.0
        elif tier == self.TIER_YELLOW:
            return 0.5
        elif tier == self.TIER_ORANGE:
            return 0.25
        else:  # CRITICAL
            return 0.0  # No trading allowed

    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed based on current score tier."""
        return self.get_tier() != self.TIER_CRITICAL

    # ---- Streak Multiplier ----

    def _get_streak_multiplier(self) -> float:
        """Get penalty multiplier based on consecutive losses."""
        if self.losing_streak <= 2:
            return 1.0
        elif self.losing_streak <= 4:
            return 1.5
        else:
            return 2.0

    # ---- Core Actions ----

    def initialize(self, max_score: float = 100.0, initial_balance: float = 10000.0, base_multiplier: float = 100.0, recovery_rate: float = 0.5) -> Dict[str, Any]:
        """Initialize or reset the credit score system with custom parameters."""
        self.max_score = max(1.0, max_score)
        self.current_score = self.max_score
        self.initial_balance = max(1.0, initial_balance)
        self.base_multiplier = max(1.0, base_multiplier)
        self.recovery_rate = max(0.1, min(1.0, recovery_rate))
        self.losing_streak = 0
        self.winning_streak = 0
        self.total_deductions = 0.0
        self.total_recoveries = 0.0
        self.initialized = True
        self.history = []

        self._log_event("INIT", 0.0, f"Score initialized: {self.max_score} pts, Balance ref: ${self.initial_balance}")

        return self.get_status()

    def deduct(self, loss_usd: float, reason: str = "SL Hit") -> Dict[str, Any]:
        """Deduct points based on loss amount from a Stop Loss hit."""
        if not self.initialized:
            return {"status": "error", "message": "Credit Score not initialized. Call mt5_score_init first."}

        loss_usd = abs(loss_usd)
        if loss_usd <= 0:
            return {"status": "error", "message": "Loss amount must be greater than 0"}

        # Update streaks
        self.losing_streak += 1
        self.winning_streak = 0

        # Calculate deduction
        streak_mult = self._get_streak_multiplier()
        raw_deduction = (loss_usd / self.initial_balance) * self.base_multiplier
        final_deduction = round(raw_deduction * streak_mult, 2)

        old_score = self.current_score
        old_tier = self.get_tier()
        self.current_score = max(0.0, self.current_score - final_deduction)
        new_tier = self.get_tier()
        self.total_deductions += final_deduction

        self._log_event("DEDUCT", -final_deduction,
                        f"{reason} | Loss: ${loss_usd:.2f} | Streak: {self.losing_streak} (x{streak_mult})")

        tier_changed = old_tier != new_tier

        return {
            "status": "success",
            "points_deducted": final_deduction,
            "loss_usd": loss_usd,
            "streak_multiplier": streak_mult,
            "losing_streak": self.losing_streak,
            "score_before": round(old_score, 2),
            "score_after": round(self.current_score, 2),
            "score_percent": self.get_score_percent(),
            "tier": new_tier,
            "tier_changed": tier_changed,
            "tier_change": f"{old_tier} → {new_tier}" if tier_changed else None,
            "trading_allowed": self.is_trading_allowed(),
            "lot_multiplier": self.get_lot_multiplier()
        }

    def recover(self, profit_usd: float) -> Dict[str, Any]:
        """Recover points based on profit from a Take Profit hit."""
        if not self.initialized:
            return {"status": "error", "message": "Credit Score not initialized. Call mt5_score_init first."}

        profit_usd = abs(profit_usd)
        if profit_usd <= 0:
            return {"status": "error", "message": "Profit amount must be greater than 0"}

        # Update streaks
        self.winning_streak += 1
        self.losing_streak = 0

        # Calculate recovery (slower than deduction)
        raw_recovery = (profit_usd / self.initial_balance) * self.base_multiplier * self.recovery_rate
        final_recovery = round(raw_recovery, 2)

        old_score = self.current_score
        old_tier = self.get_tier()
        self.current_score = min(self.max_score, self.current_score + final_recovery)
        new_tier = self.get_tier()
        self.total_recoveries += final_recovery

        self._log_event("RECOVER", +final_recovery,
                        f"TP Hit | Profit: ${profit_usd:.2f} | Win streak: {self.winning_streak}")

        tier_changed = old_tier != new_tier

        return {
            "status": "success",
            "points_recovered": final_recovery,
            "profit_usd": profit_usd,
            "winning_streak": self.winning_streak,
            "score_before": round(old_score, 2),
            "score_after": round(self.current_score, 2),
            "score_percent": self.get_score_percent(),
            "tier": new_tier,
            "tier_changed": tier_changed,
            "tier_change": f"{old_tier} → {new_tier}" if tier_changed else None,
            "trading_allowed": self.is_trading_allowed(),
            "lot_multiplier": self.get_lot_multiplier()
        }

    def reset(self) -> Dict[str, Any]:
        """Reset score back to max without changing configuration."""
        if not self.initialized:
            return {"status": "error", "message": "Credit Score not initialized. Call mt5_score_init first."}

        old_score = self.current_score
        self.current_score = self.max_score
        self.losing_streak = 0
        self.winning_streak = 0
        self._log_event("RESET", self.max_score - old_score, "Manual reset to max score")

        return self.get_status()

    def set_score(self, score: float) -> Dict[str, Any]:
        """Manually set the score to a specific value."""
        if not self.initialized:
            return {"status": "error", "message": "Credit Score not initialized. Call mt5_score_init first."}

        old_score = self.current_score
        self.current_score = max(0.0, min(self.max_score, score))
        diff = self.current_score - old_score
        self._log_event("MANUAL_SET", diff, f"Manually set to {self.current_score}")

        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Get full current status of the credit score system."""
        if not self.initialized:
            return {
                "status": "warning",
                "initialized": False,
                "message": "Credit Score not initialized. Call mt5_score_init to start."
            }

        tier = self.get_tier()
        tier_icons = {
            self.TIER_GREEN: "🟢",
            self.TIER_YELLOW: "🟡",
            self.TIER_ORANGE: "🟠",
            self.TIER_CRITICAL: "🔴"
        }

        return {
            "status": "success",
            "initialized": True,
            "score": {
                "current": round(self.current_score, 2),
                "max": self.max_score,
                "percent": self.get_score_percent(),
                "tier": f"{tier_icons.get(tier, '')} {tier}",
                "tier_raw": tier
            },
            "risk_control": {
                "trading_allowed": self.is_trading_allowed(),
                "lot_multiplier": self.get_lot_multiplier(),
                "lot_adjustment": f"{int(self.get_lot_multiplier() * 100)}% of normal"
            },
            "streaks": {
                "losing_streak": self.losing_streak,
                "winning_streak": self.winning_streak,
                "streak_multiplier": self._get_streak_multiplier()
            },
            "cumulative": {
                "total_deductions": round(self.total_deductions, 2),
                "total_recoveries": round(self.total_recoveries, 2),
                "net_change": round(self.total_recoveries - self.total_deductions, 2)
            },
            "config": {
                "initial_balance": self.initial_balance,
                "base_multiplier": self.base_multiplier,
                "recovery_rate": self.recovery_rate
            }
        }

    def get_history(self, limit: int = 20) -> Dict[str, Any]:
        """Get the score change history log."""
        if not self.initialized:
            return {"status": "error", "message": "Credit Score not initialized."}

        return {
            "status": "success",
            "total_events": len(self.history),
            "recent_events": self.history[-limit:]
        }

    # ---- Internal ----

    def _log_event(self, event_type: str, points_change: float, detail: str):
        """Log a score event to history."""
        self.history.append({
            "time": datetime.now().isoformat(),
            "event": event_type,
            "change": round(points_change, 2),
            "score_after": round(self.current_score, 2),
            "tier": self.get_tier(),
            "detail": detail
        })
        logger.info(f"[CreditScore] {event_type}: {points_change:+.2f} → {self.current_score:.2f} ({self.get_tier()}) | {detail}")


# Singleton instance
credit_score = TradingCreditScore()


# ---- MCP Tool Functions ----

def score_init(max_score: float = 100.0, initial_balance: float = 10000.0, base_multiplier: float = 100.0, recovery_rate: float = 0.5) -> Dict[str, Any]:
    """Initialize the Trading Credit Score system with custom max score and reference balance."""
    return credit_score.initialize(max_score, initial_balance, base_multiplier, recovery_rate)

def score_status() -> Dict[str, Any]:
    """Get current credit score, tier, lot multiplier, streaks, and cumulative stats."""
    return credit_score.get_status()

def score_deduct(loss_usd: float, reason: str = "SL Hit") -> Dict[str, Any]:
    """Deduct points from the credit score based on a trading loss (SL hit). Automatically calculates streak penalties."""
    return credit_score.deduct(loss_usd, reason)

def score_recover(profit_usd: float) -> Dict[str, Any]:
    """Recover points to the credit score based on a trading profit (TP hit)."""
    return credit_score.recover(profit_usd)

def score_reset() -> Dict[str, Any]:
    """Reset credit score back to max without changing configuration."""
    return credit_score.reset()

def score_set(score: float) -> Dict[str, Any]:
    """Manually set the credit score to a specific value (0 to max_score)."""
    return credit_score.set_score(score)

def score_history(limit: int = 20) -> Dict[str, Any]:
    """View the recent score change history log with timestamps and details."""
    return credit_score.get_history(limit)
