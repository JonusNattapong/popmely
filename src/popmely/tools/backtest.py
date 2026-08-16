from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import MetaTrader5 as mt5
from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.tools.market_data import TIMEFRAME_MAP
from popmely.tools.smc import find_swings, detect_market_structure, detect_fvgs

def backtest_smc_strategy(df: pd.DataFrame, rr_ratio: float = 2.0) -> List[Dict[str, Any]]:
    """Simulate SMC strategy (Trade in direction of BOS/CHoCH on FVG/OB touch)."""
    trades = []
    in_trade = False
    trade_info = {}

    for i in range(50, len(df) - 1):
        curr_bar = df.iloc[i]
        next_bar = df.iloc[i + 1]

        if in_trade:
            if trade_info['type'] == 'BUY':
                if next_bar['low'] <= trade_info['sl']:
                    trades.append({**trade_info, "exit_time": str(next_bar['time']), "exit_price": trade_info['sl'], "result": "LOSS", "pnl_rr": -1.0})
                    in_trade = False
                elif next_bar['high'] >= trade_info['tp']:
                    trades.append({**trade_info, "exit_time": str(next_bar['time']), "exit_price": trade_info['tp'], "result": "WIN", "pnl_rr": rr_ratio})
                    in_trade = False
            elif trade_info['type'] == 'SELL':
                if next_bar['high'] >= trade_info['sl']:
                    trades.append({**trade_info, "exit_time": str(next_bar['time']), "exit_price": trade_info['sl'], "result": "LOSS", "pnl_rr": -1.0})
                    in_trade = False
                elif next_bar['low'] <= trade_info['tp']:
                    trades.append({**trade_info, "exit_time": str(next_bar['time']), "exit_price": trade_info['tp'], "result": "WIN", "pnl_rr": rr_ratio})
                    in_trade = False
            continue

        sub_df = df.iloc[max(0, i - 40):i + 1].copy().reset_index(drop=True)
        swings = find_swings(sub_df, window=2)
        structure = detect_market_structure(sub_df, swings)
        fvgs = detect_fvgs(sub_df)
        
        bias = structure.get("structure")
        close_p = curr_bar['close']

        if bias == "BULLISH":
            active_bull_fvgs = [f for f in fvgs if f['type'] == 'BULLISH_FVG' and not f['mitigated']]
            if active_bull_fvgs:
                fvg = active_bull_fvgs[-1]
                if fvg['bottom'] <= close_p <= fvg['top']:
                    sl = fvg['bottom'] - ((fvg['top'] - fvg['bottom']) * 0.5)
                    sl_dist = abs(close_p - sl)
                    if sl_dist > 0:
                        tp = close_p + (sl_dist * rr_ratio)
                        in_trade = True
                        trade_info = {
                            "entry_time": str(curr_bar['time']),
                            "type": "BUY",
                            "entry_price": round(float(close_p), 5),
                            "sl": round(float(sl), 5),
                            "tp": round(float(tp), 5),
                            "strategy": "SMC_BULLISH_FVG"
                        }

        elif bias == "BEARISH":
            active_bear_fvgs = [f for f in fvgs if f['type'] == 'BEARISH_FVG' and not f['mitigated']]
            if active_bear_fvgs:
                fvg = active_bear_fvgs[-1]
                if fvg['bottom'] <= close_p <= fvg['top']:
                    sl = fvg['top'] + ((fvg['top'] - fvg['bottom']) * 0.5)
                    sl_dist = abs(sl - close_p)
                    if sl_dist > 0:
                        tp = close_p - (sl_dist * rr_ratio)
                        in_trade = True
                        trade_info = {
                            "entry_time": str(curr_bar['time']),
                            "type": "SELL",
                            "entry_price": round(float(close_p), 5),
                            "sl": round(float(sl), 5),
                            "tp": round(float(tp), 5),
                            "strategy": "SMC_BEARISH_FVG"
                        }

    return trades

def backtest_ema_rsi_strategy(df: pd.DataFrame, rr_ratio: float = 2.0) -> List[Dict[str, Any]]:
    """Simulate EMA Trend + RSI Pullback strategy."""
    trades = []
    in_trade = False
    trade_info = {}

    close = df['close']
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - (100 / (1 + rs))).fillna(50.0)

    for i in range(50, len(df) - 1):
        curr_bar = df.iloc[i]
        next_bar = df.iloc[i + 1]

        if in_trade:
            if trade_info['type'] == 'BUY':
                if next_bar['low'] <= trade_info['sl']:
                    trades.append({**trade_info, "exit_time": str(next_bar['time']), "exit_price": trade_info['sl'], "result": "LOSS", "pnl_rr": -1.0})
                    in_trade = False
                elif next_bar['high'] >= trade_info['tp']:
                    trades.append({**trade_info, "exit_time": str(next_bar['time']), "exit_price": trade_info['tp'], "result": "WIN", "pnl_rr": rr_ratio})
                    in_trade = False
            elif trade_info['type'] == 'SELL':
                if next_bar['high'] >= trade_info['sl']:
                    trades.append({**trade_info, "exit_time": str(next_bar['time']), "exit_price": trade_info['sl'], "result": "LOSS", "pnl_rr": -1.0})
                    in_trade = False
                elif next_bar['low'] <= trade_info['tp']:
                    trades.append({**trade_info, "exit_time": str(next_bar['time']), "exit_price": trade_info['tp'], "result": "WIN", "pnl_rr": rr_ratio})
                    in_trade = False
            continue

        c_p = close.iloc[i]
        e20 = ema20.iloc[i]
        e50 = ema50.iloc[i]
        r = rsi.iloc[i]

        if e20 > e50 and r <= 42 and c_p > e20:
            sl = float(df['low'].iloc[max(0, i-5):i].min())
            sl_dist = abs(c_p - sl)
            if sl_dist > 0:
                tp = c_p + (sl_dist * rr_ratio)
                in_trade = True
                trade_info = {
                    "entry_time": str(curr_bar['time']),
                    "type": "BUY",
                    "entry_price": round(float(c_p), 5),
                    "sl": round(float(sl), 5),
                    "tp": round(float(tp), 5),
                    "strategy": "EMA_RSI_PULLBACK"
                }

        elif e20 < e50 and r >= 58 and c_p < e20:
            sl = float(df['high'].iloc[max(0, i-5):i].max())
            sl_dist = abs(sl - c_p)
            if sl_dist > 0:
                tp = c_p - (sl_dist * rr_ratio)
                in_trade = True
                trade_info = {
                    "entry_time": str(curr_bar['time']),
                    "type": "SELL",
                    "entry_price": round(float(c_p), 5),
                    "sl": round(float(sl), 5),
                    "tp": round(float(tp), 5),
                    "strategy": "EMA_RSI_PULLBACK"
                }

    return trades

