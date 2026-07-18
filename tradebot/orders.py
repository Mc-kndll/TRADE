"""Safe IBKR bracket-order construction and submission."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from ib_insync import Contract, LimitOrder, MarketOrder, Order, StopOrder, Trade

from .broker import BrokerError, IBKRBroker
from .config import Settings
from .risk import TradePlan

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderSubmission:
    symbol: str
    status: str
    order_ref: str
    trades: tuple[Trade, ...] = ()


class OrderManager:
    """Builds parent/target/stop orders and blocks duplicate symbols."""

    def __init__(self, broker: IBKRBroker, settings: Settings) -> None:
        self.broker = broker
        self.settings = settings
        self._reserved_symbols: set[str] = set()
        self._lock = threading.Lock()

    def _reserve(self, symbol: str) -> None:
        symbol = symbol.upper()
        with self._lock:
            if symbol in self._reserved_symbols or self.broker.has_symbol_exposure(symbol):
                raise BrokerError(f"Duplicate position/order blocked for {symbol}")
            self._reserved_symbols.add(symbol)

    def _release(self, symbol: str) -> None:
        with self._lock:
            self._reserved_symbols.discard(symbol.upper())

    def build_bracket(
        self, contract: Contract, plan: TradePlan, order_ref: str
    ) -> tuple[Order, Order, Order]:
        parent_id = self.broker.ib.client.getReqId()
        common = {
            "account": self.broker.account,
            "tif": "DAY",
            "outsideRth": False,
            "orderRef": order_ref,
        }
        if self.settings.entry_order_type == "LMT":
            limit_price = round(plan.entry * (1 + self.settings.entry_limit_offset_pct), 2)
            parent: Order = LimitOrder("BUY", plan.quantity, limit_price, **common)
        else:
            parent = MarketOrder("BUY", plan.quantity, **common)
        parent.orderId = parent_id
        parent.transmit = False

        take_profit = LimitOrder("SELL", plan.quantity, plan.target, **common)
        take_profit.orderId = self.broker.ib.client.getReqId()
        take_profit.parentId = parent_id
        take_profit.transmit = False

        stop_loss = StopOrder("SELL", plan.quantity, plan.stop, **common)
        stop_loss.orderId = self.broker.ib.client.getReqId()
        stop_loss.parentId = parent_id
        stop_loss.transmit = True
        return parent, take_profit, stop_loss

    def submit_bracket(
        self, contract: Contract, plan: TradePlan, *, order_ref: str
    ) -> OrderSubmission:
        symbol = contract.symbol.upper()
        self._reserve(symbol)
        try:
            orders = self.build_bracket(contract, plan, order_ref)
            if self.settings.dry_run:
                LOGGER.warning("DRY_RUN: bracket for %s was not transmitted", symbol)
                return OrderSubmission(symbol, "DRY_RUN", order_ref)
            if not self.settings.auto_trading_enabled:
                LOGGER.warning("AUTO_TRADING_ENABLED=false: order for %s blocked", symbol)
                return OrderSubmission(symbol, "DISABLED", order_ref)
            trades = tuple(self.broker.ib.placeOrder(contract, order) for order in orders)
            LOGGER.info("Submitted paper bracket %s for %s", order_ref, symbol)
            return OrderSubmission(symbol, "SUBMITTED", order_ref, trades)
        except Exception:
            self._release(symbol)
            raise
        finally:
            if self.settings.dry_run or not self.settings.auto_trading_enabled:
                self._release(symbol)
