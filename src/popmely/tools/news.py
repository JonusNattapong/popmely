"""High-Impact Economic News & News Trading Tools for popmely.

Provides:
1. Live Economic Calendar (ForexFactory / FairEconomy Feed)
2. News Blackout & High-Volatility Window Detection
3. High-Impact News Straddle Execution (Trade explosive spikes with dual BUY_STOP + SELL_STOP)
4. Post-News Volatility & Spike Momentum Analyzer
"""

from typing import Dict, Any, List, Optional
import json
import urllib.request
import logging
from datetime import datetime, timezone
import MetaTrader5 as mt5
import pandas as pd

from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.tools.trading import place_bracket_order, get_positions, close_position
from popmely.tools.market_data import get_quote, TIMEFRAME_MAP

logger = logging.getLogger("popmely.news")

CALENDAR_FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


# =====================================================================
# 1. ECONOMIC CALENDAR FEED
# =====================================================================

def get_economic_calendar(
    currency: Optional[str] = None,
    impact: str = "High",
    days: int = 7
) -> Dict[str, Any]:
    """Fetch live economic calendar events with filters for Impact (High, Medium, Low, All) and Currency (USD, EUR, GBP, JPY, etc.)."""
    try:
        req = urllib.request.Request(
            CALENDAR_FEED_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) popmely/5.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            raw_data = response.read().decode('utf-8')
            events = json.loads(raw_data)
    except Exception as e:
        logger.warning(f"Failed to fetch live economic calendar feed: {e}")
        return {
            "status": "warning",
            "message": f"Could not connect to live economic calendar feed: {e}",
            "events_count": 0,
            "events": []
        }

    filtered = []
    impact_filter = impact.upper() if impact else "ALL"
    curr_filter = currency.upper() if currency else None

    for ev in events:
        ev_impact = ev.get("impact", "").strip().title()
        ev_country = ev.get("country", "").strip().upper()

        if impact_filter != "ALL" and ev_impact.upper() != impact_filter:
            continue
        if curr_filter and ev_country != curr_filter:
            continue

        filtered.append({
            "title": ev.get("title"),
            "currency": ev_country,
            "impact": ev_impact,
            "date": ev.get("date"),
            "forecast": ev.get("forecast") or "-",
            "previous": ev.get("previous") or "-"
        })

    return {
        "status": "success",
        "feed_source": "FairEconomy / ForexFactory Live Feed",
        "filter_impact": impact,
        "filter_currency": currency or "ALL",
        "events_count": len(filtered),
        "events": filtered
    }


# =====================================================================
# 2. NEWS BLACKOUT / HIGH-IMPACT WINDOW DETECTOR
# =====================================================================

def check_news_blackout(
    symbol: str = "XAUUSD",
    minutes_before: int = 15,
    minutes_after: int = 15
) -> Dict[str, Any]:
    """Check if current time is within a High-Impact news blackout window for the symbol's currency pair."""
    # Determine base/quote currencies
    curr_list = ["USD"]
    s_upper = symbol.upper()
    if "EUR" in s_upper: curr_list.append("EUR")
    if "GBP" in s_upper: curr_list.append("GBP")
    if "JPY" in s_upper: curr_list.append("JPY")
    if "AUD" in s_upper: curr_list.append("AUD")
    if "CAD" in s_upper: curr_list.append("CAD")
    if "CHF" in s_upper: curr_list.append("CHF")
    if "NZD" in s_upper: curr_list.append("NZD")

    cal = get_economic_calendar(impact="High")
    if cal.get("status") != "success":
        return {
            "status": "warning",
            "symbol": symbol,
            "in_news_window": False,
            "recommendation": "Calendar feed unavailable. Exercise standard risk management."
        }

    now_utc = datetime.now(timezone.utc)
    imminent_events = []

    for ev in cal.get("events", []):
        if ev["currency"] not in curr_list:
            continue

        date_str = ev.get("date")
        if not date_str:
            continue

        try:
            ev_dt = datetime.fromisoformat(date_str)
            if ev_dt.tzinfo is None:
                ev_dt = ev_dt.replace(tzinfo=timezone.utc)

            diff_mins = (ev_dt - now_utc).total_seconds() / 60.0

            # Inside blackout window: -minutes_after <= diff <= +minutes_before
            if -minutes_after <= diff_mins <= minutes_before:
                imminent_events.append({
                    **ev,
                    "minutes_until_release": round(diff_mins, 1),
                    "status": "RELEASED_RECENTLY" if diff_mins < 0 else "IMMINENT_RELEASE"
                })
        except Exception:
            continue

    in_window = len(imminent_events) > 0
    recommendation = (
        "⚠️ HIGH-IMPACT NEWS WINDOW DETECTED! High slippage/spread expected. Use News Straddle or pause standard market entries."
        if in_window else
        "🟢 Clear market conditions. No imminent high-impact news for relevant currencies."
    )

    return {
        "status": "success",
        "symbol": symbol,
        "monitored_currencies": curr_list,
        "in_news_window": in_window,
        "imminent_high_impact_events": imminent_events,
        "blackout_window_config": f"{minutes_before}m before / {minutes_after}m after",
        "recommendation": recommendation
    }


