from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import MetaTrader5 as mt5
from utils.mt5_connection import MT5ConnectionManager
from mcp_tools.market_data import TIMEFRAME_MAP

def find_swings(df: pd.DataFrame, window: int = 3) -> List[Dict[str, Any]]:
    """Identify swing highs and swing lows."""
    swings = []
    highs = df['high'].values
    lows = df['low'].values
    times = df['time'].values

    for i in range(window, len(df) - window):
        # Swing High
        if all(highs[i] >= highs[i - j] for j in range(1, window + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, window + 1)):
            swings.append({
                "index": i,
                "type": "HIGH",
                "price": round(float(highs[i]), 5),
                "time": str(times[i])
            })
        # Swing Low
        elif all(lows[i] <= lows[i - j] for j in range(1, window + 1)) and \
             all(lows[i] <= lows[i + j] for j in range(1, window + 1)):
            swings.append({
                "index": i,
                "type": "LOW",
                "price": round(float(lows[i]), 5),
                "time": str(times[i])
            })

    return swings

def detect_market_structure(df: pd.DataFrame, swings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Detect BOS (Break of Structure), CHoCH (Change of Character), and current market structure."""
    if len(swings) < 4:
        return {"structure": "UNDETERMINED", "last_event": None, "recent_events": []}

    events = []
    current_trend = "NEUTRAL"
    last_high = None
    last_low = None

    for s in swings:
        if s["type"] == "HIGH":
            if last_high is not None:
                if s["price"] > last_high["price"]:
                    if current_trend == "BEARISH":
                        events.append({"type": "CHoCH_BULLISH", "price": s["price"], "time": s["time"]})
                        current_trend = "BULLISH"
                    else:
                        events.append({"type": "BOS_BULLISH", "price": s["price"], "time": s["time"]})
                        current_trend = "BULLISH"
            last_high = s
        elif s["type"] == "LOW":
            if last_low is not None:
                if s["price"] < last_low["price"]:
                    if current_trend == "BULLISH":
                        events.append({"type": "CHoCH_BEARISH", "price": s["price"], "time": s["time"]})
                        current_trend = "BEARISH"
                    else:
                        events.append({"type": "BOS_BEARISH", "price": s["price"], "time": s["time"]})
                        current_trend = "BEARISH"
            last_low = s

    last_event = events[-1] if events else None
    return {
        "structure": current_trend,
        "last_event": last_event,
        "recent_events": events[-5:]
    }

def detect_fvgs(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Detect Fair Value Gaps (FVG) and track if they are mitigated."""
    fvgs = []
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    times = df['time'].values
    n = len(df)

    for i in range(len(df) - 2):
        # Bullish FVG: Low of candle i+2 > High of candle i
        if lows[i + 2] > highs[i]:
            gap_bottom = highs[i]
            gap_top = lows[i + 2]
            # Check mitigation by subsequent candles
            mitigated = any(lows[k] <= gap_bottom for k in range(i + 3, n))
            partially_filled = any(lows[k] < gap_top for k in range(i + 3, n))
            fvgs.append({
                "type": "BULLISH_FVG",
                "top": round(float(gap_top), 5),
                "bottom": round(float(gap_bottom), 5),
                "size": round(float(gap_top - gap_bottom), 5),
                "time": str(times[i + 1]),
                "mitigated": bool(mitigated),
                "partially_filled": bool(partially_filled)
            })

        # Bearish FVG: High of candle i+2 < Low of candle i
        elif highs[i + 2] < lows[i]:
            gap_top = lows[i]
            gap_bottom = highs[i + 2]
            mitigated = any(highs[k] >= gap_top for k in range(i + 3, n))
            partially_filled = any(highs[k] > gap_bottom for k in range(i + 3, n))
            fvgs.append({
                "type": "BEARISH_FVG",
                "top": round(float(gap_top), 5),
                "bottom": round(float(gap_bottom), 5),
                "size": round(float(gap_top - gap_bottom), 5),
                "time": str(times[i + 1]),
                "mitigated": bool(mitigated),
                "partially_filled": bool(partially_filled)
            })

    return fvgs

def detect_order_blocks(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Detect Order Blocks (OB) created prior to strong displacement moves."""
    obs = []
    opens = df['open'].values
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    times = df['time'].values
    n = len(df)

    for i in range(1, len(df) - 2):
        # Bullish OB: Bearish candle (close < open) followed by a strong bullish move that breaks prior high
        if closes[i] < opens[i] and closes[i + 1] > opens[i + 1]:
            displacement = (closes[i + 1] - opens[i + 1])
            avg_body = np.mean(np.abs(closes[max(0, i-5):i] - opens[max(0, i-5):i]))
            if displacement > (avg_body * 1.5) and closes[i + 1] > highs[i]:
                top = highs[i]
                bottom = lows[i]
                mitigated = any(lows[k] <= top for k in range(i + 2, n))
                obs.append({
                    "type": "BULLISH_OB",
                    "top": round(float(top), 5),
                    "bottom": round(float(bottom), 5),
                    "time": str(times[i]),
                    "mitigated": bool(mitigated)
                })

        # Bearish OB: Bullish candle (close > open) followed by a strong bearish move
        elif closes[i] > opens[i] and closes[i + 1] < opens[i + 1]:
            displacement = (opens[i + 1] - closes[i + 1])
            avg_body = np.mean(np.abs(closes[max(0, i-5):i] - opens[max(0, i-5):i]))
            if displacement > (avg_body * 1.5) and closes[i + 1] < lows[i]:
                top = highs[i]
                bottom = lows[i]
                mitigated = any(highs[k] >= bottom for k in range(i + 2, n))
                obs.append({
                    "type": "BEARISH_OB",
                    "top": round(float(top), 5),
                    "bottom": round(float(bottom), 5),
                    "time": str(times[i]),
                    "mitigated": bool(mitigated)
                })

    return obs

def calculate_premium_discount(df: pd.DataFrame, swings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate Premium, Discount, Equilibrium (50%), and OTE (Optimal Trade Entry 61.8%-78.6%)."""
    if len(swings) < 2:
        high = float(df['high'].max())
        low = float(df['low'].min())
    else:
        recent_highs = [s['price'] for s in swings if s['type'] == 'HIGH']
        recent_lows = [s['price'] for s in swings if s['type'] == 'LOW']
        high = max(recent_highs[-3:]) if recent_highs else float(df['high'].max())
        low = min(recent_lows[-3:]) if recent_lows else float(df['low'].min())

    range_diff = high - low
    if range_diff <= 0:
        return {}

    curr_price = float(df['close'].iloc[-1])
    eq = round(low + (range_diff * 0.5), 5)
    ote_618 = round(low + (range_diff * 0.618), 5)
    ote_786 = round(low + (range_diff * 0.786), 5)

    zone = "EQUILIBRIUM"
    if curr_price > eq:
        zone = "PREMIUM (Sell Zone)"
    elif curr_price < eq:
        zone = "DISCOUNT (Buy Zone)"

    return {
        "range_high": round(high, 5),
        "range_low": round(low, 5),
        "equilibrium_50": eq,
        "current_price": round(curr_price, 5),
        "current_zone": zone,
        "ote_levels": {
            "fib_61_8": ote_618,
            "fib_78_6": ote_786
        }
    }

def detect_liquidity_pools(swings: List[Dict[str, Any]], tolerance_pct: float = 0.05) -> Dict[str, Any]:
    """Detect Equal Highs (Buy-side Liquidity) and Equal Lows (Sell-side Liquidity)."""
    eq_highs = []
    eq_lows = []

    high_swings = [s for s in swings if s['type'] == 'HIGH']
    low_swings = [s for s in swings if s['type'] == 'LOW']

    for i in range(len(high_swings) - 1):
        p1 = high_swings[i]['price']
        p2 = high_swings[i + 1]['price']
        diff_pct = abs(p1 - p2) / p1 * 100
        if diff_pct <= tolerance_pct:
            eq_highs.append({
                "type": "EQH (Buy-side Liquidity)",
                "price_level": round((p1 + p2) / 2, 5),
                "time1": high_swings[i]['time'],
                "time2": high_swings[i + 1]['time']
            })

    for i in range(len(low_swings) - 1):
        p1 = low_swings[i]['price']
        p2 = low_swings[i + 1]['price']
        diff_pct = abs(p1 - p2) / p1 * 100
        if diff_pct <= tolerance_pct:
            eq_lows.append({
                "type": "EQL (Sell-side Liquidity)",
                "price_level": round((p1 + p2) / 2, 5),
                "time1": low_swings[i]['time'],
                "time2": low_swings[i + 1]['time']
            })

    return {
        "equal_highs": eq_highs[-3:],
        "equal_lows": eq_lows[-3:]
    }

def analyze_smc(symbol: str = "XAUUSD", timeframe: str = "M15", count: int = 150) -> Dict[str, Any]:
    """Perform Smart Money Concept (SMC) analysis: BOS, CHoCH, Order Blocks, FVGs, Liquidity Pools, Premium/Discount."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    tf = TIMEFRAME_MAP.get(timeframe.upper())
    if tf is None:
        return {"status": "error", "message": f"Invalid timeframe '{timeframe}'"}

    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) < 30:
        return {"status": "error", "message": f"Insufficient candle data for '{symbol}'"}

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    swings = find_swings(df, window=3)
    structure = detect_market_structure(df, swings)
    fvgs = detect_fvgs(df)
    obs = detect_order_blocks(df)
    prem_disc = calculate_premium_discount(df, swings)
    liquidity = detect_liquidity_pools(swings)

    # Filter for active (unmitigated) FVGs and OBs
    unmitigated_fvgs = [f for f in fvgs if not f['mitigated']][-5:]
    unmitigated_obs = [o for o in obs if not o['mitigated']][-5:]

    # SMC Trade Bias Summary
    bias = structure.get("structure", "NEUTRAL")
    trade_suggestion = "Wait for pullback to unmitigated OB/FVG"
    if bias == "BULLISH":
        if prem_disc.get("current_zone", "").startswith("DISCOUNT"):
            trade_suggestion = "High Probability BUY: In Discount zone with Bullish Market Structure."
        else:
            trade_suggestion = "Bullish structure, but in Premium zone. Wait for retracement to Discount/OB."
    elif bias == "BEARISH":
        if prem_disc.get("current_zone", "").startswith("PREMIUM"):
            trade_suggestion = "High Probability SELL: In Premium zone with Bearish Market Structure."
        else:
            trade_suggestion = "Bearish structure, but in Discount zone. Wait for retracement to Premium/OB."

    return {
        "status": "success",
        "symbol": symbol,
        "timeframe": timeframe,
        "market_structure": structure,
        "premium_discount": prem_disc,
        "trade_bias": bias,
        "smc_summary": trade_suggestion,
        "active_unmitigated_order_blocks": unmitigated_obs,
        "active_unmitigated_fvgs": unmitigated_fvgs,
        "liquidity_pools": liquidity
    }
