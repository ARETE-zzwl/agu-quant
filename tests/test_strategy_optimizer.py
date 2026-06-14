from __future__ import annotations

import pandas as pd

from tradingagents.ranking.strategy_optimizer import (
    compare_prepared_strategies,
    normalize_strategy_weights,
    objective_score,
    optimize_prepared_weights,
)


def test_normalize_strategy_weights_keeps_all_keys_and_sums_to_one():
    weights = normalize_strategy_weights({"momentum": 3, "money_flow": 1})

    assert set(weights) == {"value_quality", "momentum", "money_flow", "sentiment", "size"}
    assert round(sum(weights.values()), 6) == 1
    assert weights["momentum"] == 0.75
    assert weights["money_flow"] == 0.25


def test_objective_score_penalizes_drawdown():
    clean = {"annual_return": 0.18, "sharpe_ratio": 1.2, "max_drawdown": 0.08, "win_rate": 0.56}
    risky = {"annual_return": 0.18, "sharpe_ratio": 1.2, "max_drawdown": 0.30, "win_rate": 0.56}

    assert objective_score(clean) > objective_score(risky)


def test_optimizer_prefers_weight_that_matches_forward_returns():
    dates = pd.date_range("2026-01-01", periods=45, freq="B")
    returns = pd.DataFrame(
        {
            "A": [0.004] * len(dates),
            "B": [-0.002] * len(dates),
            "C": [0.001] * len(dates),
        },
        index=dates,
    )
    good = pd.Series({"A": 1.0, "B": 0.0, "C": 0.5})
    bad = pd.Series({"A": 0.0, "B": 1.0, "C": 0.5})
    category_scores = {
        d: {
            "momentum": good,
            "value_quality": bad,
            "money_flow": good,
            "sentiment": good,
            "size": good,
        }
        for d in dates
    }
    prepared = {"calendar": dates, "returns": returns, "category_scores": category_scores}
    candidates = [
        {"momentum": 1, "value_quality": 0, "money_flow": 0, "sentiment": 0, "size": 0},
        {"momentum": 0, "value_quality": 1, "money_flow": 0, "sentiment": 0, "size": 0},
    ]

    result = optimize_prepared_weights(prepared, candidates, max_positions=1, rebalance_days=5)

    assert result["best"]["weights"]["momentum"] == 1
    assert result["best"]["metrics"]["total_return"] > result["candidates"][1]["metrics"]["total_return"]


def test_compare_prepared_strategies_ranks_named_strategies():
    dates = pd.date_range("2026-01-01", periods=45, freq="B")
    returns = pd.DataFrame(
        {"A": [0.004] * len(dates), "B": [-0.002] * len(dates), "C": [0.001] * len(dates)},
        index=dates,
    )
    good = pd.Series({"A": 1.0, "B": 0.0, "C": 0.5})
    bad = pd.Series({"A": 0.0, "B": 1.0, "C": 0.5})
    prepared = {
        "calendar": dates,
        "returns": returns,
        "category_scores": {
            d: {
                "momentum": good,
                "value_quality": bad,
                "money_flow": good,
                "sentiment": good,
                "size": good,
            }
            for d in dates
        },
    }
    strategies = {
        "good_mom": {"label": "好动量", "weights": {"momentum": 1}},
        "bad_value": {"label": "差价值", "weights": {"value_quality": 1}},
    }

    ranked = compare_prepared_strategies(prepared, strategies, max_positions=1, rebalance_days=5)

    assert ranked[0]["key"] == "good_mom"
    assert ranked[0]["metrics"]["objective_score"] > ranked[1]["metrics"]["objective_score"]
