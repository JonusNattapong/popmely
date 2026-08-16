"""Institutional-Grade & ICT Algorithmic Trading Tools for popmely.

Includes:
1. ICT Silver Bullet Framework (Time-window, Liquidity Sweep, MSS, FVG Retest)
2. Judas Swing & Asian Range Sweep Detector
3. Inversion Fair Value Gap (IFVG) Scanner
4. Multi-Timeframe Institutional Confluence Matrix (Score 0-100%)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.tools.market_data import TIMEFRAME_MAP
from popmely.tools.smc import find_swings, detect_market_structure, detect_fvgs, detect_order_blocks
from popmely.tools.analysis import calculate_rsi


# =====================================================================
# 1. ICT SILVER BULLET ANALYZER
# =====================================================================

def analyze_silver_bullet(
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    count: int = 100
) -> Dict[str, Any]:
    """Analyze chart for ICT Silver Bullet setup (Liquidity Sweep + MSS + FVG Trigger)."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    tf = TIMEFRAME_MAP.get(timeframe.upper(), mt5.TIMEFRAME_M15)
    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) < 40:
        return {"status": "error", "message": f"Insufficient candle data for {symbol}"}

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    close_p = float(df['close'].iloc[-1])

    # 1. Check swings & liquidity pools
    swings = find_swings(df, window=2)
    structure = detect_market_structure(df, swings)
    fvgs = detect_fvgs(df)

    recent_highs = [s['price'] for s in swings if s['type'] == 'HIGH']
    recent_lows = [s['price'] for s in swings if s['type'] == 'LOW']

    # 2. Sweep detection
    sweep_bull = False
    sweep_bear = False
    sweep_detail = "None"

    if len(df) >= 5:
        recent_window = df.iloc[-10:]
        if recent_lows and recent_window['low'].min() < recent_lows[-1] and close_p > recent_lows[-1]:
            sweep_bull = True
            sweep_detail = f"Sell-Side Liquidity (SSL) swept at {recent_lows[-1]:.2f} followed by bullish rebound"
        elif recent_highs and recent_window['high'].max() > recent_highs[-1] and close_p < recent_highs[-1]:
            sweep_bear = True
            sweep_detail = f"Buy-Side Liquidity (BSL) swept at {recent_highs[-1]:.2f} followed by bearish rejection"

    # 3. Market Structure Shift (MSS)
    bias = structure.get("structure", "NEUTRAL")
    active_bull_fvgs = [f for f in fvgs if f['type'] == 'BULLISH_FVG' and not f['mitigated']]
    active_bear_fvgs = [f for f in fvgs if f['type'] == 'BEARISH_FVG' and not f['mitigated']]

    setup = {
        "status": "success",
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy": "ICT_SILVER_BULLET",
        "current_price": close_p,
        "liquidity_sweep": {
            "detected": sweep_bull or sweep_bear,
            "type": "SSL_BULLISH_SWEEP" if sweep_bull else "BSL_BEARISH_SWEEP" if sweep_bear else "NONE",
            "detail": sweep_detail
        },
        "market_structure_shift": {
            "mss_bias": bias,
            "last_event": structure.get("last_event")
        },
        "silver_bullet_signal": None
    }

    # Bullish Silver Bullet
    if (sweep_bull or bias == "BULLISH") and active_bull_fvgs:
        target_fvg = active_bull_fvgs[-1]
        sl = round(target_fvg['bottom'] - ((target_fvg['top'] - target_fvg['bottom']) * 0.5), 5)
        sl_dist = abs(close_p - sl)
        tp = round(close_p + (sl_dist * 2.5), 5)
        setup["silver_bullet_signal"] = {
            "action": "BUY_LIMIT" if close_p > target_fvg['top'] else "BUY",
            "entry_zone": f"[{target_fvg['bottom']} - {target_fvg['top']}]",
            "optimal_entry": round((target_fvg['top'] + target_fvg['bottom']) / 2, 5),
            "stop_loss": sl,
            "take_profit_1": round(close_p + (sl_dist * 2.0), 5),
            "take_profit_2": tp,
            "rr_ratio": "1:2.5",
            "quality": "HIGH" if sweep_bull and bias == "BULLISH" else "MEDIUM",
            "rationale": "SSL Liquidity sweep confirmed with bullish displacement into unmitigated FVG."
        }

    # Bearish Silver Bullet
    elif (sweep_bear or bias == "BEARISH") and active_bear_fvgs:
        target_fvg = active_bear_fvgs[-1]
        sl = round(target_fvg['top'] + ((target_fvg['top'] - target_fvg['bottom']) * 0.5), 5)
        sl_dist = abs(sl - close_p)
        tp = round(close_p - (sl_dist * 2.5), 5)
        setup["silver_bullet_signal"] = {
            "action": "SELL_LIMIT" if close_p < target_fvg['bottom'] else "SELL",
            "entry_zone": f"[{target_fvg['bottom']} - {target_fvg['top']}]",
            "optimal_entry": round((target_fvg['top'] + target_fvg['bottom']) / 2, 5),
            "stop_loss": sl,
            "take_profit_1": round(close_p - (sl_dist * 2.0), 5),
            "take_profit_2": tp,
            "rr_ratio": "1:2.5",
            "quality": "HIGH" if sweep_bear and bias == "BEARISH" else "MEDIUM",
            "rationale": "BSL Liquidity sweep confirmed with bearish displacement into unmitigated FVG."
        }
    else:
        setup["silver_bullet_signal"] = {
            "action": "NO_TRADE",
            "quality": "LOW",
            "rationale": "No clean Liquidity Sweep + FVG alignment. Waiting for institutional displacement."
        }

    return setup


