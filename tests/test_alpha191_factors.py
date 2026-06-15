from __future__ import annotations

import numpy as np
import pandas as pd

from tradingagents.factors import ALL_FACTORS, FACTOR_CATEGORIES
from tradingagents.ranking.scoring_engine import ScoringEngine
from tradingagents.ranking.strategy_optimizer import (
    FACTOR_MAP_PRESETS,
    get_strategy_factor_map,
)


ALPHA191_FACTOR_NAMES = [
    f"gtja_alpha{i:03d}"
    for i in range(1, 192)
    if i != 30
]


def _sample_ohlcv(rows: int = 220) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=rows, freq="B")
    base = pd.Series(np.linspace(10, 16, rows), index=dates)
    wave = pd.Series(np.sin(np.arange(rows) / 4) * 0.4, index=dates)
    close = base + wave
    open_ = close.shift(1).fillna(close.iloc[0]) * (1 + np.cos(np.arange(rows)) * 0.002)
    high = pd.concat([open_, close], axis=1).max(axis=1) * 1.015
    low = pd.concat([open_, close], axis=1).min(axis=1) * 0.985
    volume = pd.Series(1_000_000 + np.arange(rows) * 3000, index=dates)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": open_.values,
            "High": high.values,
            "Low": low.values,
            "Close": close.values,
            "Volume": volume.values,
        }
    ).set_index("Date")


def test_alpha191_factor_subset_is_registered():
    assert "GTJA Alpha191" in FACTOR_CATEGORIES
    assert len(FACTOR_CATEGORIES["GTJA Alpha191"]) == 190
    assert "gtja_alpha030" not in ALL_FACTORS
    for name in ALPHA191_FACTOR_NAMES:
        assert name in ALL_FACTORS
        assert ALL_FACTORS[name].category == "GTJA Alpha191"


def test_alpha191_factors_compute_finite_recent_values():
    df = _sample_ohlcv()

    for name in ALPHA191_FACTOR_NAMES:
        series = ALL_FACTORS[name].compute_series(df)
        recent = series.replace([np.inf, -np.inf], np.nan).dropna().tail(10)
        assert len(recent) > 0, name


def test_alpha191_strategy_presets_are_user_selectable():
    keys = {p["key"] for p in ScoringEngine.get_presets()}

    assert "alpha191_balanced" in keys
    assert "alpha191_momentum_reversal" in keys
    assert "alpha191_flow_volatility" in keys
    assert "alpha191_momentum_core" in keys
    assert "alpha191_flow_lowvol_opt" in keys


def test_alpha191_strategies_use_alpha191_factor_map():
    catalog = ScoringEngine.get_strategies()
    factor_map = get_strategy_factor_map(catalog["alpha191_balanced"])

    assert factor_map == FACTOR_MAP_PRESETS["alpha191_style"]
    assert "gtja_alpha001" in factor_map["money_flow"]
    assert "gtja_alpha014" in factor_map["sentiment"]
    assert "gtja_alpha150" in factor_map["money_flow"]
    assert "gtja_alpha172" in factor_map["size"]
