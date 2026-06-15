from __future__ import annotations

from tradingagents.ranking.scoring_engine import SCORE_KEYS, ScoringEngine


def test_strategy_catalog_exposes_expanded_user_selectable_presets():
    presets = ScoringEngine.get_presets()
    keys = {p["key"] for p in presets}

    assert len(presets) >= 24
    assert "backtest_value_size_alpha" in keys
    assert "flow_value_rotation" in keys
    assert "defensive_value_size" in keys


def test_strategy_details_have_page_ready_metadata_and_valid_weights():
    details = ScoringEngine.get_strategy_details()

    assert len(details) >= 24
    for item in details:
        assert item["key"]
        assert item["label"]
        assert item["desc"]
        assert item["family"]
        assert item["risk_level"]
        assert item["holding_period"]
        assert item["best_for"]
        assert item["implementation"]
        assert set(item["weights"]) == set(SCORE_KEYS)
        assert round(sum(item["weights"].values()), 6) == 1