# =====================================================================
# 2. JUDAS SWING & ASIAN RANGE SWEEP DETECTOR
# =====================================================================

def detect_judas_swing(
    symbol: str = "XAUUSD",
    count: int = 120
) -> Dict[str, Any]:
    """Detect Asian Range manipulation (Judas Swing) and Stop Hunt reversals for London/NY open."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, count)
    if rates is None or len(rates) < 60:
        return {"status": "error", "message": f"Insufficient candle data for {symbol}"}

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    close_p = float(df['close'].iloc[-1])

    # Filter recent Asian Session (approx 00:00 to 08:00 UTC / Asian hours)
    df['hour'] = df['time'].dt.hour
    asian_candles = df[df['hour'].between(0, 7)]

    if len(asian_candles) < 8:
        asian_high = float(df['high'].iloc[-40:-15].max())
        asian_low = float(df['low'].iloc[-40:-15].min())
    else:
        asian_high = float(asian_candles['high'].tail(24).max())
        asian_low = float(asian_candles['low'].tail(24).min())

    asian_range_pips = round(abs(asian_high - asian_low), 2)
    asian_mid = round((asian_high + asian_low) / 2, 2)

    # Check recent breakout (last 10 candles)
    recent_10 = df.tail(10)
    highest_recent = float(recent_10['high'].max())
    lowest_recent = float(recent_10['low'].min())

    judas_type = "NONE"
    reversal_target = None
    sl_target = None
    confidence = "LOW"
    rationale = "Price is currently oscillating inside Asian range."

    # Bearish Judas Swing: Swept Asian High then dropped back below
    if highest_recent > asian_high and close_p < asian_high:
        judas_type = "BEARISH_JUDAS_SWING"
        sl_target = round(highest_recent + (asian_range_pips * 0.1), 2)
        reversal_target = asian_low
        confidence = "HIGH" if close_p < asian_mid else "MEDIUM"
        rationale = f"Fakeout above Asian High ({asian_high:.2f}). Liquidity swept up to {highest_recent:.2f}. Trapped buyers, targeting Asian Low ({asian_low:.2f})."

    # Bullish Judas Swing: Swept Asian Low then bounced back above
    elif lowest_recent < asian_low and close_p > asian_low:
        judas_type = "BULLISH_JUDAS_SWING"
        sl_target = round(lowest_recent - (asian_range_pips * 0.1), 2)
        reversal_target = asian_high
        confidence = "HIGH" if close_p > asian_mid else "MEDIUM"
        rationale = f"Fakeout below Asian Low ({asian_low:.2f}). Liquidity swept down to {lowest_recent:.2f}. Trapped sellers, targeting Asian High ({asian_high:.2f})."

    return {
        "status": "success",
        "symbol": symbol,
        "current_price": close_p,
        "asian_range": {
            "high": round(asian_high, 2),
            "low": round(asian_low, 2),
            "equilibrium": asian_mid,
            "range_points": asian_range_pips
        },
        "judas_swing_analysis": {
            "pattern": judas_type,
            "confidence": confidence,
            "rationale": rationale,
            "suggested_action": "SELL" if judas_type == "BEARISH_JUDAS_SWING" else "BUY" if judas_type == "BULLISH_JUDAS_SWING" else "WAIT",
            "suggested_entry": close_p,
            "suggested_sl": sl_target,
            "suggested_tp": reversal_target,
            "target_side": "Asian Low" if judas_type == "BEARISH_JUDAS_SWING" else "Asian High" if judas_type == "BULLISH_JUDAS_SWING" else "N/A"
        }
    }


# =====================================================================
# 3. INVERSION FAIR VALUE GAP (IFVG) SCANNER
# =====================================================================

def analyze_ifvg(
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    count: int = 100
) -> Dict[str, Any]:
    """Scan and analyze Inversion Fair Value Gaps (IFVG) - FVG role reversals acting as support/resistance."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    tf = TIMEFRAME_MAP.get(timeframe.upper(), mt5.TIMEFRAME_M15)
    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) < 30:
        return {"status": "error", "message": f"Insufficient candle data for {symbol}"}

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    close_p = float(df['close'].iloc[-1])

    # Find raw FVGs
    raw_fvgs = detect_fvgs(df)
    inversion_fvgs = []

    for f in raw_fvgs:
        f_idx = f['bar_index']
        f_top = f['top']
        f_bottom = f['bottom']
        f_type = f['type']

        # Check subsequent candles for a BODY CLOSE through the FVG
        subsequent = df.iloc[f_idx + 3:]
        if subsequent.empty:
            continue

        if f_type == "BULLISH_FVG":
            # Violated if a candle body closes BELOW the bottom of the bullish FVG
            breaks = subsequent[subsequent['close'] < f_bottom]
            if not breaks.empty:
                break_time = str(breaks['time'].iloc[0])
                is_retesting = f_bottom <= close_p <= f_top
                inversion_fvgs.append({
                    "type": "BEARISH_IFVG",
                    "role": "INVERTED_RESISTANCE",
                    "original_type": "BULLISH_FVG",
                    "top": f_top,
                    "bottom": f_bottom,
                    "inversion_time": break_time,
                    "currently_retesting": is_retesting,
                    "status": "ACTIVE_RETEST" if is_retesting else "CONFIRMED"
                })

        elif f_type == "BEARISH_FVG":
            # Violated if a candle body closes ABOVE the top of the bearish FVG
            breaks = subsequent[subsequent['close'] > f_top]
            if not breaks.empty:
                break_time = str(breaks['time'].iloc[0])
                is_retesting = f_bottom <= close_p <= f_top
                inversion_fvgs.append({
                    "type": "BULLISH_IFVG",
                    "role": "INVERTED_SUPPORT",
                    "original_type": "BEARISH_FVG",
                    "top": f_top,
                    "bottom": f_bottom,
                    "inversion_time": break_time,
                    "currently_retesting": is_retesting,
                    "status": "ACTIVE_RETEST" if is_retesting else "CONFIRMED"
                })

    active_retests = [ifvg for ifvg in inversion_fvgs if ifvg['currently_retesting']]
    
    recommendation = "No active IFVG retests at current market price."
    if active_retests:
        latest_retest = active_retests[-1]
        if latest_retest['type'] == 'BULLISH_IFVG':
            recommendation = f"High Probability BUY: Price is retesting Bullish IFVG Support [{latest_retest['bottom']} - {latest_retest['top']}]."
        else:
            recommendation = f"High Probability SELL: Price is retesting Bearish IFVG Resistance [{latest_retest['bottom']} - {latest_retest['top']}]."

    return {
        "status": "success",
        "symbol": symbol,
        "timeframe": timeframe,
        "current_price": close_p,
        "total_ifvgs_found": len(inversion_fvgs),
        "active_retests_count": len(active_retests),
        "active_retests": active_retests,
        "recent_inversion_fvgs": inversion_fvgs[-5:],
        "summary_recommendation": recommendation
    }


