"""Telegram notifications and emergency control commands."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

import requests

from .config import Settings

LOGGER = logging.getLogger(__name__)


class TelegramService:
    def __init__(
        self,
        settings: Settings,
        *,
        status_callback: Callable[[], str],
        positions_callback: Callable[[], str],
        stop_callback: Callable[[], None],
    ) -> None:
        self.settings = settings
        self.status_callback = status_callback
        self.positions_callback = positions_callback
        self.stop_callback = stop_callback
        self.session = requests.Session()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._offset = 0

    @property
    def enabled(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    @property
    def api_url(self) -> str:
        return f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    def send(self, message: str) -> None:
        if not self.enabled:
            return
        try:
            response = self.session.post(
                f"{self.api_url}/sendMessage",
                json={"chat_id": self.settings.telegram_chat_id, "text": message[:4096]},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException:
            LOGGER.exception("Telegram notification failed")

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._poll, name="telegram-poll", daemon=True)
        self._thread.start()
        self.send("TRADE bot started safely (paper-account guard enabled).")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def signal(self, text: str) -> None:
        self.send(f"SIGNAL\n{text}")

    def order(self, text: str) -> None:
        self.send(f"ORDER\n{text}")

    def error(self, text: str) -> None:
        self.send(f"ERROR\n{text}")

    def _poll(self) -> None:
        while not self._stop_event.is_set():
            try:
                response = self.session.get(
                    f"{self.api_url}/getUpdates",
                    params={"timeout": 20, "offset": self._offset},
                    timeout=25,
                )
                response.raise_for_status()
                for update in response.json().get("result", []):
                    self._offset = max(self._offset, int(update["update_id"]) + 1)
                    self._handle_update(update)
            except requests.RequestException:
                LOGGER.exception("Telegram polling failed")
                self._stop_event.wait(5)
            except Exception:
                LOGGER.exception("Unexpected Telegram update error")

    def _handle_update(self, update: dict[str, object]) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return
        chat = message.get("chat")
        if not isinstance(chat, dict) or str(chat.get("id")) != self.settings.telegram_chat_id:
            LOGGER.warning("Ignored Telegram command from an unauthorized chat")
            return
        text = str(message.get("text", "")).strip().split("@", 1)[0].lower()
        if text == "/status":
            self.send(self.status_callback())
        elif text == "/positions":
            self.send(self.positions_callback())
        elif text == "/stop":
            self.stop_callback()
            self.send("Emergency kill switch activated. New orders are blocked.")
