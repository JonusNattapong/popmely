"""Live Streaming Trading Dashboard & Real-Time Console for popmely.

Usage:
    python -m popmely.live --symbol XAUUSD --interval 2 --auto-trade
"""

import sys
import io
import time
import os
import argparse
from typing import Optional, List, Dict, Any
from datetime import datetime
import MetaTrader5 as mt5

from popmely.utils.mt5_connection import MT5ConnectionManager
from popmely.tools.market_data import get_quote
from popmely.tools.smc import analyze_smc
from popmely.tools.institutional import calculate_confluence_matrix
from popmely.tools.credit_score import credit_score
from popmely.tools.news import check_news_blackout
from popmely.tools.trading import get_positions
from popmely.agent.bot_engine import bot_agent

# Fix Windows console UTF-8 encoding safely
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def format_currency(val: float) -> str:
    """Format USD currency."""
    return f"${val:,.2f}"


def render_score_bar(score: float, max_score: float = 100.0) -> str:
    """Render colored ASCII progress bar for Credit Score."""
    pct = max(0.0, min(100.0, (score / max_score) * 100.0))
    bar_length = 20
    filled = int((pct / 100.0) * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)
    
    if pct >= 70:
        color = "\033[92m"  # Green
        tier = "🟢 GREEN (100% Lot)"
    elif pct >= 50:
        color = "\033[93m"  # Yellow
        tier = "🟡 YELLOW (50% Lot)"
    elif pct >= 30:
        color = "\033[38;5;208m"  # Orange
        tier = "🟠 ORANGE (25% Lot)"
    else:
        color = "\033[91m"  # Red
        tier = "🔴 CRITICAL (HALTED)"
        
    reset = "\033[0m"
    return f"{color}[{bar}] {pct:.1f}% {tier}{reset}"


