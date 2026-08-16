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
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """Generate high-resolution candlestick chart image (.png) with optional SMC (FVG, Order Blocks) and EMA overlays."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    tf = TIMEFRAME_MAP.get(timeframe.upper(), mt5.TIMEFRAME_M15)
    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) < 30:
        return {"status": "error", "message": f"Insufficient candle data for {symbol}"}

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
        title=f"\n{symbol} ({timeframe}) - popmely SMC Chart",
        returnfig=True,
        figsize=(12, 7),
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
                main_ax.axhspan(f['bottom'], f['top'], color=f_color, alpha=0.22, label=f['type'])
                smc_annotations_count += 1

        # Plot recent Order Blocks
        for ob in obs[-4:]:
            if not ob['mitigated']:
                ob_color = '#00b0ff' if ob['type'] == 'BULLISH_OB' else '#ff9100'
                main_ax.axhspan(ob['bottom'], ob['top'], color=ob_color, alpha=0.18, linestyle='--')
                smc_annotations_count += 1

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
        "smc_overlays_applied": smc_annotations_count,
        "ema_overlays_applied": len(addplots),
        "message": f"Candlestick chart generated successfully: {out_file.name}"
    }
