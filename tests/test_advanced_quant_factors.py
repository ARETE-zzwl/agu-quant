from __future__ import annotations

import numpy as np
import pandas as pd

from tradingagents.factors import ALL_FACTORS, FACTOR_CATEGORIES
from tradingagents.ranking.scoring_engine import ScoringEngine
from tradingagents.ranking.strategy_optimizer import (
    FACTOR_MAP_PRESETS,
    get_strategy_factor_map,
)


ADVANCED_FACTOR_NAMES = [
    "adv_vol_target_momentum",
    "adv_trend_consistency",
    "adv_liquidity_shock_reversal",
    "adv_amihud_liquidity",
    "adv_vol_stability",
    "adv_residual_momentum",
]


def _sample_ohlcv(rows: int = 180) -> pd.DataFrame:
    dates = pd.date_range("2025-09-01", periods=rows, freq="B")
    drift = np.linspace(10, 18, rows)
    cycle = np.sin(np.arange(rows) / 7) * 0.7
    close = pd.Series(drift + cycle, index=dates)
    open_ = close.shift(1).fillna(close.iloc[0]) * (1 + np.cos(np.arange(rows) / 3) * 0.004)
    high = pd.concat([open_, close], axis=1).max(axis=1) * 1.02
    low = pd.concat([open_, close], axis=1).min(axis=1) * 0.98
    volume = pd.Series(900_000 + np.arange(rows) * 4500 + (np.arange(rows) % 13) * 30_000, index=dates)
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


def test_advanced_quant_factors_are_registered():
    assert "Advanced Quant" in FACTOR_CATEGORIES
    for name in ADVANCED_FACTOR_NAMES:
        assert name in ALL_FACTORS
        assert ALL_FACTORS[name].category == "Advanced Quant"


def test_advanced_quant_factors_compute_finite_recent_values():
    df = _sample_ohlcv()

    for name in ADVANCED_FACTOR_NAMES:
        series = ALL_FACTORS[name].compute_series(df)
        recent = series.replace([np.inf, -np.inf], np.nan).dropna().tail(20)
        assert len(recent) > 0, name


def test_advanced_quant_strategy_presets_are_user_selectable():
    keys = {p["key"] for p in ScoringEngine.get_presets()}

    assert "advanced_vol_momentum" in keys
    assert "advanced_liquidity_reversal" in keys
    assert "advanced_lowvol_quality" in keys
    assert "advanced_stable_momentum_opt" in keys


def test_advanced_quant_strategies_use_dedicated_factor_map():
    catalog = ScoringEngine.get_strategies()
    factor_map = get_strategy_factor_map(catalog["advanced_vol_momentum"])

    assert factor_map == FACTOR_MAP_PRESETS["advanced_quant"]
    assert "adv_vol_target_momentum" in factor_map["momentum"]
    assert "adv_amihud_liquidity" in factor_map["money_flow"]
