import sys
import os
import argparse
import logging
import json
from typing import Optional
from mcp.server.fastmcp import FastMCP, Context

from popmely import __version__
from popmely.config import config
import popmely.tools.account as account_tool
import popmely.tools.market_data as market_tool
import popmely.tools.analysis as analysis_tool
import popmely.tools.smc as smc_tool
import popmely.tools.backtest as backtest_tool
import popmely.tools.risk as risk_tool
import popmely.tools.trading as trading_tool
import popmely.tools.agent as agent_tool
import popmely.tools.credit_score as score_tool
import popmely.tools.institutional as inst_tool

# Setup standard logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("popmely")

# Initialize FastMCP Server
mcp = FastMCP("popmely-mt5-trading", dependencies=["MetaTrader5", "pandas", "numpy", "pydantic", "requests"])

# =====================================================================
# 1. ACCOUNT & TERMINAL TOOLS
# =====================================================================

@mcp.tool()
def mt5_account_info() -> dict:
    """Retrieve detailed information about the current MT5 trading account (Balance, Equity, Margin, Leverage, Profit)."""
    return account_tool.get_account_info()

@mcp.tool()
def mt5_terminal_status() -> dict:
    """Check MetaTrader 5 terminal status, connection to broker, and whether automated trading is enabled."""
    return account_tool.get_terminal_status()

# =====================================================================
# 2. MARKET DATA TOOLS
# =====================================================================

@mcp.tool()
def mt5_get_quote(symbol: str = "XAUUSD") -> dict:
    """Get live Bid, Ask, Spread, and timestamp for a given symbol (e.g. 'XAUUSD', 'EURUSD', 'BTCUSD')."""
    return market_tool.get_quote(symbol)

@mcp.tool()
def mt5_get_symbol_info(symbol: str = "XAUUSD") -> dict:
    """Get detailed specification for a symbol (Digits, Point, Min/Max Lot, Contract Size, Tick Value, Spread)."""
    return market_tool.get_symbol_info(symbol)

@mcp.tool()
def mt5_search_symbols(query: str = "XAU") -> dict:
    """Search for matching symbol names available in the broker (e.g. 'XAU', 'GOLD', 'EUR', 'BTC')."""
    return market_tool.search_symbols(query)

@mcp.tool()
def mt5_get_candles(symbol: str = "XAUUSD", timeframe: str = "M15", count: int = 50) -> dict:
    """Get historical OHLCV candles for a symbol. Timeframe: 'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'. Count: 1-500."""
    return market_tool.get_candles(symbol, timeframe, count)

# =====================================================================
# 3. TECHNICAL & SMC ANALYSIS TOOLS
# =====================================================================

@mcp.tool()
def mt5_analyze_technical(symbol: str = "XAUUSD", timeframe: str = "M15", count: int = 100) -> dict:
    """Perform automated technical analysis on a symbol. Calculates EMA (20/50/200), RSI (14), MACD, ATR, Bollinger Bands, and Key Support/Resistance Levels."""
    return analysis_tool.analyze_technical(symbol, timeframe, count)

@mcp.tool()
def mt5_analyze_smc(symbol: str = "XAUUSD", timeframe: str = "M15", count: int = 150) -> dict:
    """Perform Smart Money Concept (SMC) analysis: Break of Structure (BOS), Change of Character (CHoCH), Order Blocks (OB), Fair Value Gaps (FVG), Liquidity Pools (EQH/EQL), and Premium vs Discount zones."""
    return smc_tool.analyze_smc(symbol, timeframe, count)

# =====================================================================
# 4. BACKTEST ENGINE TOOLS
# =====================================================================

@mcp.tool()
def mt5_run_backtest(
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    strategy: str = "smc",  # 'smc' or 'ema_rsi'
    bars_count: int = 500,
    start_balance: float = 10000.0,
    risk_percent: float = 1.0,
    rr_ratio: float = 2.0
) -> dict:
    """Run historical backtest simulation on MT5 candles and calculate performance metrics (Win Rate, Net Profit, Profit Factor, Max Drawdown, Trade logs)."""
    return backtest_tool.run_backtest(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        bars_count=bars_count,
        start_balance=start_balance,
        risk_percent=risk_percent,
        rr_ratio=rr_ratio
    )