# =====================================================================
# 3. HIGH-IMPACT NEWS STRADDLE EXECUTION (TRADE THE NEWS)
# =====================================================================

def execute_news_straddle_trade(
    symbol: str = "XAUUSD",
    event_name: str = "High_Impact_News",
    distance_points: float = 250.0,
    volume: float = 0.01,
    sl_points: float = 150.0,
    tp_points: float = 450.0,
    expire_minutes: int = 30
) -> Dict[str, Any]:
    """Execute a High-Impact News Straddle Strategy.

    Places simultaneous BUY_STOP above and SELL_STOP below market price with tight SL and 1:3 R:R TP
    to instantly catch the explosive breakout spike regardless of direction.
    """
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    quote = get_quote(symbol)
    if quote.get("status") != "success":
        return {"status": "error", "message": f"Could not retrieve quote for {symbol}"}

    comment = f"News_{event_name[:10]}"

    # Execute Bracket Breakout Orders via place_bracket_order
    res = place_bracket_order(
        symbol=symbol,
        distance_points=distance_points,
        volume=volume,
        sl_points=sl_points,
        tp_points=tp_points,
        comment=comment
    )

    if res.get("status") == "success":
        # Log to Database
        try:
            from popmely.db import log_bot_signal
            log_bot_signal(
                symbol=symbol,
                strategy="NEWS_STRADDLE_SPIKE",
                signal_type="BRACKET_STRADDLE",
                direction="BOTH",
                timeframe="M1",
                entry_price=quote.get("ask"),
                sl_price=sl_points,
                tp_price=tp_points,
                confluence_score=95.0,
                executed=True,
                detail=f"News Straddle placed for {event_name} with {distance_points}pt offset and 1:3 R:R"
            )
        except Exception:
            pass

    return {
        "status": "success",
        "strategy": "HIGH_IMPACT_NEWS_STRADDLE",
        "symbol": symbol,
        "event_target": event_name,
        "current_market_price": quote.get("ask"),
        "distance_offset_points": distance_points,
        "risk_reward_ratio": f"1:{round(tp_points / sl_points, 1)}",
        "execution_result": res,
        "operational_guide": "When the news releases, the market spike will trigger one side. The pending opposite side will act as hedge or can be cancelled via mt5_cancel_all_pending_orders."
    }


# =====================================================================
# 4. POST-NEWS VOLATILITY & SPIKE ANALYZER
# =====================================================================

def analyze_news_volatility(
    symbol: str = "XAUUSD",
    timeframe: str = "M1",
    count: int = 30
) -> Dict[str, Any]:
    """Analyze instantaneous candle volatility spike (ATR expansion & pip displacement) to verify news spike continuation vs rejection."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    tf = TIMEFRAME_MAP.get(timeframe.upper(), mt5.TIMEFRAME_M1)
    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) < 15:
        return {"status": "error", "message": "Insufficient candle rates for volatility analysis"}

    df = pd.DataFrame(rates)
    df['range'] = df['high'] - df['low']
    
    recent_candle = df.iloc[-1]
    recent_range = float(recent_candle['range'])
    avg_range = float(df['range'].iloc[:-1].mean())

    spike_multiplier = round(recent_range / avg_range, 2) if avg_range > 0 else 1.0

    candle_direction = "BULLISH_SPIKE" if recent_candle['close'] > recent_candle['open'] else "BEARISH_SPIKE"
    
    if spike_multiplier >= 3.0:
        volatility_state = "EXTREME_NEWS_EXPLOSION"
    elif spike_multiplier >= 1.8:
        volatility_state = "ELEVATED_VOLATILITY"
    else:
        volatility_state = "NORMAL_VOLATILITY"

    return {
        "status": "success",
        "symbol": symbol,
        "timeframe": timeframe,
        "current_price": float(recent_candle['close']),
        "volatility_state": volatility_state,
        "spike_multiplier": f"{spike_multiplier}x normal range",
        "latest_candle_range": round(recent_range, 2),
        "baseline_average_range": round(avg_range, 2),
        "spike_direction": candle_direction,
        "recommendation": "Trail stop closely to protect breakout profits." if spike_multiplier >= 2.0 else "Volatility standard. Safe for standard SMC trading."
    }
