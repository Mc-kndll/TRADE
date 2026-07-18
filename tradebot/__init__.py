"""Safe, modular IBKR TWS paper-trading bot."""

import asyncio


def _ensure_legacy_event_loop() -> None:
    """Provide the loop expected by ib-insync/eventkit on Python 3.14+."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


_ensure_legacy_event_loop()

__version__ = "0.2.0"
