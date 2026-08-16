import sys
import logging
import MetaTrader5 as mt5
from typing import Dict, Any
from popmely.config import config

logger = logging.getLogger("popmely.mt5_connection")

class MT5ConnectionManager:
    """Manages the lifecycle of the MetaTrader 5 connection."""

    _initialized = False

    @classmethod
    def ensure_connected(cls) -> bool:
        """Checks if MT5 is connected; if not, attempts to initialize/connect."""
        if cls._initialized and mt5.terminal_info() is not None:
            return True

        logger.info("Initializing MetaTrader 5 connection...")
        
        init_args = {}
        if config.PATH:
            init_args["path"] = config.PATH

        if not mt5.initialize(**init_args):
            err = mt5.last_error()
            logger.error(f"MT5 initialize failed: {err}")
            cls._initialized = False
            return False

        # Login if account is specified
        if config.ACCOUNT and config.PASSWORD and config.SERVER:
            authorized = mt5.login(
                login=config.ACCOUNT,
                password=config.PASSWORD,
                server=config.SERVER
            )
            if not authorized:
                err = mt5.last_error()
                logger.error(f"MT5 login failed for account {config.ACCOUNT}: {err}")
                cls._initialized = False
                return False

        cls._initialized = True
        logger.info("MetaTrader 5 connected successfully.")
        return True

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Returns the connection and terminal status."""
        if not cls.ensure_connected():
            return {
                "connected": False,
                "error": str(mt5.last_error())
            }

        terminal = mt5.terminal_info()
        version = mt5.version()

        if terminal is None:
            return {"connected": False, "error": "Unable to get terminal info"}

        return {
            "connected": True,
            "version": version,
            "trade_allowed": terminal.trade_allowed,
            "connected_to_broker": terminal.connected,
            "dlls_allowed": terminal.dlls_allowed,
            "company": terminal.company,
            "name": terminal.name,
            "ping_last": terminal.ping_last
        }

    @classmethod
    def shutdown(cls):
        """Shuts down the connection to MT5."""
        if cls._initialized:
            mt5.shutdown()
            cls._initialized = False
            logger.info("MetaTrader 5 connection closed.")
