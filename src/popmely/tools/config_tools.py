"""Dynamic Configuration & Key Setup Tools for popmely.

Allows setting and updating runtime credentials (Telegram Bot Token, Chat ID, Webhooks,
Max Lot Size, Safety Limits) directly through MCP tools and persisting to .env.
"""

from typing import Dict, Any, Optional
import os
from pathlib import Path
from dotenv import set_key, find_dotenv

from popmely.config import config
from popmely.agent.notifier import notifier

ENV_PATH = Path(".env")


def mask_secret(secret: str) -> str:
    """Mask sensitive API keys / tokens for privacy."""
    if not secret:
        return "<Not Configured>"
    if len(secret) <= 8:
        return "***"
    return f"{secret[:4]}***{secret[-4:]}"


def get_config(masked: bool = True) -> Dict[str, Any]:
    """Retrieve current runtime configuration settings and credentials."""
    return {
        "status": "success",
        "telegram": {
            "bot_token": mask_secret(config.TELEGRAM_BOT_TOKEN) if masked else config.TELEGRAM_BOT_TOKEN,
            "chat_id": mask_secret(config.TELEGRAM_CHAT_ID) if masked else config.TELEGRAM_CHAT_ID,
            "configured": bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
        },
        "webhook": {
            "webhook_url": mask_secret(config.WEBHOOK_URL) if masked else config.WEBHOOK_URL,
            "configured": bool(config.WEBHOOK_URL)
        },
        "trading_defaults": {
            "default_symbol": config.DEFAULT_SYMBOL,
            "default_magic": config.DEFAULT_MAGIC,
            "default_deviation": config.DEFAULT_DEVIATION,
            "max_slippage_points": config.MAX_SLIPPAGE_POINTS
        },
        "safety_limits": {
            "max_lot_size": config.MAX_LOT_SIZE,
            "max_daily_drawdown_percent": config.MAX_DAILY_DRAWDOWN_PERCENT,
            "require_sl": config.REQUIRE_SL
        },
        "account_credentials": {
            "account": config.ACCOUNT if config.ACCOUNT else "<Auto/Active Terminal>",
            "server": config.SERVER if config.SERVER else "<Auto/Active Terminal>",
            "path": config.PATH if config.PATH else "<Default Path>"
        }
    }


def set_config(
    telegram_bot_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    webhook_url: Optional[str] = None,
    default_symbol: Optional[str] = None,
    default_magic: Optional[int] = None,
    default_deviation: Optional[int] = None,
    max_lot_size: Optional[float] = None,
    max_daily_drawdown_percent: Optional[float] = None,
    require_sl: Optional[bool] = None,
    persist_to_env: bool = True
) -> Dict[str, Any]:
    """Dynamically set API keys, Telegram credentials, or trading safety limits via MCP and optionally persist to .env."""
    updated_keys = []
    env_file = find_dotenv() or str(ENV_PATH)

    # Ensure .env file exists if persisting
    if persist_to_env and not os.path.exists(env_file):
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("# popmely Environment Configuration\n")

    # 1. Telegram
    if telegram_bot_token is not None:
        config.TELEGRAM_BOT_TOKEN = telegram_bot_token.strip()
        notifier.telegram_token = config.TELEGRAM_BOT_TOKEN
        updated_keys.append("TELEGRAM_BOT_TOKEN")
        if persist_to_env:
            set_key(env_file, "TELEGRAM_BOT_TOKEN", config.TELEGRAM_BOT_TOKEN)

    if telegram_chat_id is not None:
        config.TELEGRAM_CHAT_ID = telegram_chat_id.strip()
        notifier.telegram_chat_id = config.TELEGRAM_CHAT_ID
        updated_keys.append("TELEGRAM_CHAT_ID")
        if persist_to_env:
            set_key(env_file, "TELEGRAM_CHAT_ID", config.TELEGRAM_CHAT_ID)

    # 2. Webhook
    if webhook_url is not None:
        config.WEBHOOK_URL = webhook_url.strip()
        notifier.webhook_url = config.WEBHOOK_URL
        updated_keys.append("WEBHOOK_URL")
        if persist_to_env:
            set_key(env_file, "WEBHOOK_URL", config.WEBHOOK_URL)

    # 3. Trading Defaults
    if default_symbol is not None:
        config.DEFAULT_SYMBOL = default_symbol.strip().upper()
        updated_keys.append("DEFAULT_SYMBOL")
        if persist_to_env:
            set_key(env_file, "DEFAULT_SYMBOL", config.DEFAULT_SYMBOL)

    if default_magic is not None:
        config.DEFAULT_MAGIC = int(default_magic)
        updated_keys.append("DEFAULT_MAGIC")
        if persist_to_env:
            set_key(env_file, "DEFAULT_MAGIC", str(config.DEFAULT_MAGIC))

    if default_deviation is not None:
        config.DEFAULT_DEVIATION = int(default_deviation)
        updated_keys.append("DEFAULT_DEVIATION")
        if persist_to_env:
            set_key(env_file, "DEFAULT_DEVIATION", str(config.DEFAULT_DEVIATION))

    # 4. Safety Limits
    if max_lot_size is not None:
        config.MAX_LOT_SIZE = float(max_lot_size)
        updated_keys.append("MAX_LOT_SIZE")
        if persist_to_env:
            set_key(env_file, "MAX_LOT_SIZE", str(config.MAX_LOT_SIZE))

    if max_daily_drawdown_percent is not None:
        config.MAX_DAILY_DRAWDOWN_PERCENT = float(max_daily_drawdown_percent)
        updated_keys.append("MAX_DAILY_DRAWDOWN_PERCENT")
        if persist_to_env:
            set_key(env_file, "MAX_DAILY_DRAWDOWN_PERCENT", str(config.MAX_DAILY_DRAWDOWN_PERCENT))

    if require_sl is not None:
        config.REQUIRE_SL = bool(require_sl)
        updated_keys.append("REQUIRE_SL")
        if persist_to_env:
            set_key(env_file, "REQUIRE_SL", str(config.REQUIRE_SL).lower())

    return {
        "status": "success",
        "message": f"Successfully updated {len(updated_keys)} configuration settings." + (" (Persisted to .env)" if persist_to_env else " (In-memory only)"),
        "updated_keys": updated_keys,
        "current_config": get_config(masked=True)
    }
