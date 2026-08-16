import os
import logging
import requests
from typing import Optional, Dict, Any
from popmely.config import config

logger = logging.getLogger("popmely.notifier")

class AlertNotifier:
    """Manages multi-channel notifications (Telegram, Discord/Webhooks, Console)."""

    def __init__(self, telegram_token: Optional[str] = None, telegram_chat_id: Optional[str] = None, webhook_url: Optional[str] = None):
        self.telegram_token = telegram_token or config.TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = telegram_chat_id or config.TELEGRAM_CHAT_ID
        self.webhook_url = webhook_url or config.WEBHOOK_URL

    def send_telegram(self, message: str, parse_mode: str = "HTML", token: Optional[str] = None, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Send custom/freeform message via Telegram Bot API."""
        bot_token = token or self.telegram_token
        target_chat_id = chat_id or self.telegram_chat_id

        if not bot_token or not target_chat_id:
            return {
                "status": "warning",
                "message": "Telegram token or chat_id not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env or pass them directly."
            }

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": target_chat_id,
            "text": message,
            "parse_mode": parse_mode
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram alert sent successfully.")
                return {
                    "status": "success",
                    "chat_id": target_chat_id,
                    "message_length": len(message),
                    "delivered": True
                }
            else:
                return {
                    "status": "error",
                    "status_code": resp.status_code,
                    "message": f"Telegram API error: {resp.text}"
                }
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
            return {"status": "error", "message": f"Connection error: {e}"}

    def send_telegram_photo(self, photo_path: str, caption: Optional[str] = None, token: Optional[str] = None, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Send an image/chart (.png, .jpg) with optional caption to Telegram."""
        bot_token = token or self.telegram_token
        target_chat_id = chat_id or self.telegram_chat_id

        if not bot_token or not target_chat_id:
            return {
                "status": "warning",
                "message": "Telegram token or chat_id not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env or pass them directly."
            }

        if not os.path.exists(photo_path):
            return {"status": "error", "message": f"Photo file not found at '{photo_path}'"}

        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        data = {"chat_id": target_chat_id}
        if caption:
            data["caption"] = caption
            data["parse_mode"] = "HTML"

        try:
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                resp = requests.post(url, data=data, files=files, timeout=15)

            if resp.status_code == 200:
                logger.info(f"Telegram photo sent successfully: {photo_path}")
                return {
                    "status": "success",
                    "chat_id": target_chat_id,
                    "photo_path": photo_path,
                    "delivered": True
                }
            else:
                return {
                    "status": "error",
                    "status_code": resp.status_code,
                    "message": f"Telegram API photo error: {resp.text}"
                }
        except Exception as e:
            logger.error(f"Error sending Telegram photo: {e}")
            return {"status": "error", "message": f"Connection error: {e}"}

    def send_webhook(self, data: Dict[str, Any]) -> bool:
        """Send JSON payload to generic webhook / Discord."""
        if not self.webhook_url:
            return False

        try:
            resp = requests.post(self.webhook_url, json=data, timeout=10)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Error sending Webhook alert: {e}")
            return False

    def notify_signal(self, symbol: str, action: str, price: float, sl: float, tp: float, strategy: str, lot: Optional[float] = None, reason: str = "") -> bool:
        """Notify when a new trade signal is generated or an order is opened."""
        icon = "🟢" if action.upper() == "BUY" else "🔴"
        lot_str = f"\n📦 <b>Lot Size:</b> {lot}" if lot else ""
        reason_str = f"\n💡 <b>Reason:</b> {reason}" if reason else ""

        msg = (
            f"{icon} <b>[POPMELY SIGNAL] {action.upper()} {symbol}</b>\n\n"
            f"🎯 <b>Strategy:</b> {strategy}\n"
            f"💰 <b>Entry Price:</b> {price}\n"
            f"🛑 <b>Stop Loss:</b> {sl}\n"
            f"🎯 <b>Take Profit:</b> {tp}{lot_str}{reason_str}\n"
            f"⏰ <b>Status:</b> Signal Generated"
        )
        logger.info(f"Signal Alert: {action} {symbol} @ {price}")
        t_ok = self.send_telegram(msg)
        w_ok = self.send_webhook({"event": "signal", "symbol": symbol, "action": action, "price": price, "sl": sl, "tp": tp})
        return t_ok or w_ok

    def notify_breakeven(self, symbol: str, ticket: int, entry_price: float, new_sl: float) -> bool:
        """Notify when SL has been moved to Breakeven."""
        msg = (
            f"🛡️ <b>[AUTO BREAKEVEN] {symbol}</b>\n\n"
            f"🎫 <b>Ticket:</b> #{ticket}\n"
            f"🔒 <b>Stop Loss Updated:</b> {new_sl} (Risk Eliminated)\n"
            f"💰 <b>Entry Price:</b> {entry_price}"
        )
        logger.info(f"Breakeven Alert: #{ticket} {symbol} SL moved to {new_sl}")
        return self.send_telegram(msg)

    def notify_close(self, symbol: str, ticket: int, profit_usd: float, close_price: float, balance: float) -> bool:
        """Notify when an order has been closed."""
        icon = "🎉" if profit_usd >= 0 else "🛑"
        res_str = "PROFIT" if profit_usd >= 0 else "LOSS"

        msg = (
            f"{icon} <b>[TRADE CLOSED - {res_str}] {symbol}</b>\n\n"
            f"🎫 <b>Ticket:</b> #{ticket}\n"
            f"💵 <b>PnL:</b> ${profit_usd:+.2f} USD\n"
            f"🏁 <b>Close Price:</b> {close_price}\n"
            f"💼 <b>Account Balance:</b> ${balance:,.2f} USD"
        )
        logger.info(f"Close Alert: #{ticket} {symbol} PnL: ${profit_usd:+.2f}")
        return self.send_telegram(msg)

notifier = AlertNotifier()
