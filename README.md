# 📈 popmely - MT5 Trading MCP Server

A high-performance **Model Context Protocol (MCP) Server** that bridges **MetaTrader 5 (MT5)** with AI models (Claude, Antigravity, Cursor, OpenAI Agents). It enables AI to monitor real-time market data, perform automated technical analysis, calculate risk-adjusted lot sizes, and execute trades directly via natural language chat.

---

## 🌟 Key Features & Tools

### 1. 💼 Account & Terminal
* `mt5_account_info`: Retrieve Balance, Equity, Free Margin, Leverage, Profit.
* `mt5_terminal_status`: Check MT5 connection and whether Algo Trading is enabled.

### 2. 📊 Market Data & Quotes
* `mt5_get_quote`: Live Bid/Ask/Spread for `XAUUSD`, Forex pairs, or Crypto.
* `mt5_get_candles`: Historical OHLCV bars for M1, M5, M15, H1, H4, D1.
* `mt5_search_symbols`: Search matching broker symbols (e.g. `XAUUSD`, `GOLD`).
* `mt5_get_symbol_info`: Digits, Point, Contract Size, Tick Value, Min/Max Lot.

### 3. 📈 Automated Technical Analysis
* `mt5_analyze_technical`: Calculates EMA (20/50/200), RSI (14), MACD, ATR (14), Bollinger Bands, and Key Support/Resistance levels automatically.

### 4. 🧠 Smart Money Concepts (SMC) Analyzer (v2)
* `mt5_analyze_smc`: Advanced institutional market structure analysis:
  * **Break of Structure (BOS)** & **Change of Character (CHoCH)**
  * **Unmitigated Order Blocks (OB)**
  * **Fair Value Gaps (FVG / Imbalances)**
  * **Liquidity Pools (Equal Highs / Equal Lows)**
  * **Premium vs Discount Zones & OTE (Optimal Trade Entry 61.8%-78.6%)**

### 5. 🔬 Backtest Engine (v2)
* `mt5_run_backtest`: Fast bar-by-bar historical simulation:
  * Supported Strategies: `smc` (BOS/FVG entries) & `ema_rsi` (Trend Pullback)
  * Computes: Win Rate (%), Total Trades, Net Profit ($ / %), Profit Factor, Max Drawdown ($ / %), and detailed recent Trade Logs.

### 6. 🧮 Risk Management & Lot Sizing
* `mt5_calculate_lot_size`: Calculates optimal Lot Size according to risk in USD or % of equity, Stop Loss distance, and computes Risk/Reward ratio.

### 7. ⚡ Trading & Position Management
* `mt5_place_order`: Execute Market BUY / SELL orders with Stop Loss, Take Profit, and Slippage controls.
* `mt5_place_pending_order`: Place Buy Limit / Sell Limit / Buy Stop / Sell Stop orders.
* `mt5_get_positions`: View all open positions and floating PnL.
* `mt5_modify_position`: Modify SL / TP for open positions (Trailing SL / Breakeven).
* `mt5_close_position`: Close a single position or execute Partial Close.
* `mt5_close_all_positions`: Emergency close all open positions.
* `mt5_get_pending_orders`: View active pending orders.
* `mt5_cancel_pending_order`: Cancel pending orders.
* `mt5_get_trade_history`: View closed deals and realized PnL history.

---

## 🚀 Setup & Configuration

### Prerequisites
1. Windows OS
2. [MetaTrader 5](https://www.metatrader5.com/) installed and running (with Algo Trading enabled in MT5: `Tools` > `Options` > `Expert Advisors` > Check `Allow Algo Trading`).
3. Python 3.10+

### Installation
```bash
pip install -r requirements.txt
```

### Quick Diagnostic Test
Run the self-test to verify MT5 terminal connection and indicators:
```bash
python test_mt5.py
```

---

## ⚙️ MCP Client Configuration

Add this server to your MCP client config (e.g., Claude Desktop, Antigravity, Cursor, etc.):

### `mcp.json` / Claude Desktop Config (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "mt5-trading": {
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

## 💬 Example AI Prompts

* *"เช็กราคาทอง XAUUSD ตอนนี้ พร้อมวิเคราะห์แนวโน้ม M15"*
* *"ช่วยคำนวณ Lot Size ถ้ายอมเสี่ยงขาดทุน 1% ของพอร์ต โดยตั้ง SL ห่าง 400 จุด"*
* *"เปิด Buy XAUUSD 0.05 lot โดยตั้ง SL ที่ 2640 และ TP ที่ 2660"*
* *"ดูออเดอร์ที่เปิดค้างอยู่ตอนนี้ มีกำไร/ขาดทุนเท่าไหร่บ้าง"*
* *"ขยับ Stop Loss ของไม้ทอง ticket #12345 ไปที่ราคาหน้าทุน (Breakeven)"*
