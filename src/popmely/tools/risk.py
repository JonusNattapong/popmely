from typing import Dict, Any, Optional
import MetaTrader5 as mt5
from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.config import config

def calculate_lot_size(
    symbol: str = "XAUUSD",
    stop_loss_points: float = 0.0,
    risk_amount_usd: Optional[float] = None,
    risk_percent: Optional[float] = None,
    entry_price: Optional[float] = None,
    stop_loss_price: Optional[float] = None,
    take_profit_price: Optional[float] = None
) -> Dict[str, Any]:
    """Calculate recommended lot size, estimated loss at SL, and risk/reward ratio based on account equity."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    account = mt5.account_info()
    if account is None:
        return {"status": "error", "message": "Failed to get account info"}

    info = mt5.symbol_info(symbol)
    if info is None:
        return {"status": "error", "message": f"Symbol '{symbol}' not found"}

    equity = account.equity
    point = info.point
    tick_size = info.trade_tick_size or point
    tick_value = info.trade_tick_value or 1.0

    if entry_price is not None and stop_loss_price is not None:
        distance = abs(entry_price - stop_loss_price)
        stop_loss_points = distance / point

    if stop_loss_points <= 0:
        return {"status": "error", "message": "Stop loss points or distance must be greater than 0"}

    if risk_amount_usd is not None and risk_amount_usd > 0:
        target_risk_usd = risk_amount_usd
    elif risk_percent is not None and risk_percent > 0:
        target_risk_usd = equity * (risk_percent / 100.0)
    else:
        target_risk_usd = equity * 0.01

    loss_per_lot = (stop_loss_points * point / tick_size) * tick_value
    if loss_per_lot <= 0:
        return {"status": "error", "message": "Unable to calculate loss per lot for this symbol"}

    raw_lot = target_risk_usd / loss_per_lot
    step = info.volume_step or 0.01
    rounded_lot = round(raw_lot / step) * step
    rounded_lot = max(info.volume_min, min(rounded_lot, info.volume_max, config.MAX_LOT_SIZE))
    rounded_lot = round(rounded_lot, 2)

    actual_risk_usd = rounded_lot * loss_per_lot

    rr_ratio = None
    est_profit_usd = None
    if entry_price is not None and take_profit_price is not None:
        tp_distance = abs(take_profit_price - entry_price)
        profit_per_lot = (tp_distance / tick_size) * tick_value
        est_profit_usd = round(rounded_lot * profit_per_lot, 2)
        if actual_risk_usd > 0:
            rr_ratio = round(est_profit_usd / actual_risk_usd, 2)

    return {
        "status": "success",
        "symbol": symbol,
        "recommended_lot": rounded_lot,
        "target_risk_usd": round(target_risk_usd, 2),
        "estimated_loss_usd": round(actual_risk_usd, 2),
        "risk_percent_of_equity": round((actual_risk_usd / equity) * 100, 2),
        "stop_loss_points": round(stop_loss_points, 1),
        "estimated_profit_usd": est_profit_usd,
        "risk_reward_ratio": f"1:{rr_ratio}" if rr_ratio is not None else None,
        "symbol_limits": {
            "min_lot": info.volume_min,
            "max_lot": info.volume_max,
            "step": info.volume_step,
            "max_allowed_config_lot": config.MAX_LOT_SIZE
        }
    }
