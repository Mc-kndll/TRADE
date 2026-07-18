"""SQLite persistence for bot events and audit data."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .strategy import Signal

if TYPE_CHECKING:
    from .broker import AccountSnapshot


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, symbol TEXT NOT NULL,
            action TEXT NOT NULL, score INTEGER NOT NULL, price REAL NOT NULL,
            atr REAL NOT NULL, reasons TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, symbol TEXT NOT NULL,
            order_ref TEXT NOT NULL, status TEXT NOT NULL, quantity INTEGER NOT NULL,
            entry REAL NOT NULL, stop REAL NOT NULL, target REAL NOT NULL,
            broker_order_ids TEXT NOT NULL DEFAULT '[]'
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_ref ON orders(order_ref);
        CREATE TABLE IF NOT EXISTS fills (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, symbol TEXT NOT NULL,
            order_id INTEGER, execution_id TEXT, side TEXT, shares REAL, price REAL,
            commission REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, component TEXT NOT NULL,
            message TEXT NOT NULL, details TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS account_snapshots (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, account TEXT NOT NULL,
            net_liquidation REAL NOT NULL, available_funds REAL NOT NULL,
            buying_power REAL NOT NULL, realized_pnl REAL NOT NULL,
            unrealized_pnl REAL NOT NULL
        );
        """
        with self.connection() as connection:
            connection.executescript(schema)

    def record_signal(self, signal: Signal) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO signals VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _now(), signal.symbol, signal.action, signal.score, signal.price,
                    signal.atr, json.dumps(signal.reasons),
                ),
            )

    def record_order(
        self,
        *,
        symbol: str,
        order_ref: str,
        status: str,
        quantity: int,
        entry: float,
        stop: float,
        target: float,
        broker_order_ids: list[int] | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO orders
                (created_at, symbol, order_ref, status, quantity, entry, stop, target,
                 broker_order_ids) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    _now(), symbol, order_ref, status, quantity, entry, stop, target,
                    json.dumps(broker_order_ids or []),
                ),
            )

    def record_fill(self, **fill: Any) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO fills
                (created_at, symbol, order_id, execution_id, side, shares, price, commission)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    _now(), fill["symbol"], fill.get("order_id"), fill.get("execution_id"),
                    fill.get("side"), fill.get("shares"), fill.get("price"),
                    fill.get("commission", 0),
                ),
            )

    def record_error(self, component: str, message: str, details: str = "") -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO errors VALUES (NULL, ?, ?, ?, ?)",
                (_now(), component, message, details),
            )

    def record_snapshot(self, snapshot: AccountSnapshot) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO account_snapshots VALUES
                (NULL, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    _now(), snapshot.account, snapshot.net_liquidation,
                    snapshot.available_funds, snapshot.buying_power,
                    snapshot.realized_pnl, snapshot.unrealized_pnl,
                ),
            )

    def starting_equity_today(self) -> float | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT net_liquidation FROM account_snapshots
                WHERE date(created_at) = date('now') ORDER BY id ASC LIMIT 1"""
            ).fetchone()
        return float(row[0]) if row else None

    def status_summary(self) -> dict[str, Any]:
        with self.connection() as connection:
            snapshot = connection.execute(
                "SELECT * FROM account_snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
            last_order = connection.execute(
                "SELECT * FROM orders ORDER BY id DESC LIMIT 1"
            ).fetchone()
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("signals", "orders", "fills", "errors")
            }
        return {
            "last_snapshot": dict(snapshot) if snapshot else None,
            "last_order": dict(last_order) if last_order else None,
            "counts": counts,
        }
