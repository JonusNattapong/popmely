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
def mt5_get_pending_orders(symbol: Optional[str] = None) -> dict:
    """Get all active pending orders or filter by symbol."""
    return trading_tool.get_pending_orders(symbol)

@mcp.tool()
def mt5_cancel_pending_order(ticket: int) -> dict:
    """Cancel a pending order by ticket ID."""
    return trading_tool.cancel_pending_order(ticket)

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

# =====================================================================
# 9. MCP PROMPTS (Pre-built prompts for LLM)
# =====================================================================

@mcp.prompt()
def daily_market_briefing(symbol: str = "XAUUSD") -> str:
    """Generate a daily market overview and account health check."""
    return f"""Please perform a comprehensive market briefing for {symbol}:
1. Check MT5 account balance, equity, and current margin.
2. Get the real-time quote for {symbol}.
3. Perform technical analysis (EMA, RSI, MACD, ATR) on H1 and M15 timeframes.
4. Perform SMC analysis (Market Structure, Order Blocks, FVGs).
5. Give a concise summary with high-probability trade zones for today."""

@mcp.prompt()
def smc_trade_setup(symbol: str = "XAUUSD", risk_percent: float = 1.0) -> str:
    """Generate a full SMC trade plan with risk calculation."""
    return f"""Analyze {symbol} using Smart Money Concepts:
1. Identify the current market structure (BOS/CHoCH).
2. Find any active unmitigated Order Blocks (OB) or Fair Value Gaps (FVG).
3. Determine if current price is in Premium (Sell) or Discount (Buy) zone.
4. If a valid setup exists, calculate optimal Lot Size for {risk_percent}% risk and suggest Entry, SL, and TP (1:2 R:R)."""

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
