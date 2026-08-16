from typing import Dict, Any
import numpy as np
import pandas as pd
import MetaTrader5 as mt5
from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.tools.market_data import TIMEFRAME_MAP

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def analyze_technical(symbol: str = "XAUUSD", timeframe: str = "M15", count: int = 100) -> Dict[str, Any]:
    """Perform automated technical analysis on a symbol. Calculates EMA (20/50/200), RSI (14), MACD, ATR, Bollinger Bands, and Key Levels."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    tf = TIMEFRAME_MAP.get(timeframe.upper())
    if tf is None:
        return {"status": "error", "message": f"Invalid timeframe '{timeframe}'"}

    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, max(count, 220))
    if rates is None or len(rates) < 30:
        return {"status": "error", "message": f"Insufficient candle data for '{symbol}'"}

    df = pd.DataFrame(rates)
    close = df['close']

    # Indicators
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean() if len(df) >= 200 else pd.Series([np.nan] * len(df))
    
    rsi = calculate_rsi(close, 14)
    
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - macd_signal

    atr = calculate_atr(df, 14)

    # Bollinger Bands (20, 2)
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    bb_upper = sma20 + (std20 * 2)
    bb_lower = sma20 - (std20 * 2)

    # Latest values
    curr_price = float(close.iloc[-1])
    curr_ema20 = float(ema20.iloc[-1])
    curr_ema50 = float(ema50.iloc[-1])
    curr_ema200 = float(ema200.iloc[-1]) if not np.isnan(ema200.iloc[-1]) else None
    curr_rsi = round(float(rsi.iloc[-1]), 2)
    curr_macd = round(float(macd_line.iloc[-1]), 4)
    curr_macd_sig = round(float(macd_signal.iloc[-1]), 4)
    curr_macd_hist = round(float(macd_hist.iloc[-1]), 4)
    curr_atr = round(float(atr.iloc[-1]), 4) if not np.isnan(atr.iloc[-1]) else None
    curr_bb_u = round(float(bb_upper.iloc[-1]), 4) if not np.isnan(bb_upper.iloc[-1]) else None
    curr_bb_l = round(float(bb_lower.iloc[-1]), 4) if not np.isnan(bb_lower.iloc[-1]) else None

    # Trend Bias
    trend = "NEUTRAL"
    if curr_price > curr_ema20 > curr_ema50:
        trend = "BULLISH"
    elif curr_price < curr_ema20 < curr_ema50:
        trend = "BEARISH"

    # RSI Condition
    rsi_condition = "NORMAL"
    if curr_rsi >= 70:
        rsi_condition = "OVERBOUGHT"
    elif curr_rsi <= 30:
        rsi_condition = "OVERSOLD"

    # Key Support and Resistance from recent 50 bars
    recent_high = round(float(df['high'].tail(50).max()), 4)
    recent_low = round(float(df['low'].tail(50).min()), 4)

    return {
        "status": "success",
        "symbol": symbol,
        "timeframe": timeframe,
        "current_price": curr_price,
        "trend_bias": trend,
        "indicators": {
            "rsi_14": curr_rsi,
            "rsi_condition": rsi_condition,
            "ema_20": round(curr_ema20, 4),
            "ema_50": round(curr_ema50, 4),
            "ema_200": round(curr_ema200, 4) if curr_ema200 else "N/A",
            "macd": {"line": curr_macd, "signal": curr_macd_sig, "histogram": curr_macd_hist},
            "atr_14": curr_atr,
            "bollinger_bands": {"upper": curr_bb_u, "middle": round(float(sma20.iloc[-1]), 4), "lower": curr_bb_l}
        },
        "key_levels": {
            "recent_resistance_50": recent_high,
            "recent_support_50": recent_low
        }
    }
