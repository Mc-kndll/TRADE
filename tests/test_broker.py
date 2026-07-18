from types import SimpleNamespace

import pytest

from tradebot.broker import BrokerError, IBKRBroker
from tradebot.config import Settings


class _Event:
    def __iadd__(self, callback: object) -> "_Event":
        return self


class _IB:
    def __init__(self) -> None:
        self.disconnectedEvent = _Event()

    def isConnected(self) -> bool:
        return True

    def accountSummary(self, account: str) -> list[SimpleNamespace]:
        assert account == "DUR123456"
        return [
            SimpleNamespace(tag="NetLiquidation", value="1002032.15", currency="CAD"),
            SimpleNamespace(tag="AvailableFunds", value="1001577.12", currency="CAD"),
            SimpleNamespace(tag="BuyingPower", value="3338590.40", currency="CAD"),
        ]


def test_account_snapshot_accepts_non_usd_base_currency() -> None:
    broker = IBKRBroker(Settings(), ib=_IB())  # type: ignore[arg-type]
    broker.account = "DUR123456"

    snapshot = broker.account_snapshot()

    assert snapshot.net_liquidation == pytest.approx(1_002_032.15)
    assert snapshot.available_funds == pytest.approx(1_001_577.12)
    assert snapshot.buying_power == pytest.approx(3_338_590.40)


def test_paper_only_mode_rejects_live_account() -> None:
    broker = IBKRBroker(Settings(), ib=_IB())  # type: ignore[arg-type]

    with pytest.raises(BrokerError, match="refused"):
        broker._select_safe_account(["U1234567"])