# =====================================================================
# 5. INSTITUTIONAL & ICT STRATEGY TOOLS
# =====================================================================

@mcp.tool()
def mt5_analyze_silver_bullet(
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    count: int = 100
) -> dict:
    """ICT Silver Bullet Analyzer: Detects Liquidity Sweeps (BSL/SSL), Market Structure Shift (MSS) displacement, and unmitigated FVG triggers. Returns structured execution plans with entry, SL, and 1:2.5 R:R TP."""
    return inst_tool.analyze_silver_bullet(symbol, timeframe, count)

@mcp.tool()
def mt5_detect_judas_swing(
    symbol: str = "XAUUSD",
    count: int = 120
) -> dict:
    """Judas Swing & Asian Range Sweep: Detects false breakout manipulation above Asian High / below Asian Low at London/NY open and generates sniper reversal targets."""
    return inst_tool.detect_judas_swing(symbol, count)

@mcp.tool()
def mt5_analyze_ifvg(
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    count: int = 100
) -> dict:
    """Inversion Fair Value Gap (IFVG) Scanner: Scans for broken FVGs that have inverted their role into high-probability support (Bullish IFVG) or resistance (Bearish IFVG) zones."""
    return inst_tool.analyze_ifvg(symbol, timeframe, count)

@mcp.tool()
def mt5_confluence_matrix(
    symbol: str = "XAUUSD"
) -> dict:
    """Multi-Timeframe Institutional Confluence Matrix: Computes a comprehensive 0-100% confluence score across H4 (Macro Bias), H1 (Structure & OBs), M15 (FVG Retest), and RSI Momentum."""
    return inst_tool.calculate_confluence_matrix(symbol)

# =====================================================================
# 5. RISK MANAGEMENT TOOLS
# =====================================================================

@mcp.tool()
def mt5_calculate_lot_size(
    symbol: str = "XAUUSD",
    stop_loss_points: float = 0.0,
    risk_amount_usd: Optional[float] = None,
    risk_percent: Optional[float] = None,
    entry_price: Optional[float] = None,
    stop_loss_price: Optional[float] = None,
    take_profit_price: Optional[float] = None
) -> dict:
    """Calculate recommended lot size, estimated loss at SL, and risk/reward ratio based on account equity and SL distance."""
    return risk_tool.calculate_lot_size(
        symbol=symbol,
        stop_loss_points=stop_loss_points,
        risk_amount_usd=risk_amount_usd,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price
    )

# =====================================================================
# 6. TRADING & ORDER EXECUTION TOOLS
# =====================================================================

@mcp.tool()
def mt5_place_order(
    symbol: str,
    action: str,  # 'BUY' or 'SELL'
    volume: float,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
    deviation: Optional[int] = None,
    comment: str = "AI_MCP_Order",
    magic: Optional[int] = None
) -> dict:
    """Execute a market BUY or SELL order on MT5 with lot size, SL, and TP."""
    return trading_tool.place_order(
        symbol=symbol,
        action=action,
        volume=volume,
        sl=sl,
        tp=tp,
        deviation=deviation,
        comment=comment,
        magic=magic
    )

@mcp.tool()
def mt5_place_pending_order(
    symbol: str,
    order_type: str,  # 'BUY_LIMIT', 'SELL_LIMIT', 'BUY_STOP', 'SELL_STOP'
    price: float,
    volume: float,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
    deviation: Optional[int] = None,
    comment: str = "AI_MCP_Pending",
    magic: Optional[int] = None
) -> dict:
    """Place a pending order (BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP)."""
    return trading_tool.place_pending_order(
        symbol=symbol,
        order_type=order_type,
        price=price,
        volume=volume,
        sl=sl,
        tp=tp,
        deviation=deviation,
        comment=comment,
        magic=magic
    )

