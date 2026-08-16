from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import MetaTrader5 as mt5
from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.utils.formatters import format_tick

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

def get_quote(symbol: str) -> Dict[str, Any]:
    """Get live Bid, Ask, Spread, and timestamp for a given symbol (e.g. 'XAUUSD', 'EURUSD')."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'. Check if symbol name is correct."}

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"status": "error", "message": f"Failed to get tick for '{symbol}'"}

    return {
        "status": "success",
        "data": format_tick(tick, symbol)
    }

def get_symbol_info(symbol: str) -> Dict[str, Any]:
    """Get detailed specification for a symbol (Digits, Point, Min/Max Lot, Contract Size, Tick Value, Spread)."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    info = mt5.symbol_info(symbol)
    if info is None:
        return {"status": "error", "message": f"Symbol '{symbol}' not found"}

    return {
        "status": "success",
        "data": {
            "name": info.name,
            "description": info.description,
            "currency_base": info.currency_base,
            "currency_profit": info.currency_profit,
            "currency_margin": info.currency_margin,
            "digits": info.digits,
            "point": info.point,
            "spread": info.spread,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "trade_contract_size": info.trade_contract_size,
            "trade_tick_size": info.trade_tick_size,
            "trade_tick_value": info.trade_tick_value,
            "trade_mode": info.trade_mode
        }
    }

def search_symbols(query: str = "XAU") -> Dict[str, Any]:
    """Search for matching symbol names available in the broker (e.g. 'XAU', 'GOLD', 'EUR')."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    symbols = mt5.symbols_get()
    if symbols is None:
        return {"status": "error", "message": "Failed to fetch symbols"}

    query_upper = query.upper()
    matches = []
    for s in symbols:
        if query_upper in s.name.upper() or (s.description and query_upper in s.description.upper()):
            matches.append({
                "name": s.name,
                "path": s.path,
                "description": s.description,
                "visible": s.visible
            })

    return {
        "status": "success",
        "count": len(matches),
        "data": matches[:50]
    }

def get_candles(symbol: str, timeframe: str = "M15", count: int = 50) -> Dict[str, Any]:
    """Get historical OHLCV candles for a symbol. Timeframe: 'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'. Count: 1-500."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    tf = TIMEFRAME_MAP.get(timeframe.upper())
    if tf is None:
        return {"status": "error", "message": f"Invalid timeframe '{timeframe}'. Valid options: {list(TIMEFRAME_MAP.keys())}"}

    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        return {"status": "error", "message": f"Failed to get candle rates for '{symbol}'"}

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    candles = []
    for _, row in df.iterrows():
        candles.append({
            "time": row['time'].isoformat(),
            "open": round(float(row['open']), 5),
            "high": round(float(row['high']), 5),
            "low": round(float(row['low']), 5),
            "close": round(float(row['close']), 5),
            "tick_volume": int(row['tick_volume']),
            "spread": int(row['spread'])
        })

    return {
        "status": "success",
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(candles),
        "candles": candles
    }