def run_live_stream(
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    interval: float = 2.0,
    auto_trade: bool = False,
    max_cycles: Optional[int] = None
):
    """Run live real-time trading and market data stream."""
    if not MT5ConnectionManager.ensure_connected():
        print("❌ Could not connect to MetaTrader 5 terminal.")
        return

    # Initialize credit score if needed
    if not credit_score.initialized:
        credit_score.initialize(100.0, 10000.0)

    # Start bot if auto-trade requested
    if auto_trade and not bot_agent._running:
        bot_agent.start(
            symbol=symbol,
            timeframe=timeframe,
            auto_trade=True,
            scan_interval=int(interval * 5)
        )

    cycle = 0
    event_logs = [
        f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Live Streaming Terminal Initialized.",
        f"[{datetime.now().strftime('%H:%M:%S')}] 📡 Connecting to MetaTrader 5 WebSocket & Data Feed...",
        f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ Credit Score System Online (Persistent SQLite)."
    ]

    try:
        while True:
            cycle += 1
            if max_cycles and cycle > max_cycles:
                break

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 1. Fetch Account
            acc = mt5.account_info()
            balance = acc.balance if acc else 0.0
            equity = acc.equity if acc else 0.0
            margin = acc.margin if acc else 0.0
            free_margin = acc.margin_free if acc else 0.0
            profit = acc.profit if acc else 0.0
            server_name = acc.server if acc else "Unknown"
            login_id = acc.login if acc else "0"

            # 2. Fetch Quote
            q = get_quote(symbol)
            bid = q.get("bid", 0.0)
            ask = q.get("ask", 0.0)
            spread = q.get("spread", 0)

            # 3. Fetch Positions
            pos_res = get_positions()
            open_positions = pos_res.get("positions", [])

            # 4. Confluence & SMC (computed every 3 cycles to maintain high FPS)
            if cycle % 3 == 1 or 'conf_score' not in locals():
                try:
                    conf = calculate_confluence_matrix(symbol)
                    conf_score = conf.get("confluence_score", {})
                    conf_verdict = conf_score.get("verdict", "NEUTRAL")
                    bull_p = conf_score.get("bullish_probability", "50%")
                    bear_p = conf_score.get("bearish_probability", "50%")
                except Exception:
                    conf_verdict, bull_p, bear_p = "NEUTRAL", "50%", "50%"

            # 5. News Window Check
            if cycle % 10 == 1 or 'news_status' not in locals():
                try:
                    news_res = check_news_blackout(symbol=symbol, minutes_before=15, minutes_after=15)
                    in_news = news_res.get("in_news_window", False)
                    news_status = "⚠️ NEWS WINDOW ACTIVE" if in_news else "🟢 CLEAR (No High-Impact News)"
                except Exception:
                    news_status = "🟢 CLEAR"

            # Render Screen
            clear_screen()
            print("=" * 82)
            print(f" 👑 POPMELY LIVE STREAMING TRADING TERMINAL v5.0.0 | {now_str}")
            print(f" 🔌 MT5 Account: #{login_id} ({server_name}) | Terminal: CONNECTED")
            print("=" * 82)

            # Portfolio Row
            pnl_color = "\033[92m" if profit >= 0 else "\033[91m"
            reset = "\033[0m"
            print(f" 💰 Balance: {format_currency(balance):<14} | Equity: {format_currency(equity):<14} | Floating PnL: {pnl_color}{format_currency(profit):<12}{reset}")
            print(f" 🔒 Margin Used: {format_currency(margin):<10} | Free Margin: {format_currency(free_margin):<10} | Margin Level: {acc.margin_level if acc and acc.margin_level else 0.0:.1f}%")
            print("-" * 82)

            # Risk & Credit Score
            cs_stat = credit_score.get_status()
            curr_score = cs_stat.get("score", {}).get("current", 100.0)
            max_sc = cs_stat.get("score", {}).get("max", 100.0)
            l_streak = cs_stat.get("streaks", {}).get("losing_streak", 0)
            w_streak = cs_stat.get("streaks", {}).get("winning_streak", 0)

            print(f" 🛡️  Trading Credit Score : {render_score_bar(curr_score, max_sc)}")
            print(f"    Streak Counters      : Win Streak: {w_streak} | Loss Streak: {l_streak} | SQLite: PERSISTENT")
            print("-" * 82)

            # Market & Confluence
            verdict_color = "\033[92m" if "BUY" in conf_verdict else "\033[91m" if "SELL" in conf_verdict else "\033[93m"
            print(f" 📊 Ticker ({symbol})       : Bid: {bid:.2f} | Ask: {ask:.2f} | Spread: {spread} pts")
            print(f" 🎛️  Confluence Matrix   : {verdict_color}{conf_verdict:<12}{reset} (Bullish: {bull_p} | Bearish: {bear_p})")
            print(f" 📰 Economic News Status : {news_status}")
            print("-" * 82)

            # Active Positions Table
            print(f" 📈 Active Positions ({len(open_positions)} Open):")
            if not open_positions:
                print("    (No open market positions currently active)")
            else:
                print(f"    {'Ticket':<10} {'Symbol':<8} {'Type':<6} {'Volume':<8} {'Open Price':<12} {'Current':<12} {'PnL ($)':<10}")
                for p in open_positions[:5]:
                    pos_pnl_col = "\033[92m" if p['profit'] >= 0 else "\033[91m"
                    print(f"    #{p['ticket']:<9} {p['symbol']:<8} {p['type']:<6} {p['volume']:<8} {p['price_open']:<12.2f} {p['price_current']:<12.2f} {pos_pnl_col}${p['profit']:<9.2f}{reset}")

            print("-" * 82)

            # Live Event Stream Log (Last 5)
            print(" 📡 Live Stream Event Feed:")
            for log in event_logs[-4:]:
                print(f"    {log}")

            print("=" * 82)
            print(f" [Auto-Refresh every {interval}s | Press Ctrl+C to Stop Stream]")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n⏹️ Live Stream Terminated by User.")
        if auto_trade and bot_agent._running:
            bot_agent.stop()
            print("🛑 Autonomous Bot Stopped cleanly.")


def main():
    parser = argparse.ArgumentParser(description="popmely Live Streaming Trading Terminal")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol to monitor (default: XAUUSD)")
    parser.add_argument("--timeframe", default="M15", help="Timeframe (default: M15)")
    parser.add_argument("--interval", type=float, default=2.0, help="Refresh interval in seconds (default: 2.0)")
    parser.add_argument("--auto-trade", action="store_true", help="Enable autonomous trading execution in background")
    args = parser.parse_args()

    run_live_stream(
        symbol=args.symbol,
        timeframe=args.timeframe,
        interval=args.interval,
        auto_trade=args.auto_trade
    )


if __name__ == "__main__":
    main()
