"""Trading-engine orchestration with conservative safety gates."""

from __future__ import annotations

import json
import logging
import math
import threading
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from ib_insync import Fill, Trade

from .broker import IBKRBroker
from .config import Settings
from .database import Database
from .market_data import MarketDataService
from .orders import OrderManager
from .risk import build_trade_plan, daily_loss_limit_hit
from .scanner import WatchlistScanner
from .telegram import TelegramService

LOGGER = logging.getLogger(__name__)
EASTERN = ZoneInfo("America/New_York")


def is_regular_trading_hours(now: datetime | None = None) -> bool:
    current = (now or datetime.now(EASTERN)).astimezone(EASTERN)
    return current.weekday() < 5 and time(9, 30) <= current.time() <= time(16, 0)


def parse_clock(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":"))
    return time(hour, minute)


def entry_window_open(now: datetime, settings: Settings) -> bool:
    current = now.astimezone(EASTERN).time()
    return parse_clock(settings.order_start_time) <= current <= parse_clock(
        settings.last_entry_time
    )


def next_scan_time(
    now: datetime, *, start: str, end: str, interval_seconds: int
) -> datetime:
    """Return the next weekday scan aligned to the configured start time."""
    current = now.astimezone(EASTERN)
    start_clock = parse_clock(start)
    end_clock = parse_clock(end)
    day = current.date()
    while True:
        if day.weekday() >= 5:
            day += timedelta(days=1)
            continue
        first = datetime.combine(day, start_clock, tzinfo=EASTERN)
        last = datetime.combine(day, end_clock, tzinfo=EASTERN)
        if current <= first:
            return first
        if current <= last and current.date() == day:
            elapsed = (current - first).total_seconds()
            slots = math.ceil(elapsed / interval_seconds)
            candidate = first + timedelta(seconds=slots * interval_seconds)
            if candidate >= current and candidate <= last:
                return candidate
        day += timedelta(days=1)


class TradingEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_path)
        self.broker = IBKRBroker(settings)
        self.market_data = MarketDataService(self.broker, settings)
        self.scanner = WatchlistScanner(self.market_data, settings)
        self.orders = OrderManager(self.broker, settings)
        self.kill_switch = threading.Event()
        self.telegram = TelegramService(
            settings,
            status_callback=self.status_text,
            positions_callback=self.positions_text,
            stop_callback=self.activate_kill_switch,
        )
        self.broker.ib.execDetailsEvent += self._on_fill

    def activate_kill_switch(self) -> None:
        self.kill_switch.set()
        LOGGER.critical("Emergency kill switch activated")

    def start(self, *, once: bool = False) -> None:
        self.settings.validate()
        self.broker.connect(max_attempts=1 if once else None)
        self.telegram.start()
        LOGGER.info(
            "Engine started: dry_run=%s auto_trading=%s paper_only=%s",
            self.settings.dry_run,
            self.settings.auto_trading_enabled,
            self.settings.paper_account_only,
        )
        try:
            if once:
                self.run_cycle()
                return
            while not self.kill_switch.is_set():
                scheduled = next_scan_time(
                    datetime.now(EASTERN),
                    start=self.settings.scan_start_time,
                    end=self.settings.scan_end_time,
                    interval_seconds=self.settings.scan_interval_seconds,
                )
                wait_seconds = max(
                    0.0, (scheduled - datetime.now(EASTERN)).total_seconds()
                )
                LOGGER.info("Next scan scheduled for %s", scheduled.isoformat())
                if self.kill_switch.wait(wait_seconds):
                    break
                try:
                    self.run_cycle()
                except Exception as exc:
                    self._record_error("engine", exc)
        finally:
            self.telegram.stop()
            self.broker.disconnect()

    def run_cycle(self, now: datetime | None = None) -> None:
        cycle_time = (now or datetime.now(EASTERN)).astimezone(EASTERN)
        if self.kill_switch.is_set():
            LOGGER.warning("Kill switch is active; scan cycle skipped")
            return
        self.broker.ensure_connected()
        snapshot = self.broker.account_snapshot()
        self.database.record_snapshot(snapshot)
        starting_equity = self.database.starting_equity_today() or snapshot.net_liquidation
        if daily_loss_limit_hit(
            starting_equity, snapshot.net_liquidation, self.settings.max_daily_loss_pct
        ):
            self.activate_kill_switch()
            self.telegram.error("Daily loss limit reached; kill switch activated.")
            return
        if not is_regular_trading_hours(cycle_time):
            LOGGER.info("Outside regular US trading hours; no orders will be evaluated")
            self._send_scan_report(
                cycle_time,
                snapshot.net_liquidation,
                0,
                [],
                "market closed; no scan",
            )
            return

        open_symbols = {
            position.contract.symbol.upper() for position in self.broker.positions()
        }
        for trade in self.broker.open_trades():
            open_symbols.add(trade.contract.symbol.upper())
        open_position_count = len(open_symbols)
        results = self.scanner.scan()
        buy_signals = [result.signal for result in results if result.signal.action == "BUY"]
        orders_allowed = entry_window_open(cycle_time, self.settings)

        for result in results:
            signal = result.signal
            self.database.record_signal(signal)
            if signal.action != "BUY":
                continue
            self.telegram.signal(
                f"{signal.symbol} score={signal.score} price={signal.price} "
                f"reasons={','.join(signal.reasons)}"
            )
            if not orders_allowed:
                LOGGER.info(
                    "Observation/report window: new order for %s blocked until %s",
                    signal.symbol,
                    self.settings.order_start_time,
                )
                continue
            if self.kill_switch.is_set():
                break
            if signal.symbol in open_symbols:
                LOGGER.info("Duplicate symbol %s skipped", signal.symbol)
                continue
            if open_position_count >= self.settings.max_open_positions:
                LOGGER.warning("Maximum open positions reached")
                break
            if not self.broker.contract_is_trading_now(result.contract):
                LOGGER.warning("IBKR RTH/holiday gate blocked %s", signal.symbol)
                continue
            plan = build_trade_plan(
                net_liquidation=snapshot.net_liquidation,
                entry=signal.price,
                atr=signal.atr,
                risk_per_trade=self.settings.risk_per_trade,
                max_position_value_pct=self.settings.max_position_value_pct,
                atr_stop_multiplier=self.settings.atr_stop_multiplier,
                reward_risk_ratio=self.settings.reward_risk_ratio,
            )
            if plan is None:
                LOGGER.warning("Risk sizing rejected %s", signal.symbol)
                continue
            order_ref = f"TRADE-{signal.symbol}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            try:
                submission = self.orders.submit_bracket(
                    result.contract, plan, order_ref=order_ref
                )
                order_ids = [trade.order.orderId for trade in submission.trades]
                self.database.record_order(
                    symbol=signal.symbol,
                    order_ref=order_ref,
                    status=submission.status,
                    quantity=plan.quantity,
                    entry=plan.entry,
                    stop=plan.stop,
                    target=plan.target,
                    broker_order_ids=order_ids,
                )
                self.telegram.order(
                    f"{signal.symbol} {submission.status}: qty={plan.quantity} "
                    f"entry={plan.entry} stop={plan.stop} target={plan.target}"
                )
                if submission.status == "SUBMITTED":
                    open_symbols.add(signal.symbol)
                    open_position_count += 1
            except Exception as exc:
                self._record_error("orders", exc)
        mode = (
            "orders allowed by schedule"
            if orders_allowed
            else f"observation only; entries {self.settings.order_start_time}-"
            f"{self.settings.last_entry_time} ET"
        )
        self._send_scan_report(
            cycle_time,
            snapshot.net_liquidation,
            open_position_count,
            buy_signals,
            mode,
        )

    def _send_scan_report(
        self,
        cycle_time: datetime,
        net_liquidation: float,
        open_positions: int,
        buy_signals: list[object],
        note: str,
    ) -> None:
        if not self.settings.send_scan_reports:
            return
        symbols = ", ".join(
            f"{getattr(signal, 'symbol', '?')}({getattr(signal, 'score', 0)})"
            for signal in buy_signals
        ) or "none"
        safety = (
            "DRY_RUN"
            if self.settings.dry_run
            else "AUTO" if self.settings.auto_trading_enabled else "ORDERS_DISABLED"
        )
        self.telegram.report(
            f"{cycle_time:%Y-%m-%d %H:%M} ET\n"
            f"Net liquidation: {net_liquidation:,.2f}\n"
            f"Open symbols: {open_positions}\n"
            f"BUY signals: {symbols}\n"
            f"Mode: {safety}\n{note}"
        )

    def status_text(self) -> str:
        payload = {
            **self.broker.status(),
            "dry_run": self.settings.dry_run,
            "auto_trading": self.settings.auto_trading_enabled,
            "kill_switch": self.kill_switch.is_set(),
            "database": self.database.status_summary(),
        }
        return json.dumps(payload, default=str, indent=2)

    def positions_text(self) -> str:
        try:
            positions = self.broker.positions()
        except Exception as exc:
            return f"Unable to read positions: {exc}"
        if not positions:
            return "No open positions."
        return "\n".join(
            f"{position.contract.symbol}: {position.position:g} @ {position.avgCost:.2f}"
            for position in positions
        )

    def _record_error(self, component: str, exc: Exception) -> None:
        LOGGER.exception("%s failure", component)
        self.database.record_error(component, str(exc), repr(exc))
        self.telegram.error(f"{component}: {exc}")

    def _on_fill(self, trade: Trade, fill: Fill) -> None:
        try:
            self.database.record_fill(
                symbol=trade.contract.symbol,
                order_id=trade.order.orderId,
                execution_id=fill.execution.execId,
                side=fill.execution.side,
                shares=fill.execution.shares,
                price=fill.execution.price,
                commission=getattr(fill.commissionReport, "commission", 0.0),
            )
        except Exception:
            LOGGER.exception("Could not persist fill")