@mcp.tool()
def mt5_smart_order(
    symbol: str = "XAUUSD",
    action: str = "BUY",
    sl_price: float = 0.0,
    tp_price: Optional[float] = None,
    rr_ratio: float = 2.0,
    risk_percent: float = 1.0,
    comment: str = "AI_SmartOrder"
) -> dict:
    """Smart Order Execution: Automatically calculates optimal Lot Size from % risk and SL distance, verifies Credit Score, calculates TP target based on R:R ratio, and executes order in one step."""
    return trading_tool.smart_order(
        symbol=symbol,
        action=action,
        sl_price=sl_price,
        tp_price=tp_price,
        rr_ratio=rr_ratio,
        risk_percent=risk_percent,
        comment=comment
    )

@mcp.tool()
def mt5_place_bracket_order(
    symbol: str = "XAUUSD",
    distance_points: float = 200.0,
    volume: float = 0.01,
    sl_points: float = 150.0,
    tp_points: float = 300.0,
    comment: str = "AI_Bracket"
) -> dict:
    """Place a Straddle Bracket Order (Both BUY_STOP above and SELL_STOP below market price) for breakout/news trading."""
    return trading_tool.place_bracket_order(
        symbol=symbol,
        distance_points=distance_points,
        volume=volume,
        sl_points=sl_points,
        tp_points=tp_points,
        comment=comment
    )

@mcp.tool()
def mt5_place_grid_orders(
    symbol: str = "XAUUSD",
    action: str = "BUY",
    levels: int = 3,
    step_points: float = 150.0,
    volume_per_order: float = 0.01,
    tp_points: float = 300.0,
    comment: str = "AI_Grid"
) -> dict:
    """Place DCA/Grid Pending Limit Orders stepping down (for BUY) or stepping up (for SELL) to average into positions."""
    return trading_tool.place_grid_orders(
        symbol=symbol,
        action=action,
        levels=levels,
        step_points=step_points,
        volume_per_order=volume_per_order,
        tp_points=tp_points,
        comment=comment
    )

@mcp.tool()
def mt5_get_positions(symbol: Optional[str] = None) -> dict:
    """Get all open active positions or filter by symbol, including unrealized profit and tickets."""
    return trading_tool.get_positions(symbol)

@mcp.tool()
def mt5_modify_position(ticket: int, sl: Optional[float] = None, tp: Optional[float] = None) -> dict:
    """Modify Stop Loss (sl) and/or Take Profit (tp) for an open position by Ticket ID."""
    return trading_tool.modify_position(ticket, sl, tp)

@mcp.tool()
def mt5_close_position(ticket: int, volume: Optional[float] = None) -> dict:
    """Close an open position (or partially close if volume is specified) by Ticket ID."""
    return trading_tool.close_position(ticket, volume)

@mcp.tool()
def mt5_close_all_positions(symbol: Optional[str] = None) -> dict:
    """Emergency close all open positions or all positions for a specific symbol."""
    return trading_tool.close_all_positions(symbol)

@mcp.tool()
def mt5_close_profitable_positions(symbol: Optional[str] = None, min_profit_usd: float = 0.0) -> dict:
    """Close only profitable open positions (floating profit > min_profit_usd) to instantly lock in gains."""
    return trading_tool.close_profitable_positions(symbol, min_profit_usd)

@mcp.tool()
def mt5_close_losing_positions(symbol: Optional[str] = None, max_loss_usd: float = 0.0) -> dict:
    """Close only losing open positions (floating loss < -abs(max_loss_usd)) to cut losses immediately."""
    return trading_tool.close_losing_positions(symbol, max_loss_usd)

@mcp.tool()
def mt5_close_by_comment(comment_query: str, symbol: Optional[str] = None) -> dict:
    """Close open positions matching a specific comment / strategy tag (e.g. 'AI_SMC', 'Manual', 'Breakout')."""
    return trading_tool.close_by_comment(comment_query, symbol)

@mcp.tool()
def mt5_close_by_magic(magic_number: int, symbol: Optional[str] = None) -> dict:
    """Close open positions matching a specific Magic Number (Bot ID)."""
    return trading_tool.close_by_magic(magic_number, symbol)

