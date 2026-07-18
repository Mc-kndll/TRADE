import pandas as pd

from tradebot.strategy import evaluate_signal


def _signal_frame() -> pd.DataFrame:
    rows = 60
    return pd.DataFrame(
        {
            "close": [105.0] * rows,
            "ema9": [104.0] * rows,
            "ema20": [103.0] * rows,
            "ema50": [102.0] * rows,
            "rsi": [55.0] * rows,
            "macd": [2.0] * rows,
            "macd_signal": [1.0] * rows,
            "atr": [2.5] * rows,
            "vwap": [101.0] * rows,
            "volume": [1_200.0] * rows,
            "volume_sma20": [1_000.0] * rows,
        }
    )


def test_evaluate_signal_returns_long_buy_when_score_passes_threshold() -> None:
    signal = evaluate_signal("AAPL", _signal_frame(), min_score=80)

    assert signal.action == "BUY"
    assert signal.score == 95
    assert signal.price == 105.0
    assert "bullish_ema_stack" in signal.reasons
    assert "volume_confirmation" in signal.reasons


def test_evaluate_signal_waits_for_enough_bars() -> None:
    signal = evaluate_signal("AAPL", _signal_frame().iloc[:20])

    assert signal.action == "WAIT"
    assert signal.reasons == ("insufficient_data",)


def test_strategy_never_emits_short_action() -> None:
    frame = _signal_frame()
    frame.loc[:, ["ema9", "ema20", "ema50"]] = [100.0, 102.0, 104.0]

    assert evaluate_signal("AAPL", frame).action == "WAIT"