# =====================================================================
# 4. MULTI-TIMEFRAME CONFLUENCE MATRIX
# =====================================================================

def calculate_confluence_matrix(symbol: str = "XAUUSD") -> Dict[str, Any]:
    """Calculate Multi-Timeframe Institutional Confluence Score (0 to 100%) across H4, H1, and M15."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    # Fetch data across 3 timeframes
    r_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 80)
    r_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 80)
    r_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 80)

    if r_h4 is None or r_h1 is None or r_m15 is None:
        return {"status": "error", "message": "Failed to fetch multi-timeframe candles"}

    df_h4 = pd.DataFrame(r_h4)
    df_h1 = pd.DataFrame(r_h1)
    df_m15 = pd.DataFrame(r_m15)

    close_p = float(df_m15['close'].iloc[-1])

    # 1. H4 Higher Timeframe Bias (Max 25 pts)
    sw_h4 = find_swings(df_h4, 2)
    st_h4 = detect_market_structure(df_h4, sw_h4)
    h4_bias = st_h4.get("structure", "NEUTRAL")
    h4_score = 25 if h4_bias == "BULLISH" else -25 if h4_bias == "BEARISH" else 0

    # 2. H1 Market Structure & Order Block (Max 35 pts)
    sw_h1 = find_swings(df_h1, 2)
    st_h1 = detect_market_structure(df_h1, sw_h1)
    obs_h1 = detect_order_blocks(df_h1)
    h1_bias = st_h1.get("structure", "NEUTRAL")

    h1_score = 20 if h1_bias == "BULLISH" else -20 if h1_bias == "BEARISH" else 0
    # Add points if near H1 Order Block
    for ob in obs_h1:
        if not ob['mitigated'] and ob['bottom'] <= close_p <= ob['top']:
            h1_score += 15 if ob['type'] == 'BULLISH_OB' else -15

    # 3. M15 Trigger & FVG (Max 25 pts)
    fvgs_m15 = detect_fvgs(df_m15)
    active_bull_fvg = any(f['bottom'] <= close_p <= f['top'] for f in fvgs_m15 if f['type'] == 'BULLISH_FVG' and not f['mitigated'])
    active_bear_fvg = any(f['bottom'] <= close_p <= f['top'] for f in fvgs_m15 if f['type'] == 'BEARISH_FVG' and not f['mitigated'])

    m15_score = 0
    if active_bull_fvg:
        m15_score += 25
    elif active_bear_fvg:
        m15_score -= 25

    # 4. Momentum / RSI 14 (Max 15 pts)
    rsi_val = float(calculate_rsi(df_m15['close']).iloc[-1])
    rsi_score = 0
    if rsi_val <= 35:
        rsi_score += 15  # Oversold -> Bullish
    elif rsi_val >= 65:
        rsi_score -= 15  # Overbought -> Bearish

    # Calculate Total Bullish & Bearish %
    total_raw = h4_score + h1_score + m15_score + rsi_score  # range -100 to +100
    bullish_prob = max(0, min(100, int(50 + (total_raw / 2))))
    bearish_prob = 100 - bullish_prob

    verdict = "NEUTRAL"
    if bullish_prob >= 80:
        verdict = "STRONG_BUY"
    elif bullish_prob >= 65:
        verdict = "BUY"
    elif bearish_prob >= 80:
        verdict = "STRONG_SELL"
    elif bearish_prob >= 65:
        verdict = "SELL"

    return {
        "status": "success",
        "symbol": symbol,
        "current_price": close_p,
        "confluence_score": {
            "verdict": verdict,
            "bullish_probability": f"{bullish_prob}%",
            "bearish_probability": f"{bearish_prob}%",
            "total_score_raw": total_raw
        },
        "timeframe_breakdown": {
            "H4_Macro": {"bias": h4_bias, "points": h4_score, "max_points": 25},
            "H1_Structure": {"bias": h1_bias, "points": h1_score, "max_points": 35},
            "M15_Execution": {"fvg_retest": "Bullish FVG" if active_bull_fvg else "Bearish FVG" if active_bear_fvg else "None", "points": m15_score, "max_points": 25},
            "RSI_Momentum": {"rsi_14": round(rsi_val, 2), "points": rsi_score, "max_points": 15}
        },
        "trade_readiness": "READY" if abs(total_raw) >= 50 else "WAIT_FOR_BETTER_ALIGNMENT"
    }
