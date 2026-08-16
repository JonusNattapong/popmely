import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.mt5_connection import MT5ConnectionManager
import mcp_tools.smc_analyzer as smc_tool
import mcp_tools.backtest_engine as backtest_tool

def test_v2():
    print("=" * 65)
    print(" Testing popmely v2: SMC Analyzer & Backtest Engine")
    print("=" * 65)

    if not MT5ConnectionManager.ensure_connected():
        print("[!] MT5 not connected.")
        return

    # 1. SMC Analysis on XAUUSD
    print("\n--- 1. SMC Analysis on XAUUSD (M15) ---")
    smc_res = smc_tool.analyze_smc("XAUUSD", "M15", count=150)
    print(json.dumps(smc_res, indent=2))

    # 2. Backtest SMC Strategy on XAUUSD
    print("\n--- 2. Backtesting SMC Strategy on XAUUSD (M15, 1,000 bars) ---")
    bt_smc = backtest_tool.run_backtest(
        symbol="XAUUSD",
        timeframe="M15",
        strategy="smc",
        bars_count=1000,
        start_balance=10000.0,
        risk_percent=1.0,
        rr_ratio=2.0
    )
    print(json.dumps(bt_smc, indent=2))

    # 3. Backtest EMA/RSI Strategy on XAUUSD
    print("\n--- 3. Backtesting EMA + RSI Strategy on XAUUSD (M15, 1,000 bars) ---")
    bt_ema = backtest_tool.run_backtest(
        symbol="XAUUSD",
        timeframe="M15",
        strategy="ema_rsi",
        bars_count=1000,
        start_balance=10000.0,
        risk_percent=1.0,
        rr_ratio=2.0
    )
    print(json.dumps(bt_ema, indent=2))

    print("\n" + "=" * 65)
    print(" v2 Testing Completed Successfully!")
    print("=" * 65)

if __name__ == "__main__":
    test_v2()