@mcp.tool()
def mt5_get_pending_orders(symbol: Optional[str] = None) -> dict:
    """Get all active pending orders or filter by symbol."""
    return trading_tool.get_pending_orders(symbol)

@mcp.tool()
def mt5_cancel_pending_order(ticket: int) -> dict:
    """Cancel a single pending order by ticket ID."""
    return trading_tool.cancel_pending_order(ticket)

@mcp.tool()
def mt5_cancel_all_pending_orders(symbol: Optional[str] = None) -> dict:
    """Cancel all active pending orders (BUY_STOP, SELL_STOP, BUY_LIMIT, SELL_LIMIT) in one click."""
    return trading_tool.cancel_all_pending_orders(symbol)

@mcp.tool()
def mt5_get_trade_history(days: int = 7, symbol: Optional[str] = None) -> dict:
    """Get closed trade deals and profit history for the past N days."""
    return trading_tool.get_trade_history(days, symbol)

# =====================================================================
# 7. AUTONOMOUS AGENT TOOLS
# =====================================================================

@mcp.tool()
def mt5_agent_start(
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    strategy: str = "smc",
    scan_interval: int = 15,
    auto_trade: bool = False,
    risk_percent: float = 1.0,
    rr_ratio: float = 2.0,
    enable_breakeven: bool = True,
    be_trigger_points: float = 300.0
) -> dict:
    """Start the autonomous background AI trading agent. Set auto_trade=True to execute orders directly, or False for Signal & Telegram alerts only."""
    return agent_tool.agent_start(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        scan_interval=scan_interval,
        auto_trade=auto_trade,
        risk_percent=risk_percent,
        rr_ratio=rr_ratio,
        enable_breakeven=enable_breakeven,
        be_trigger_points=be_trigger_points
    )

@mcp.tool()
def mt5_agent_stop() -> dict:
    """Stop the background autonomous AI trading agent."""
    return agent_tool.agent_stop()

@mcp.tool()
def mt5_agent_status() -> dict:
    """Get the live status, uptime, scan counts, and signals generated by the autonomous agent."""
    return agent_tool.agent_status()

@mcp.tool()
def mt5_send_test_alert(message: str = "Test alert from popmely AI trading bot!") -> dict:
    """Send a test notification to Telegram or configured Webhook."""
    return agent_tool.send_test_alert(message)

# =====================================================================
# 8. CREDIT SCORE TOOLS (Risk Management Scoring)
# =====================================================================

@mcp.tool()
def mt5_score_init(max_score: float = 100.0, initial_balance: float = 10000.0, base_multiplier: float = 100.0, recovery_rate: float = 0.5) -> dict:
    """Initialize the Trading Credit Score system. Set your own starting score and reference balance. The score controls risk behavior:
    - GREEN (70-100%): Normal trading, full lot size
    - YELLOW (50-70%): Cautious mode, lot size reduced 50%
    - ORANGE (30-50%): Warning mode, lot size reduced 75% + alerts
    - CRITICAL (<30%): STOP TRADING, signal-only mode + urgent alerts
    Points are deducted on SL hits and partially recovered on TP hits."""
    return score_tool.score_init(max_score, initial_balance, base_multiplier, recovery_rate)

@mcp.tool()
def mt5_score_status() -> dict:
    """Get current credit score, tier (GREEN/YELLOW/ORANGE/CRITICAL), lot multiplier, streaks, and cumulative statistics."""
    return score_tool.score_status()

@mcp.tool()
def mt5_score_deduct(loss_usd: float, reason: str = "SL Hit") -> dict:
    """Deduct points from credit score based on a realized trading loss (SL hit). Automatically applies losing streak multiplier penalty."""
    return score_tool.score_deduct(loss_usd, reason)

@mcp.tool()
def mt5_score_recover(profit_usd: float) -> dict:
    """Recover credit score points based on a realized trading profit (TP hit). Recovery rate is 50% of deduction rate."""
    return score_tool.score_recover(profit_usd)

