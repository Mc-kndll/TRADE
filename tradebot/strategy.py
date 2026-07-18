from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: str
    score: int
    price: float
    atr: float
    reasons: tuple[str, ...]


def evaluate_signal(symbol: str, frame: pd.DataFrame, min_score: int = 80) -> Signal:
    if len(frame) < 55:
        return Signal(symbol, "WAIT", 0, 0.0, 0.0, ("insufficient_data",))

    last = frame.iloc[-1]
    previous = frame.iloc[-2]
    required = [
        "close",
        "ema9",
        "ema20",
        "ema50",
        "rsi",
        "macd",
        "macd_signal",
        "atr",
        "vwap",
        "volume",
        "volume_sma20",
    ]
    if any(pd.isna(last[column]) for column in required):
        return Signal(
            symbol,
            "WAIT",
            0,
            float(last.get("close", 0) or 0),
            0.0,
            ("indicators_not_ready",),
        )

    score = 0
    reasons: list[str] = []

    if last["ema9"] > last["ema20"] > last["ema50"]:
        score += 25
        reasons.append("bullish_ema_stack")
    elif last["ema9"] > last["ema20"]:
        score += 15
        reasons.append("short_term_uptrend")

    if 45 <= last["rsi"] <= 65:
        score += 20
        reasons.append("healthy_rsi")
    elif 35 <= last["rsi"] < 45 and last["rsi"] > previous["rsi"]:
        score += 10
        reasons.append("rsi_recovery")

    if last["macd"] > last["macd_signal"]:
        score += 20
        reasons.append("macd_bullish")
        if previous["macd"] <= previous["macd_signal"]:
            score += 5
            reasons.append("macd_cross_up")

    if last["close"] > last["vwap"]:
        score += 15
        reasons.append("above_vwap")

    if last["volume"] >= last["volume_sma20"] * 1.10:
        score += 15
        reasons.append("volume_confirmation")

    action = "BUY" if score >= min_score else "WAIT"
    return Signal(
        symbol=symbol,
        action=action,
        score=min(score, 100),
        price=round(float(last["close"]), 2),
        atr=round(float(last["atr"]), 4),
        reasons=tuple(reasons),
    )
