"""Dedicated small-account strategy pipeline."""

from __future__ import annotations

from typing import Any

from .recommendation_engine import run_one_click_recommendation
from .small_account import build_small_account_plan


def run_small_account_strategy(
    *,
    cash: float,
    max_positions: int = 2,
    reserve_ratio: float = 0.08,
    universe_size: int = 60,
    recommend_n: int = 10,
    lookback_days: int = 180,
) -> dict[str, Any]:
    """Run the concentrated backtest, consensus and lot-aware allocation."""
    if int(max_positions) not in {1, 2}:
        raise ValueError("小资金策略最多只能持有1或2只股票")

    analysis = run_one_click_recommendation(
        universe_size=universe_size,
        recommend_n=recommend_n,
        lookback_days=lookback_days,
        top_pct=0.2,
        rebalance_days=10,
        max_positions=int(max_positions),
        include_consensus=True,
    )
    consensus = analysis.get("consensus_analysis", {})
    plan = build_small_account_plan(
        consensus.get("candidates", []),
        cash=cash,
        max_positions=int(max_positions),
        reserve_ratio=reserve_ratio,
    )
    return {
        **analysis,
        "settings": {
            "cash": float(cash),
            "max_positions": int(max_positions),
            "reserve_ratio": float(reserve_ratio),
        },
        "plan": plan,
    }
