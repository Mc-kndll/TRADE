from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradePlan:
    quantity: int
    entry: float
    stop: float
    target: float
    risk_dollars: float


def build_trade_plan(
    *,
    net_liquidation: float,
    entry: float,
    atr: float,
    risk_per_trade: float,
    max_position_value_pct: float,
    atr_stop_multiplier: float,
    reward_risk_ratio: float,
) -> TradePlan | None:
    if net_liquidation <= 0 or entry <= 0 or atr <= 0:
        return None

    stop_distance = atr * atr_stop_multiplier
    stop = round(entry - stop_distance, 2)
    if stop <= 0 or stop >= entry:
        return None

    risk_budget = net_liquidation * risk_per_trade
    qty_by_risk = int(risk_budget // (entry - stop))
    max_position_value = net_liquidation * max_position_value_pct
    qty_by_value = int(max_position_value // entry)
    quantity = min(qty_by_risk, qty_by_value)
    if quantity < 1:
        return None

    actual_risk = round(quantity * (entry - stop), 2)
    target = round(entry + (entry - stop) * reward_risk_ratio, 2)
    return TradePlan(quantity, round(entry, 2), stop, target, actual_risk)


def daily_loss_limit_hit(
    starting_equity: float, current_equity: float, max_loss_pct: float
) -> bool:
    if starting_equity <= 0:
        return True
    return current_equity <= starting_equity * (1 - max_loss_pct)
