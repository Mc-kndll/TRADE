"""Watchlist scanner that turns bars into scored long signals."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ib_insync import Contract

from .config import Settings
from .indicators import add_indicators
from .market_data import MarketDataService
from .strategy import Signal, evaluate_signal

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanResult:
    contract: Contract
    signal: Signal


class WatchlistScanner:
    def __init__(self, market_data: MarketDataService, settings: Settings) -> None:
        self.market_data = market_data
        self.settings = settings

    def scan(self) -> list[ScanResult]:
        results: list[ScanResult] = []
        for symbol in self.settings.watchlist:
            try:
                contract, frame = self.market_data.historical_bars(symbol)
                enriched = add_indicators(frame)
                signal = evaluate_signal(symbol, enriched, self.settings.min_signal_score)
                results.append(ScanResult(contract, signal))
            except Exception:
                LOGGER.exception("Failed to scan %s", symbol)
        return results
