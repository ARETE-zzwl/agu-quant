from __future__ import annotations

import numpy as np
import pandas as pd

from tradingagents.factors import analysis


class _ScoreFactor:
    direction = 1

    def compute_series(self, frame: pd.DataFrame) -> pd.Series:
        return frame["Score"]


def test_compute_ic_uses_requested_forward_trading_days(monkeypatch):
    dates = pd.date_range("2026-01-05", periods=6, freq="B")
    data = {}
    for index, code in enumerate(["A", "B", "C", "D"], start=1):
        close = [100, 105 - index * 2, 100, 100 * (1 + index * 0.01), 100, 100]
        data[code] = pd.DataFrame(
            {"Close": close, "Score": [index] * len(dates)},
            index=dates,
        )

    monkeypatch.setattr(analysis, "load_stock_data", lambda codes, end_date: data)
    monkeypatch.setattr("tradingagents.factors.library.get_factor", lambda name: _ScoreFactor())

    result = analysis.compute_ic("test", list(data), [str(dates[0].date()), str(dates[1].date())], forward_days=3)

    assert result["ic_mean"] == 1.0


def test_ic_decay_summary_identifies_best_and_half_life_horizons():
    result = analysis.summarize_ic_decay(
        {1: [0.08, 0.06], 5: [0.05, 0.03], 20: [0.01, -0.01]}
    )

    assert result["best_horizon"] == 1
    assert result["half_life_horizon"] == 20
    assert result["horizons"][1]["ic_mean"] == 0.04


def test_orthogonalization_removes_linear_cross_sectional_overlap():
    frame = pd.DataFrame(
        {
            "size": [1.0, 2.0, 3.0, 4.0, 5.0],
            "value": [2.1, 3.9, 6.2, 7.8, 10.1],
            "quality": [5.0, 1.0, 3.0, 2.0, 4.0],
        },
        index=list("ABCDE"),
    )

    result = analysis.orthogonalize_factor_frame(frame)

    assert list(result.index) == list(frame.index)
    assert np.allclose(result.mean().values, 0, atol=1e-10)
    assert abs(result["size"].corr(result["value"])) < 1e-10
    assert abs(result["size"].corr(result["quality"])) < 1e-10


def test_stable_factor_selection_rejects_correlated_and_weak_factors():
    reports = [
        {"factor": "value", "ic_mean": 0.06, "ic_ir": 0.8, "positive_ratio": 0.70},
        {"factor": "cheap_clone", "ic_mean": 0.05, "ic_ir": 0.7, "positive_ratio": 0.68},
        {"factor": "quality", "ic_mean": 0.04, "ic_ir": 0.6, "positive_ratio": 0.65},
        {"factor": "noise", "ic_mean": 0.005, "ic_ir": 0.1, "positive_ratio": 0.51},
    ]
    corr = pd.DataFrame(
        [
            [1.0, 0.92, 0.20, 0.0],
            [0.92, 1.0, 0.25, 0.0],
            [0.20, 0.25, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        index=["value", "cheap_clone", "quality", "noise"],
        columns=["value", "cheap_clone", "quality", "noise"],
    )

    selected = analysis.select_stable_factors(reports, corr, max_factors=3, max_correlation=0.7)

    assert [row["factor"] for row in selected] == ["value", "quality"]
