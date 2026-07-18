import pytest

from tradebot.risk import build_trade_plan, daily_loss_limit_hit


def test_risk_sizing_uses_tighter_position_value_cap() -> None:
    plan = build_trade_plan(
        net_liquidation=100_000,
        entry=100,
        atr=2,
        risk_per_trade=0.01,
        max_position_value_pct=0.10,
        atr_stop_multiplier=2,
        reward_risk_ratio=2,
    )

    assert plan is not None
    assert plan.quantity == 100
    assert plan.stop == 96
    assert plan.target == 108
    assert plan.risk_dollars == 400


@pytest.mark.parametrize("entry,atr", [(0, 2), (100, 0), (-10, 2)])
def test_risk_sizing_rejects_invalid_market_values(entry: float, atr: float) -> None:
    assert build_trade_plan(
        net_liquidation=100_000,
        entry=entry,
        atr=atr,
        risk_per_trade=0.01,
        max_position_value_pct=0.20,
        atr_stop_multiplier=1.5,
        reward_risk_ratio=2,
    ) is None


def test_daily_loss_limit() -> None:
    assert not daily_loss_limit_hit(100_000, 98_001, 0.02)
    assert daily_loss_limit_hit(100_000, 98_000, 0.02)
    assert daily_loss_limit_hit(0, 98_000, 0.02)