def run_backtest(
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    strategy: str = "smc",
    bars_count: int = 500,
    start_balance: float = 10000.0,
    risk_percent: float = 1.0,
    rr_ratio: float = 2.0
) -> Dict[str, Any]:
    """Run historical backtest simulation on MT5 data and compute metrics (Win rate, Max Drawdown, Profit Factor, PnL)."""
    if not MT5ConnectionManager.ensure_connected():
        return {"status": "error", "message": "MT5 not connected"}

    tf = TIMEFRAME_MAP.get(timeframe.upper())
    if tf is None:
        return {"status": "error", "message": f"Invalid timeframe '{timeframe}'"}

    if not mt5.symbol_select(symbol, True):
        return {"status": "error", "message": f"Failed to select symbol '{symbol}'"}

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars_count)
    if rates is None or len(rates) < 100:
        return {"status": "error", "message": f"Insufficient historical bars for '{symbol}' (need at least 100)"}

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    strat_key = strategy.lower()
    if strat_key in ("smc", "smc_fvg", "smart_money"):
        trades = backtest_smc_strategy(df, rr_ratio)
    else:
        trades = backtest_ema_rsi_strategy(df, rr_ratio)

    if not trades:
        return {
            "status": "success",
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy,
            "bars_tested": len(df),
            "message": "No trade setups triggered during this period.",
            "metrics": {
                "total_trades": 0,
                "win_rate_percent": 0.0,
                "net_profit_usd": 0.0,
                "profit_factor": 0.0
            },
            "trades": []
        }

    balance = start_balance
    peak_balance = start_balance
    max_drawdown_usd = 0.0
    max_drawdown_pct = 0.0
    wins = 0
    losses = 0
    total_gain = 0.0
    total_loss = 0.0

    trade_logs = []
    for t in trades:
        risk_usd = balance * (risk_percent / 100.0)
        pnl_usd = risk_usd * t["pnl_rr"]
        balance += pnl_usd

        if pnl_usd > 0:
            wins += 1
            total_gain += pnl_usd
        else:
            losses += 1
            total_loss += abs(pnl_usd)

        if balance > peak_balance:
            peak_balance = balance
        dd_usd = peak_balance - balance
        dd_pct = (dd_usd / peak_balance) * 100 if peak_balance > 0 else 0
        if dd_usd > max_drawdown_usd:
            max_drawdown_usd = dd_usd
        if dd_pct > max_drawdown_pct:
            max_drawdown_pct = dd_pct

        trade_logs.append({
            **t,
            "pnl_usd": round(pnl_usd, 2),
            "balance_after": round(balance, 2)
        })

    total_trades = len(trades)
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0.0
    profit_factor = round(total_gain / total_loss, 2) if total_loss > 0 else (999.0 if total_gain > 0 else 0.0)
    net_profit_usd = round(balance - start_balance, 2)
    net_profit_pct = round((net_profit_usd / start_balance) * 100, 2)

    # Auto-archive to database
    try:
        from popmely.db import save_backtest_result
        save_backtest_result(
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            bars_count=len(df),
            start_balance=start_balance,
            final_balance=round(balance, 2),
            total_trades=total_trades,
            win_rate=round(win_rate, 2),
            profit_factor=profit_factor,
            max_drawdown_pct=round(max_drawdown_pct, 2),
            net_profit=net_profit_usd,
            risk_percent=risk_percent,
            rr_ratio=rr_ratio
        )
    except Exception:
        pass

    return {
        "status": "success",
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy": strategy,
        "period_bars": len(df),
        "start_time": str(df['time'].iloc[0]),
        "end_time": str(df['time'].iloc[-1]),
        "metrics": {
            "start_balance": start_balance,
            "final_balance": round(balance, 2),
            "net_profit_usd": net_profit_usd,
            "net_profit_percent": f"{net_profit_pct}%",
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": f"{round(win_rate, 2)}%",
            "profit_factor": profit_factor,
            "max_drawdown_usd": round(max_drawdown_usd, 2),
            "max_drawdown_percent": f"{round(max_drawdown_pct, 2)}%",
            "avg_win_usd": round(total_gain / wins, 2) if wins > 0 else 0.0,
            "avg_loss_usd": round(total_loss / losses, 2) if losses > 0 else 0.0
        },
        "recent_trades": trade_logs[-15:]
    }
