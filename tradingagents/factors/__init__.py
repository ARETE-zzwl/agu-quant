"""80-factor Alpha library with backtest, analysis, and AI optimization."""

from .library import (
    ALL_FACTORS, FACTOR_CATEGORIES, Factor,
    get_factor, get_factors_by_category, get_top_by_ic,
)
from .compute import compute_single, compute_cross_section, compute_stock_history_indicators, load_stock_df
from .backtest import BacktestResult, run_factor_backtest, run_multi_factor_backtest
from .analysis import (
    compute_ic,
    factor_correlation,
    factor_report,
    factor_turnover,
    orthogonalize_factor_frame,
    select_stable_factors,
    summarize_ic_decay,
)
from .ai_optimizer import AIWeightOptimizer, AISynergyAnalyzer, AIFactorDiscovery

__all__ = [
    "ALL_FACTORS", "FACTOR_CATEGORIES", "Factor",
    "get_factor", "get_factors_by_category", "get_top_by_ic",
    "compute_single", "compute_cross_section", "compute_stock_history_indicators",
    "BacktestResult", "run_factor_backtest", "run_multi_factor_backtest",
    "compute_ic", "factor_correlation", "factor_report", "factor_turnover",
    "orthogonalize_factor_frame", "select_stable_factors", "summarize_ic_decay",
    "AIWeightOptimizer", "AISynergyAnalyzer", "AIFactorDiscovery",
]
