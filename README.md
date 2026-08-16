# 📈 popmely - MetaTrader 5 (MT5) Model Context Protocol (MCP) Server

[![Version](https://img.shields.io/badge/version-3.1.0-blue.svg)](https://github.com/JonusNattapong/popmely)
[![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Standard%20Server-purple.svg)](https://modelcontextprotocol.io/)

A high-performance, production-ready **Model Context Protocol (MCP) Server** that bridges **MetaTrader 5 (MT5)** with AI models (Claude, Antigravity, Cursor, OpenAI Agents). It empowers AI to monitor live market data, execute Smart Money Concepts (SMC) analysis, run bar-by-bar backtests, manage risk, and run an autonomous trading bot with Telegram alerts.

---

## 🌟 Standard MCP Capabilities

### 🛠️ 1. Tools (19 Interactive Tools)
* **💼 Account & Terminal:** `mt5_account_info`, `mt5_terminal_status`
* **📊 Market Data:** `mt5_get_quote`, `mt5_get_candles`, `mt5_search_symbols`, `mt5_get_symbol_info`
* **📈 Technical Analysis:** `mt5_analyze_technical` (EMA 20/50/200, RSI, MACD, ATR, Bollinger Bands)
* **🧠 Smart Money Concepts (SMC):** `mt5_analyze_smc` (BOS, CHoCH, Order Blocks, FVGs, Liquidity, OTE 61.8%-78.6%)
* **🔬 Backtest Engine:** `mt5_run_backtest` (Win Rate %, Max DD %, Profit Factor, Trade logs)
* **🤖 Autonomous AI Agent:** `mt5_agent_start`, `mt5_agent_stop`, `mt5_agent_status`, `mt5_send_test_alert`
* **🧮 Risk Management:** `mt5_calculate_lot_size` (Lot size per $ or % risk, R:R ratio)
* **⚡ Order Execution:** `mt5_place_order`, `mt5_place_pending_order`, `mt5_get_positions`, `mt5_modify_position`, `mt5_close_position`, `mt5_close_all_positions`, `mt5_get_trade_history`

### 📚 2. Resources (Read-only Context)
* `mt5://account/status`: Live Account Balance, Equity, and Margin
* `mt5://positions/active`: Live Open Positions and floating PnL
* `mt5://config/limits`: Safety limits and configuration

### 💡 3. Prompts (Pre-built AI Templates)
* `daily_market_briefing`: Comprehensive morning market overview and health check
* `smc_trade_setup`: Full SMC market structure analysis & risk-managed trade plan

---

## 🚀 Installation & Setup

### Prerequisites
1. **Windows OS**
2. [MetaTrader 5](https://www.metatrader5.com/) installed and logged into an account (Demo or Live). Enable Algo Trading: `Tools` > `Options` > `Expert Advisors` > Check `Allow Algo Trading`.
3. Python 3.10+

### Option A: Install from source (Editable mode)
```bash
git clone https://github.com/JonusNattapong/popmely.git
cd popmely
pip install -e .
```

### Option B: Run via `uvx` (or `pipx`)
```bash
uvx --from git+https://github.com/JonusNattapong/popmely.git popmely
```

---

## ⚙️ MCP Client Configuration

### Claude Desktop / Antigravity IDE (`claude_desktop_config.json` or `mcp.json`)

#### If installed via pip (`popmely` command or module):
```json
{
  "mcpServers": {
    "popmely": {
      "command": "python",
      "args": [
        "-m",
        "popmely"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

#### If referencing directory directly:
```json
{
  "mcpServers": {
    "popmely": {
      "command": "python",
      "args": [
        "d:\\Projects\\Github\\popmely\\server.py"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

---

## 🧪 Testing

Run the full automated test suite:
```bash
python -m unittest discover -s tests
```

---

## 📄 License
MIT License. Created by [JonusNattapong](https://github.com/JonusNattapong).
