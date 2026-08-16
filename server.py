import sys
import os
import logging
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp.server.fastmcp import FastMCP
from utils.mt5_connection import MT5ConnectionManager
import mcp_tools.account as account_tool
import mcp_tools.market_data as market_tool
import mcp_tools.analysis as analysis_tool
import mcp_tools.risk_manager as risk_tool
import mcp_tools.trading as trading_tool
import mcp_tools.smc_analyzer as smc_tool
import mcp_tools.backtest_engine as backtest_tool

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mt5_mcp_server")

# Initialize FastMCP Server
mcp = FastMCP("MT5-Trading-Server")

# ----------------- Account & Terminal Tools -----------------

@mcp.tool()
def mt5_account_info() -> dict:
    """Retrieve detailed information about the current MT5 trading account (Balance, Equity, Margin, Leverage, Profit)."""
    return account_tool.get_account_info()

@mcp.tool()
def mt5_terminal_status() -> dict:
    """Check MetaTrader 5 terminal status, connection to broker, and whether automated trading is enabled."""
    return account_tool.get_terminal_status()

# ----------------- Market Data Tools -----------------

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

# ----------------- Technical Analysis Tools -----------------

@mcp.tool()
def mt5_analyze_technical(symbol: str = "XAUUSD", timeframe: str = "M15", count: int = 100) -> dict:
    """Perform automated technical analysis on a symbol. Calculates EMA (20/50/200), RSI (14), MACD, ATR, Bollinger Bands, and Key Support/Resistance Levels."""
    return analysis_tool.analyze_technical(symbol, timeframe, count)

# ----------------- Risk Management Tools -----------------

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

# ----------------- Trading & Order Management Tools -----------------

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

# ----------------- Smart Money Concept (SMC) Tools -----------------

@mcp.tool()
def mt5_analyze_smc(symbol: str = "XAUUSD", timeframe: str = "M15", count: int = 150) -> dict:
    """Perform Smart Money Concept (SMC) analysis: Break of Structure (BOS), Change of Character (CHoCH), Order Blocks (OB), Fair Value Gaps (FVG), Liquidity Pools (EQH/EQL), and Premium vs Discount zones."""
    return smc_tool.analyze_smc(symbol, timeframe, count)

# ----------------- Backtest Engine Tools -----------------

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

if __name__ == "__main__":
    logger.info("Starting MT5 MCP Server on standard I/O transport...")
    mcp.run(transport="stdio")
