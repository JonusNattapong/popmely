"""Visual Chart Generation with SMC Overlays & Technical Indicators for popmely.

Uses mplfinance and matplotlib to generate high-resolution candlestick chart images (.png)
with Fair Value Gaps (FVG), Order Blocks (OB), and EMAs overlaid.
"""

from typing import Dict, Any, Optional
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import MetaTrader5 as mt5

import matplotlib
matplotlib.use('Agg')  # Headless backend (no GUI window required)
import matplotlib.pyplot as plt
import mplfinance as mpf

from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.tools.market_data import TIMEFRAME_MAP
from popmely.tools.smc import detect_fvgs, detect_order_blocks, find_swings

CHART_DIR = Path.home() / ".popmely" / "charts"


def generate_candlestick_chart(
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    count: int = 80,
    overlay_smc: bool = True,
    overlay_ema: bool = True,
    entry_price: Optional[float] = None,
    sl_price: Optional[float] = None,
    tp_price: Optional[float] = None,
    trade_action: Optional[str] = None,
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """Generate high-resolution candlestick chart image (.png) with optional SMC (FVG, Order Blocks), EMAs, and Entry / SL / TP trade plan lines overlaid."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    tf = TIMEFRAME_MAP.get(timeframe.upper(), mt5.TIMEFRAME_M15)
    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) < 30:
        return {"status": "error", "message": f"Insufficient candle data for {symbol}"}

    # Auto-detect Entry, SL, TP from active position if not provided
    if entry_price is None:
        positions = mt5.positions_get(symbol=symbol)
        if positions and len(positions) > 0:
            active_p = positions[0]
            entry_price = float(active_p.price_open)
            sl_price = float(active_p.sl) if active_p.sl > 0 else sl_price
            tp_price = float(active_p.tp) if active_p.tp > 0 else tp_price
            trade_action = "BUY" if active_p.type == mt5.ORDER_TYPE_BUY else "SELL"

    # Prepare DataFrame for mplfinance (requires DatetimeIndex and Open/High/Low/Close/Volume)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'tick_volume': 'Volume'
    }, inplace=True)

    # Determine save path
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = Path(save_path) if save_path else CHART_DIR / f"{symbol}_{timeframe}_{timestamp_str}.png"

    # Additional Plots (EMAs)
    addplots = []
    if overlay_ema and len(df) >= 30:
        ema20 = df['Close'].ewm(span=20, adjust=False).mean()
        ema50 = df['Close'].ewm(span=50, adjust=False).mean()
        addplots.append(mpf.make_addplot(ema20, color='#00ffff', width=1.2))
        addplots.append(mpf.make_addplot(ema50, color='#ffd700', width=1.2))
        if len(df) >= 80:
            ema200 = df['Close'].ewm(span=200, adjust=False).mean()
            addplots.append(mpf.make_addplot(ema200, color='#ff00ff', width=1.5))

    # Custom dark style
    mc = mpf.make_marketcolors(
        up='#26a69a',
        down='#ef5350',
        edge='inherit',
        wick='inherit',
        volume='#363c4e'
    )
    s = mpf.make_mpf_style(
        base_mpf_style='nightclouds',
        marketcolors=mc,
        gridcolor='#2a2e39',
        facecolor='#131722',
        figcolor='#131722'
    )

    # Plot
    fig, axlist = mpf.plot(
        df,
        type='candle',
        style=s,
        volume=True,
        addplot=addplots if addplots else None,
        title=f"\n{symbol} ({timeframe}) - popmely Smart Chart",
        returnfig=True,
        figsize=(13, 7.5),
        tight_layout=True
    )

    # Overlay SMC Annotations (FVG and OB highlight boxes)
    main_ax = axlist[0]
    smc_annotations_count = 0

    if overlay_smc:
        raw_df = pd.DataFrame(rates)
        raw_df['time'] = pd.to_datetime(raw_df['time'], unit='s')
        fvgs = detect_fvgs(raw_df)
        obs = detect_order_blocks(raw_df)

        # Plot recent unmitigated FVGs
        for f in fvgs[-6:]:
            if not f['mitigated']:
                f_color = '#00e676' if f['type'] == 'BULLISH_FVG' else '#ff1744'
                main_ax.axhspan(f['bottom'], f['top'], color=f_color, alpha=0.20, label=f['type'])
                smc_annotations_count += 1

        # Plot recent Order Blocks
        for ob in obs[-4:]:
            if not ob['mitigated']:
                ob_color = '#00b0ff' if ob['type'] == 'BULLISH_OB' else '#ff9100'
                main_ax.axhspan(ob['bottom'], ob['top'], color=ob_color, alpha=0.16, linestyle='--')
                smc_annotations_count += 1

    # Overlay Entry, Stop Loss, and Take Profit lines
    trade_plan_drawn = False
    rr_text = None
    if entry_price is not None and entry_price > 0:
        main_ax.axhline(entry_price, color='#00e5ff', linestyle='--', linewidth=1.8, label='ENTRY')
        main_ax.text(len(df) - 1, entry_price, f"  ENTRY {entry_price:.2f}", color='#00e5ff', verticalalignment='center', fontweight='bold', fontsize=9)
        trade_plan_drawn = True

        if sl_price is not None and sl_price > 0:
            main_ax.axhline(sl_price, color='#ff1744', linestyle='--', linewidth=1.8, label='STOP LOSS')
            main_ax.text(len(df) - 1, sl_price, f"  SL {sl_price:.2f}", color='#ff1744', verticalalignment='center', fontweight='bold', fontsize=9)
            # Risk zone shading
            main_ax.axhspan(min(entry_price, sl_price), max(entry_price, sl_price), color='#ff1744', alpha=0.10)

        if tp_price is not None and tp_price > 0:
            main_ax.axhline(tp_price, color='#00e676', linestyle='--', linewidth=1.8, label='TAKE PROFIT')
            main_ax.text(len(df) - 1, tp_price, f"  TP {tp_price:.2f}", color='#00e676', verticalalignment='center', fontweight='bold', fontsize=9)
            # Reward zone shading
            main_ax.axhspan(min(entry_price, tp_price), max(entry_price, tp_price), color='#00e676', alpha=0.10)

        # Calculate R:R Ratio
        if sl_price and tp_price:
            risk = abs(entry_price - sl_price)
            reward = abs(tp_price - entry_price)
            if risk > 0:
                rr_val = round(reward / risk, 2)
                rr_text = f"1:{rr_val} R:R"
                action_str = f"{trade_action} " if trade_action else ""
                main_ax.set_title(f"\n{symbol} ({timeframe}) | {action_str}Plan: Entry {entry_price:.2f} | SL {sl_price:.2f} | TP {tp_price:.2f} ({rr_text})", color='#ffffff', fontsize=12)

    # Save figure
    fig.savefig(str(out_file), dpi=150, bbox_inches='tight', facecolor='#131722')
    plt.close(fig)

    return {
        "status": "success",
        "symbol": symbol,
        "timeframe": timeframe,
        "bars_count": len(df),
        "last_close": float(df['Close'].iloc[-1]),
        "image_path": str(out_file),
        "trade_plan_overlaid": trade_plan_drawn,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "risk_reward_ratio": rr_text,
        "smc_overlays_applied": smc_annotations_count,
        "ema_overlays_applied": len(addplots),
        "message": f"Candlestick chart generated successfully with Entry/SL/TP: {out_file.name}"
    }
