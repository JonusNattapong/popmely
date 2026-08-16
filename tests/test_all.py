import unittest
import json
from popmely.utils.mt5_connection import MT5ConnectionManager
import popmely.tools.account as account_tool
import popmely.tools.market_data as market_tool
import popmely.tools.analysis as analysis_tool
import popmely.tools.smc as smc_tool
import popmely.tools.backtest as backtest_tool
import popmely.tools.risk as risk_tool
import popmely.tools.agent as agent_tool

class TestFullPopmelySuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        MT5ConnectionManager.ensure_connected()

    def test_01_account_status(self):
        status = account_tool.get_terminal_status()
        self.assertIn("status", status)

    def test_02_symbol_search(self):
        res = market_tool.search_symbols("XAU")
        self.assertIn("status", res)
        self.assertEqual(res["status"], "success")

    def test_03_technical_analysis(self):
        res = analysis_tool.analyze_technical("XAUUSD", "M15", 50)
        self.assertIn("status", res)

    def test_04_smc_analysis(self):
        res = smc_tool.analyze_smc("XAUUSD", "M15", 100)
        self.assertIn("status", res)

    def test_05_backtest(self):
        res = backtest_tool.run_backtest(symbol="XAUUSD", timeframe="M15", strategy="smc", bars_count=300)
        self.assertIn("status", res)

    def test_06_risk_calc(self):
        res = risk_tool.calculate_lot_size("XAUUSD", entry_price=2600.0, stop_loss_price=2595.0, risk_percent=1.0)
        self.assertIn("status", res)

    def test_07_agent_lifecycle(self):
        start = agent_tool.agent_start(symbol="XAUUSD", timeframe="M15", scan_interval=60, auto_trade=False)
        self.assertIn("status", start)
        status = agent_tool.agent_status()
        self.assertTrue(status["agent"]["running"])
        stop = agent_tool.agent_stop()
        self.assertEqual(stop["status"], "success")

if __name__ == "__main__":
    unittest.main()
