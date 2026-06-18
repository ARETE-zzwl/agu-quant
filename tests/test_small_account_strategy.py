from __future__ import annotations

import pytest

from tradingagents.ranking import small_account_strategy as strategy


def test_small_account_strategy_is_the_only_pipeline_enabling_consensus(monkeypatch):
    captured = {}

    def fake_one_click(**kwargs):
        captured.update(kwargs)
        return {
            "consensus_analysis": {
                "candidates": [
                    {
                        "code": "600001",
                        "name": "样本",
                        "price": 10,
                        "score": 88,
                        "action": "BUY",
                        "risk": "低",
                        "source": {"代码": "600001"},
                    }
                ]
            }
        }

    monkeypatch.setattr(strategy, "run_one_click_recommendation", fake_one_click)

    result = strategy.run_small_account_strategy(
        cash=20_000,
        max_positions=1,
        reserve_ratio=0.1,
        universe_size=40,
        recommend_n=5,
        lookback_days=180,
    )

    assert captured["include_consensus"] is True
    assert captured["max_positions"] == 1
    assert result["plan"]["orders"][0]["code"] == "600001"
    assert result["settings"]["cash"] == 20_000


def test_small_account_strategy_rejects_more_than_two_positions():
    with pytest.raises(ValueError, match="1或2"):
        strategy.run_small_account_strategy(cash=50_000, max_positions=3)
