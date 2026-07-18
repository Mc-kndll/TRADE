"""IBKR TWS connection and account access."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from ib_insync import IB, Position, Trade

from .config import Settings

LOGGER = logging.getLogger(__name__)


class BrokerError(RuntimeError):
    """Raised when a safe IBKR operation cannot be completed."""


@dataclass(frozen=True)
class AccountSnapshot:
    account: str
    net_liquidation: float
    available_funds: float
    buying_power: float
    realized_pnl: float
    unrealized_pnl: float


class IBKRBroker:
    """Owns the ib-insync connection and enforces paper-account selection."""

    def __init__(self, settings: Settings, ib: IB | None = None) -> None:
        self.settings = settings
        self.ib = ib or IB()
        self.account = ""
        self.ib.disconnectedEvent += self._on_disconnected

    @property
    def connected(self) -> bool:
        return self.ib.isConnected()

    def _on_disconnected(self) -> None:
        LOGGER.warning("TWS connection lost; the engine will reconnect")

    def connect(self, *, max_attempts: int | None = None) -> None:
        """Connect with retry. None retries until successful."""
        attempt = 0
        while not self.connected:
            attempt += 1
            try:
                LOGGER.info(
                    "Connecting to TWS at %s:%s (client %s)",
                    self.settings.ib_host,
                    self.settings.ib_port,
                    self.settings.ib_client_id,
                )
                self.ib.connect(
                    self.settings.ib_host,
                    self.settings.ib_port,
                    clientId=self.settings.ib_client_id,
                    timeout=self.settings.connect_timeout_seconds,
                    readonly=False,
                    account=self.settings.ib_account or "",
                )
                self.account = self._select_safe_account(self.ib.managedAccounts())
                self.ib.reqMarketDataType(self.settings.market_data_type)
                LOGGER.info("Connected to IBKR account %s", self._masked_account())
                return
            except Exception as exc:
                self.ib.disconnect()
                if max_attempts is not None and attempt >= max_attempts:
                    raise BrokerError(f"Unable to connect to TWS after {attempt} attempts") from exc
                LOGGER.exception(
                    "TWS connection attempt %s failed; retrying in %ss",
                    attempt,
                    self.settings.reconnect_interval_seconds,
                )
                time.sleep(self.settings.reconnect_interval_seconds)

    def ensure_connected(self) -> None:
        if not self.connected:
            self.connect()

    def disconnect(self) -> None:
        if self.connected:
            self.ib.disconnect()

    def _select_safe_account(self, accounts: list[str]) -> str:
        if not accounts:
            raise BrokerError("TWS returned no managed accounts")
        requested = self.settings.ib_account
        if requested and requested not in accounts:
            raise BrokerError("Configured IB_ACCOUNT is not managed by this TWS session")
        candidates = [requested] if requested else accounts
        if self.settings.paper_account_only:
            paper_accounts = [account for account in candidates if account.upper().startswith("DU")]
            if not paper_accounts:
                raise BrokerError(
                    "PAPER_ACCOUNT_ONLY=true refused the available live/non-paper account(s)"
                )
            return paper_accounts[0]
        return candidates[0]

    def _masked_account(self) -> str:
        return f"***{self.account[-4:]}" if self.account else "unknown"

    def account_snapshot(self) -> AccountSnapshot:
        self.ensure_connected()
        values = {
            value.tag: value.value
            for value in self.ib.accountSummary(self.account)
            if value.currency in {"USD", "BASE", ""}
        }

        def number(tag: str) -> float:
            try:
                return float(values.get(tag, 0.0))
            except (TypeError, ValueError):
                return 0.0

        return AccountSnapshot(
            account=self.account,
            net_liquidation=number("NetLiquidation"),
            available_funds=number("AvailableFunds"),
            buying_power=number("BuyingPower"),
            realized_pnl=number("RealizedPnL"),
            unrealized_pnl=number("UnrealizedPnL"),
        )

    def positions(self) -> list[Position]:
        self.ensure_connected()
        return [position for position in self.ib.positions(self.account) if position.position != 0]

    def open_trades(self) -> list[Trade]:
        self.ensure_connected()
        return [
            trade for trade in self.ib.openTrades() if trade.order.account in {"", self.account}
        ]

    def has_symbol_exposure(self, symbol: str) -> bool:
        wanted = symbol.upper()
        if any(position.contract.symbol.upper() == wanted for position in self.positions()):
            return True
        return any(trade.contract.symbol.upper() == wanted for trade in self.open_trades())

    def contract_is_trading_now(self, contract: Any, now: datetime | None = None) -> bool:
        """Use IBKR liquid hours as the final RTH/holiday order gate."""
        details = self.ib.reqContractDetails(contract)
        if not details:
            LOGGER.error("No contract details; conservatively blocking order")
            return False
        detail = details[0]
        try:
            timezone = ZoneInfo(detail.timeZoneId or "America/New_York")
        except Exception:
            timezone = ZoneInfo("America/New_York")
        current = (now or datetime.now(timezone)).astimezone(timezone)
        for session in (detail.liquidHours or "").split(";"):
            if not session or "CLOSED" in session:
                continue
            try:
                start_text, end_text = session.split("-", 1)
                start = datetime.strptime(start_text, "%Y%m%d:%H%M").replace(tzinfo=timezone)
                end = datetime.strptime(end_text, "%Y%m%d:%H%M").replace(tzinfo=timezone)
            except ValueError:
                LOGGER.warning("Could not parse IBKR liquid-hours segment: %s", session)
                continue
            if start <= current <= end:
                return True
        return False

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "account": self._masked_account(),
            "paper_only": self.settings.paper_account_only,
        }
