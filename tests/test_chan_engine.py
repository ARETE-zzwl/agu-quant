from __future__ import annotations

import pandas as pd

from tradingagents.chan import analyze_chan, run_chan_backtest


def _df(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="B")
    close = pd.Series(closes, index=dates)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close.shift(1).fillna(close.iloc[0]).values,
            "High": (close + 0.8).values,
            "Low": (close - 0.8).values,
            "Close": close.values,
            "Volume": [1_000_000 + i * 1000 for i in range(len(closes))],
        }
    )


def test_chan_analysis_detects_fractals_strokes_and_zones():
    prices = [10, 12, 11, 14, 12, 15, 13, 16, 14, 17, 15, 18, 16, 19, 17, 20, 18, 21, 19]

    result = analyze_chan(_df(prices), min_stroke_bars=1)

    assert len(result["fractals"]) >= 6
    assert len(result["strokes"]) >= 3
    assert "action" in result
    assert "summary" in result


def test_chan_backtest_returns_metrics_without_lookahead_crash():
    trend = [10 + i * 0.05 for i in range(80)]
    swings = [14, 12, 15, 13, 16, 14, 17, 15, 18, 16, 19, 17, 20, 18, 21, 19]
    prices = trend + swings + [19 + i * 0.08 for i in range(50)]

    result = run_chan_backtest(_df(prices), strategy="combined", min_stroke_bars=3)

    assert result["total_trades"] >= 0
    assert "total_return" in result
    assert result["equity_curve"] is not None
