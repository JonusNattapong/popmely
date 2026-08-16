import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.mt5_connection import MT5ConnectionManager
import mcp_tools.account as account_tool
import mcp_tools.market_data as market_tool
import mcp_tools.analysis as analysis_tool
import mcp_tools.risk_manager as risk_tool
import mcp_tools.trading as trading_tool

def run_tests():
    print("=" * 60)
    print(" Testing MT5 Connection & Tools")
    print("=" * 60)

    # 1. Connection test
    connected = MT5ConnectionManager.ensure_connected()
    print(f"1. MT5 Connected: {connected}")
    
    status = account_tool.get_terminal_status()
    print(f"2. Terminal Status:\n{json.dumps(status, indent=2)}")

    if not connected:
        print("\n[!] Note: MetaTrader 5 terminal is not currently running or reachable.")
        print("Please launch your MT5 terminal and login to your demo/live account.")
        return

    # 3. Account info
    acc = account_tool.get_account_info()
    print(f"\n3. Account Info:\n{json.dumps(acc, indent=2)}")

    # 4. Search symbol for Gold
    symbols = market_tool.search_symbols("XAU")
    print(f"\n4. Search Gold Symbols:\n{json.dumps(symbols, indent=2)}")

    symbol_name = "XAUUSD"
    if symbols.get("count", 0) > 0:
        symbol_name = symbols["data"][0]["name"]

    print(f"\nUsing Symbol: {symbol_name}")

    # 5. Quote
    quote = market_tool.get_quote(symbol_name)
    print(f"\n5. Live Quote ({symbol_name}):\n{json.dumps(quote, indent=2)}")

    # 6. Technical Analysis
    analysis = analysis_tool.analyze_technical(symbol_name, "M15")
    print(f"\n6. Technical Analysis ({symbol_name} M15):\n{json.dumps(analysis, indent=2)}")

    # 7. Risk calculation
    if quote.get("status") == "success":
        bid = quote["data"]["bid"]
        sl_price = bid - 5.0  # 5 dollars SL for gold
        tp_price = bid + 10.0 # 10 dollars TP
        risk = risk_tool.calculate_lot_size(
            symbol=symbol_name,
            entry_price=bid,
            stop_loss_price=sl_price,
            take_profit_price=tp_price,
            risk_percent=1.0
        )
        print(f"\n7. Risk Calculation (1% Risk):\n{json.dumps(risk, indent=2)}")

    # 8. Open positions
    positions = trading_tool.get_positions()
    print(f"\n8. Open Positions:\n{json.dumps(positions, indent=2)}")

    print("\n" + "=" * 60)
    print(" Tests Completed Successfully!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
