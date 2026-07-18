from dataclasses import replace

from ib_insync import Stock

from tradebot.config import Settings
from tradebot.orders import OrderManager
from tradebot.risk import TradePlan


class _Client:
    def __init__(self) -> None:
        self.order_id = 10

    def getReqId(self) -> int:
        self.order_id += 1
        return self.order_id


class _IB:
    def __init__(self) -> None:
        self.client = _Client()


class _Broker:
    def __init__(self) -> None:
        self.ib = _IB()
        self.account = "DU123456"

    def has_symbol_exposure(self, symbol: str) -> bool:
        return False


def test_bracket_transmit_flags_and_parent_links() -> None:
    manager = OrderManager(_Broker(), Settings())  # type: ignore[arg-type]
    contract = Stock("AAPL", "SMART", "USD")
    plan = TradePlan(quantity=10, entry=100, stop=97, target=106, risk_dollars=30)

    parent, target, stop = manager.build_bracket(contract, plan, "TEST-ORDER")

    assert [parent.transmit, target.transmit, stop.transmit] == [False, False, True]
    assert parent.orderType == "MKT"
    assert target.parentId == parent.orderId
    assert stop.parentId == parent.orderId
    assert all(not order.outsideRth for order in (parent, target, stop))
    assert all(order.account == "DU123456" for order in (parent, target, stop))


def test_limit_parent_is_supported() -> None:
    config = replace(Settings(), entry_order_type="LMT", entry_limit_offset_pct=0.001)
    manager = OrderManager(_Broker(), config)  # type: ignore[arg-type]
    plan = TradePlan(quantity=10, entry=100, stop=97, target=106, risk_dollars=30)

    parent, _, _ = manager.build_bracket(Stock("AAPL", "SMART", "USD"), plan, "TEST")

    assert parent.orderType == "LMT"
    assert parent.lmtPrice == 100.10
