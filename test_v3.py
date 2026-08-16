import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.mt5_connection import MT5ConnectionManager
import mcp_tools.agent_tools as agent_tool

def test_v3():
    print("=" * 65)
    print(" Testing popmely v3: Autonomous AI Strategy Agent")
    print("=" * 65)

    if not MT5ConnectionManager.ensure_connected():
        print("[!] MT5 not connected.")
        return

    # 1. Start Autonomous Agent in Signal-Only Mode
    print("\n--- 1. Starting Autonomous Agent (Signal-Only, 5s scan) ---")
    start_res = agent_tool.agent_start(
        symbol="XAUUSD",
        timeframe="M15",
        strategy="smc",
        scan_interval=5,
        auto_trade=False,
        risk_percent=1.0,
        enable_breakeven=True
    )
    print(json.dumps(start_res, indent=2))

    # 2. Wait and check status
    print("\n--- 2. Monitoring Agent Background Worker for 12 seconds... ---")
    for i in range(3):
        time.sleep(4)
        status = agent_tool.agent_status()
        print(f"Cycle {i+1}: Uptime={status['agent']['uptime']}, Scans={status['agent']['scan_count']}, Signals={status['agent']['signals_generated']}")

    # 3. Final Agent Status
    print("\n--- 3. Full Agent Status ---")
    print(json.dumps(agent_tool.agent_status(), indent=2))

    # 4. Stop Agent
    print("\n--- 4. Stopping Autonomous Agent ---")
    stop_res = agent_tool.agent_stop()
    print(json.dumps(stop_res, indent=2))

    print("\n" + "=" * 65)
    print(" v3 Testing Completed Successfully!")
    print("=" * 65)

if __name__ == "__main__":
    test_v3()
