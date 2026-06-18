from __future__ import annotations

from tradingagents.ranking.scoring_engine import SCORE_KEYS, ScoringEngine


def test_strategy_catalog_exposes_expanded_user_selectable_presets():
    presets = ScoringEngine.get_presets()
    keys = {p["key"] for p in presets}

    assert len(presets) >= 24
    assert "backtest_value_size_alpha" in keys
    assert "flow_value_rotation" in keys
    assert "defensive_value_size" in keys
    assert {
        "classic_12_1_momentum",
        "research_value_momentum",
        "research_quality_momentum",
        "research_downside_defense",
    }.issubset(keys)


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


def test_research_strategies_expose_sources_and_dedicated_factor_map():
    from tradingagents.ranking.strategy_optimizer import (
        FACTOR_MAP_PRESETS,
        get_strategy_factor_map,
    )

    catalog = ScoringEngine.get_strategies()
    detail = ScoringEngine.get_strategy_detail("classic_12_1_momentum")
    factor_map = get_strategy_factor_map(catalog["classic_12_1_momentum"])

    assert factor_map == FACTOR_MAP_PRESETS["research_classics"]
    assert "mom_12m1m" in factor_map["momentum"]
    assert "quality_spread" in factor_map["value_quality"]
    assert "downside_risk" in factor_map["size"]
    assert detail["research_sources"]
    assert all(source["url"].startswith("https://") for source in detail["research_sources"])