@mcp.tool()
def mt5_score_reset() -> dict:
    """Reset credit score back to max value without changing configuration."""
    return score_tool.score_reset()

@mcp.tool()
def mt5_score_set(score: float) -> dict:
    """Manually set the credit score to a specific value between 0 and max_score."""
    return score_tool.score_set(score)

@mcp.tool()
def mt5_score_history(limit: int = 20) -> dict:
    """View the recent credit score change history log with timestamps, event types, and details."""
    return score_tool.score_history(limit)

# =====================================================================
# 8. MCP RESOURCES (Read-only context for AI)
# =====================================================================

@mcp.resource("mt5://account/status")
def get_account_resource() -> str:
    """Read-only live MT5 account balance, equity, and margin status."""
    acc = account_tool.get_account_info()
    return json.dumps(acc, indent=2)

@mcp.resource("mt5://positions/active")
def get_positions_resource() -> str:
    """Read-only list of all currently active open positions."""
    pos = trading_tool.get_positions()
    return json.dumps(pos, indent=2)

@mcp.resource("mt5://config/limits")
def get_config_resource() -> str:
    """Read-only safety limits and configuration."""
    return json.dumps({
        "max_lot_size": config.MAX_LOT_SIZE,
        "default_symbol": config.DEFAULT_SYMBOL,
        "default_magic": config.DEFAULT_MAGIC,
        "require_sl": config.REQUIRE_SL
    }, indent=2)

@mcp.resource("mt5://score/status")
def get_score_resource() -> str:
    """Read-only credit score status including tier, lot multiplier, and score percentage."""
    return json.dumps(score_tool.score_status(), indent=2)

# =====================================================================
# 9. MCP PROMPTS (Pre-built prompts for LLM)
# =====================================================================

@mcp.prompt()
def daily_market_briefing(symbol: str = "XAUUSD") -> str:
    """Generate a daily market overview, account health check, and credit score review."""
    return f"""Please perform a comprehensive market briefing for {symbol}:
1. Check MT5 account balance, equity, and current margin.
2. **Check Credit Score status** (mt5_score_status) - review current tier and lot multiplier.
3. Get the real-time quote for {symbol}.
4. Perform technical analysis (EMA, RSI, MACD, ATR) on H1 and M15 timeframes.
5. Perform SMC analysis (Market Structure, Order Blocks, FVGs).
6. Give a concise summary with high-probability trade zones for today.

IMPORTANT: If the credit score is in YELLOW/ORANGE/CRITICAL tier, flag this prominently and adjust recommendations accordingly."""

@mcp.prompt()
def smc_trade_setup(symbol: str = "XAUUSD", risk_percent: float = 1.0) -> str:
    """Generate a full SMC trade plan with risk calculation and credit score awareness."""
    return f"""Analyze {symbol} using Smart Money Concepts:
1. **First, check Credit Score** (mt5_score_status). If CRITICAL, DO NOT suggest any trades - signal only.
2. Identify the current market structure (BOS/CHoCH).
3. Find any active unmitigated Order Blocks (OB) or Fair Value Gaps (FVG).
4. Determine if current price is in Premium (Sell) or Discount (Buy) zone.
5. If a valid setup exists and credit score allows trading, calculate optimal Lot Size for {risk_percent}% risk (adjusted by credit score lot_multiplier) and suggest Entry, SL, and TP (1:2 R:R).

Note: The credit score system automatically adjusts lot size:
- GREEN (70-100%): Full lot | YELLOW (50-70%): 50% lot | ORANGE (30-50%): 25% lot | CRITICAL (<30%): NO TRADE"""

# =====================================================================
# 10. MAIN ENTRYPOINT
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description=f"popmely v{__version__} - MetaTrader 5 MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="MCP transport protocol (default: stdio)")
    parser.add_argument("--host", default="127.0.0.1", help="Host for SSE transport")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE transport")
    args = parser.parse_args()

    logger.info(f"Starting popmely MT5 MCP Server v{__version__} on {args.transport} transport...")

    if args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
