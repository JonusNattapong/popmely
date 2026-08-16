import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class MT5Config:
    # Optional MT5 account credentials (if empty, MT5 will use currently logged-in account in terminal)
    ACCOUNT: int = int(os.getenv("MT5_ACCOUNT", "0"))
    PASSWORD: str = os.getenv("MT5_PASSWORD", "")
    SERVER: str = os.getenv("MT5_SERVER", "")
    PATH: str = os.getenv("MT5_PATH", "")  # Path to terminal64.exe if custom installation

    # Default trading settings
    DEFAULT_SYMBOL: str = os.getenv("DEFAULT_SYMBOL", "XAUUSD")
    DEFAULT_MAGIC: int = int(os.getenv("DEFAULT_MAGIC", "112233"))
    DEFAULT_DEVIATION: int = int(os.getenv("DEFAULT_DEVIATION", "20"))
    MAX_SLIPPAGE_POINTS: int = int(os.getenv("MAX_SLIPPAGE_POINTS", "50"))
    
    # Safety settings
    MAX_LOT_SIZE: float = float(os.getenv("MAX_LOT_SIZE", "1.0"))
    MAX_DAILY_DRAWDOWN_PERCENT: float = float(os.getenv("MAX_DAILY_DRAWDOWN_PERCENT", "5.0"))
    REQUIRE_SL: bool = os.getenv("REQUIRE_SL", "false").lower() in ("true", "1", "yes")

config = MT5Config()
