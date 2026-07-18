"""Historical market-data retrieval through IBKR."""

from __future__ import annotations

import logging

import pandas as pd
from ib_insync import Contract, Stock, util

from .broker import BrokerError, IBKRBroker
from .config import Settings

LOGGER = logging.getLogger(__name__)


class MarketDataService:
    def __init__(self, broker: IBKRBroker, settings: Settings) -> None:
        self.broker = broker
        self.settings = settings

    def stock(self, symbol: str) -> Contract:
        contract = Stock(symbol.upper(), self.settings.exchange, self.settings.currency)
        qualified = self.broker.ib.qualifyContracts(contract)
        if not qualified:
            raise BrokerError(f"IBKR could not qualify {symbol}")
        return qualified[0]

    def historical_bars(self, symbol: str) -> tuple[Contract, pd.DataFrame]:
        self.broker.ensure_connected()
        contract = self.stock(symbol)
        bars = self.broker.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=self.settings.history_duration,
            barSizeSetting=self.settings.bar_size,
            whatToShow="TRADES",
            useRTH=self.settings.use_rth,
            formatDate=1,
            keepUpToDate=False,
            timeout=30,
        )
        frame = util.df(bars)
        if frame is None or frame.empty:
            raise BrokerError(f"No historical data returned for {symbol}")
        expected = ["date", "open", "high", "low", "close", "volume"]
        missing = [column for column in expected if column not in frame.columns]
        if missing:
            raise BrokerError(f"Historical data for {symbol} is missing {missing}")
        LOGGER.debug("Loaded %s bars for %s", len(frame), symbol)
        return contract, frame
