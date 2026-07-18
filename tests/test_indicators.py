import numpy as np
import pandas as pd
import pytest

from tradebot.indicators import add_indicators


def test_add_indicators_produces_expected_columns_and_values() -> None:
    rows = 80
    close = np.linspace(100, 140, rows)
    frame = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.linspace(1_000, 2_000, rows),
        }
    )

    result = add_indicators(frame)

    expected = {
        "ema9", "ema20", "ema50", "rsi", "macd", "macd_signal",
        "macd_hist", "atr", "vwap", "volume_sma20",
    }
    assert expected.issubset(result.columns)
    assert result.iloc[-1]["ema9"] > result.iloc[-1]["ema20"]
    assert result.iloc[-1]["atr"] == pytest.approx(2.0)
    assert result.iloc[-1]["vwap"] < result.iloc[-1]["close"]


def test_add_indicators_rejects_missing_ohlcv_column() -> None:
    with pytest.raises(ValueError, match="volume"):
        add_indicators(pd.DataFrame({"open": [], "high": [], "low": [], "close": []}))
