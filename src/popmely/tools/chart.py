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

    # Overlay SMC Annotations (FVG and OB highlight boxes starting from their formation bar)
    main_ax = axlist[0]
    smc_annotations_count = 0
    import matplotlib.patches as patches

    if overlay_smc:
        raw_df = pd.DataFrame(rates)
        raw_df['time'] = pd.to_datetime(raw_df['time'], unit='s')
        fvgs = detect_fvgs(raw_df)
        obs = detect_order_blocks(raw_df)

        # Plot recent unmitigated FVGs with bounded width
        for f in fvgs[-5:]:
            if not f['mitigated']:
                f_color = '#00e676' if f['type'] == 'BULLISH_FVG' else '#ff1744'
                start_x = max(0, f.get('bar_index', len(df) - 25))
                width = len(df) - start_x + 3
                rect_fvg = patches.Rectangle(
                    (start_x, f['bottom']), width, f['top'] - f['bottom'],
                    facecolor=f_color, alpha=0.18, edgecolor=f_color, linewidth=1, linestyle=':'
                )
                main_ax.add_patch(rect_fvg)
                main_ax.text(start_x + 0.5, (f['top'] + f['bottom']) / 2, f"  {f['type'].replace('_', ' ')}", color=f_color, fontsize=7.5, verticalalignment='center')
                smc_annotations_count += 1

        # Plot recent Order Blocks with bounded width
        for ob in obs[-3:]:
            if not ob['mitigated']:
                ob_color = '#00b0ff' if ob['type'] == 'BULLISH_OB' else '#ff9100'
                start_x = max(0, ob.get('bar_index', len(df) - 30))
                width = len(df) - start_x + 3
                rect_ob = patches.Rectangle(
                    (start_x, ob['bottom']), width, ob['top'] - ob['bottom'],
                    facecolor=ob_color, alpha=0.18, edgecolor=ob_color, linewidth=1, linestyle='--'
                )
                main_ax.add_patch(rect_ob)
                main_ax.text(start_x + 0.5, (ob['top'] + ob['bottom']) / 2, f"  +{ob['type']}", color=ob_color, fontsize=8, verticalalignment='center', fontweight='bold')
                smc_annotations_count += 1

    # Overlay TradingView-style Long/Short Position Box Widget (Bounded SL/TP Box)
    trade_plan_drawn = False
    rr_text = None
    if entry_price is not None and entry_price > 0:
        box_start_x = max(0, len(df) - 22)
        box_end_x = len(df) + 4
        box_width = box_end_x - box_start_x

        # 1. Entry Line & Badge
        main_ax.hlines(entry_price, box_start_x, box_end_x, colors='#00e5ff', linestyles='dotted', linewidth=1.6)
        main_ax.text(
            box_start_x + 1, entry_price, f"  {symbol} ENTRY {entry_price:.2f}",
            color='#ffffff', fontsize=8.5, verticalalignment='center',
            bbox=dict(boxstyle='round,pad=0.25', facecolor='#00838f', edgecolor='none', alpha=0.9)
        )
        trade_plan_drawn = True

        # 2. Take Profit Box (TradingView Green Box)
        if tp_price is not None and tp_price > 0:
            tp_bottom = min(entry_price, tp_price)
            tp_height = abs(tp_price - entry_price)
            rect_tp = patches.Rectangle(
                (box_start_x, tp_bottom), box_width, tp_height,
                facecolor='#26a69a', alpha=0.28, edgecolor='#00e676', linewidth=1.2, linestyle='-'
            )
            main_ax.add_patch(rect_tp)
            main_ax.hlines(tp_price, box_start_x, box_end_x, colors='#00e676', linestyles='dotted', linewidth=1.8)
            main_ax.text(
                box_end_x - 1, tp_price, f"TP {tp_price:.2f}",
                color='#ffffff', fontsize=8.5, verticalalignment='center', horizontalalignment='right',
                bbox=dict(boxstyle='round,pad=0.25', facecolor='#2e7d32', edgecolor='none', alpha=0.9)
            )

        # 3. Stop Loss Box (TradingView Red/Purple Risk Box)
        if sl_price is not None and sl_price > 0:
            sl_bottom = min(entry_price, sl_price)
            sl_height = abs(sl_price - entry_price)
            rect_sl = patches.Rectangle(
                (box_start_x, sl_bottom), box_width, sl_height,
                facecolor='#7e57c2' if (trade_action == 'SELL') else '#ef5350',
                alpha=0.30, edgecolor='#ff1744', linewidth=1.2, linestyle='-'
            )
            main_ax.add_patch(rect_sl)
            main_ax.hlines(sl_price, box_start_x, box_end_x, colors='#ff1744', linestyles='dotted', linewidth=1.8)
            main_ax.text(
                box_end_x - 1, sl_price, f"SL {sl_price:.2f}",
                color='#ffffff', fontsize=8.5, verticalalignment='center', horizontalalignment='right',
                bbox=dict(boxstyle='round,pad=0.25', facecolor='#c62828', edgecolor='none', alpha=0.9)
            )

        # 4. Risk / Reward Header Calculation
        if sl_price and tp_price:
            risk = abs(entry_price - sl_price)
            reward = abs(tp_price - entry_price)
            if risk > 0:
                rr_val = round(reward / risk, 2)
                rr_text = f"1:{rr_val} R:R"
                action_str = f"[{trade_action}] " if trade_action else ""
                main_ax.set_title(
                    f"\n{symbol} ({timeframe}) | {action_str}Target: {tp_price:.2f} | Stop: {sl_price:.2f} | Risk/Reward: {rr_text}",
                    color='#ffffff', fontsize=11.5, fontweight='bold'
                )

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
