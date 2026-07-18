from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from tradebot.config import Settings
from tradebot.engine import entry_window_open, next_scan_time

EASTERN = ZoneInfo("America/New_York")


def _at(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 7, 20, hour, minute, second, tzinfo=EASTERN)


def test_first_scan_is_0935_then_every_ten_minutes() -> None:
    assert next_scan_time(
        _at(9, 25), start="09:35", end="15:55", interval_seconds=600
    ) == _at(9, 35)
    assert next_scan_time(
        _at(9, 35, 1), start="09:35", end="15:55", interval_seconds=600
    ) == _at(9, 45)
    assert next_scan_time(
        _at(9, 46), start="09:35", end="15:55", interval_seconds=600
    ) == _at(9, 55)


def test_weekend_schedules_monday_morning() -> None:
    saturday = datetime(2026, 7, 18, 10, 0, tzinfo=EASTERN)

    assert next_scan_time(
        saturday, start="09:35", end="15:55", interval_seconds=600
    ) == _at(9, 35)


def test_entries_wait_until_0945_and_stop_after_1500() -> None:
    config = replace(
        Settings(), order_start_time="09:45", last_entry_time="15:00"
    )

    assert not entry_window_open(_at(9, 35), config)
    assert entry_window_open(_at(9, 45), config)
    assert entry_window_open(_at(15, 0), config)
    assert not entry_window_open(_at(15, 5), config)
