"""Backtest engine using backtrader for factor validation.

Key features:
- Single-factor backtest: long top quantile stocks
- Multi-factor backtest: weighted composite ranking
- Standard metrics: Sharpe, max drawdown, annual return, win rate
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Standardized backtest result."""
    name: str = ""
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    win_loss_ratio: float = 0.0
    total_trades: int = 0
    daily_returns: Optional[pd.Series] = None
    equity_curve: Optional[pd.Series] = None
    benchmark_curve: Optional[pd.Series] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total_return": round(self.total_return * 100, 2),
            "annual_return": round(self.annual_return * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
            "win_rate": round(self.win_rate * 100, 1),
            "win_loss_ratio": round(self.win_loss_ratio, 2),
            "total_trades": self.total_trades,
            "error": self.error,
        }


# ── Factor Portfolio Backtest (No backtrader, pure numpy for simplicity) ────────


def run_factor_backtest(
    factor_name: str,
    codes: list[str],
    start_date: str,
    end_date: str,
    top_pct: float = 0.2,
    rebalance_days: int = 5,
    max_positions: int = 20,
    cost_rate: float = 0.001,
    benchmark_code: str = "000300",
) -> BacktestResult:
    """Backtest a factor by ranking stocks and going long the top quantile.

    Args:
        factor_name: Key from ALL_FACTORS registry
        codes: Universe of stock codes
        start_date, end_date: Backtest period
        top_pct: Fraction of universe to long (top performers)
        rebalance_days: Rebalance frequency
        max_positions: Max positions
        cost_rate: Per-trade cost (0.1% default)
        benchmark_code: Benchmark for comparison

    Returns:
        BacktestResult with all metrics
    """
    from .library import get_factor
    from .compute import compute_single

    factor = get_factor(factor_name)

    try:
        # Step 1: Get factor scores for all stocks on all rebalance dates
        dates = pd.date_range(start_date, end_date, freq=f"{rebalance_days}D")
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]

        # Precompute factor scores
        factor_scores: dict[str, dict[str, float]] = {}
        for ds in date_strs:
            factor_scores[ds] = {}
            for code in codes:
                factor_scores[ds][code] = compute_single(code, factor, ds, ds)

        # Step 2: Get price data for benchmark (gracefully skip if unavailable)
        bench_returns = pd.Series(dtype=float)
        try:
            from tradingagents.dataflows.a_stock import _load_ohlcv_astock
            bench_df = _load_ohlcv_astock(benchmark_code, end_date)
            bench_df = bench_df.set_index("Date")
            bench_returns = bench_df["Close"].pct_change().loc[start_date:end_date]
        except Exception:
            logger.debug("Benchmark data unavailable for %s, skipping", benchmark_code)

        # Step 3: Simulate portfolio
        portfolio_value = 1.0
        portfolio_values = [1.0]
        positions: dict[str, float] = {}  # code -> shares
        daily_rets: list[float] = []

        trade_dates = pd.bdate_range(start_date, end_date)
        prev_date = None

        for i, td in enumerate(trade_dates):
            td_str = td.strftime("%Y-%m-%d")

            # Rebalance on schedule
            rebalance_needed = (i % rebalance_days == 0)

            if rebalance_needed and td_str in factor_scores:
                scores = factor_scores[td_str]
                sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                top_count = max(1, int(len(codes) * top_pct))
                top_count = min(top_count, max_positions)
                top_stocks = dict(sorted_stocks[:top_count])

                # Equal weight among top stocks
                weight = 1.0 / max(1, len(top_stocks))
                new_positions = {}
                for code, _ in top_stocks.items():
                    new_positions[code] = weight * portfolio_value

                # Apply costs
                turnover = sum(abs(new_positions.get(c, 0) - positions.get(c, 0))
                               for c in set(new_positions) | set(positions))
                portfolio_value -= turnover * cost_rate
                positions = new_positions

            # Mark positions to market
            daily_pnl = 0.0
            for code, pos_val in positions.items():
                try:
                    stock_df = _load_ohlcv_astock(code, td_str)
                    stock_df = stock_df.set_index("Date")
                    if td_str in stock_df.index:
                        ret = stock_df["Close"].pct_change().get(td_str, 0)
                        daily_pnl += pos_val * (ret if not pd.isna(ret) else 0)
                except Exception:
                    pass

            portfolio_value += daily_pnl
            portfolio_values.append(portfolio_value)
            daily_rets.append(daily_pnl / max(portfolio_value - daily_pnl, 0.01))

            # Cash if no positions
            if not positions:
                daily_rets.append(0)

        # Step 4: Compute metrics
        equity = pd.Series(portfolio_values)
        returns = pd.Series(daily_rets)

        total_ret = equity.iloc[-1] / equity.iloc[0] - 1
        n_years = len(returns) / 252
        annual_ret = (1 + total_ret) ** (1 / max(n_years, 0.25)) - 1

        avg_daily = returns.mean()
        std_daily = returns.std() if returns.std() > 0 else 0.01
        sharpe = (avg_daily / std_daily) * math.sqrt(252)

        # Max drawdown
        peak = equity.expanding().max()
        drawdown = (equity - peak) / peak
        max_dd = abs(drawdown.min())

        # Win rate
        wins = (returns > 0).sum()
        total = len(returns[returns != 0])
        win_rate = wins / max(total, 1)

        result = BacktestResult(
            name=f"{factor_name} (top {int(top_pct*100)}% long)",
            total_return=total_ret,
            annual_return=annual_ret,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            win_loss_ratio=0.0,
            total_trades=total,
            daily_returns=returns,
            equity_curve=equity,
            benchmark_curve=bench_returns.cumsum() if not bench_returns.empty else None,
        )

    except Exception as e:
        logger.error("Backtest failed for %s: %s", factor_name, e, exc_info=True)
        result = BacktestResult(error=str(e), name=factor_name)

    return result


def run_multi_factor_backtest(
    factor_names: list[str],
    weights: dict[str, float],
    codes: list[str],
    start_date: str,
    end_date: str,
    **kwargs,
) -> BacktestResult:
    """Backtest a weighted combination of multiple factors.

    Computes composite score = sum(factor_score * weight) and runs the same
    portfolio simulation.
    """
    from .library import get_factor
    from .compute import compute_single
    from .library import ALL_FACTORS

    # Normalize weights
    total_w = sum(weights.get(f, 0) for f in factor_names)
    if total_w == 0:
        return BacktestResult(error="All weights are 0")

    top_pct = kwargs.get("top_pct", 0.2)
    rebalance_days = kwargs.get("rebalance_days", 5)
    max_positions = kwargs.get("max_positions", 20)
    cost_rate = kwargs.get("cost_rate", 0.001)

    try:
        dates = pd.date_range(start_date, end_date, freq=f"{rebalance_days}D")
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]

        # Precompute composite scores
        composite_scores: dict[str, dict[str, float]] = {}
        for ds in date_strs:
            composite_scores[ds] = {code: 0.0 for code in codes}
            for fname in factor_names:
                factor = get_factor(fname)
                w = weights.get(fname, 0) / total_w
                for code in codes:
                    val = compute_single(code, factor, ds, ds)
                    composite_scores[ds][code] += val * w

        # Portfolio simulation (same as single-factor)
        import numpy as np

        portfolio_value = 1.0
        portfolio_values = [1.0]
        positions: dict[str, float] = {}
        daily_rets: list[float] = []

        trade_dates = pd.bdate_range(start_date, end_date)

        for i, td in enumerate(trade_dates):
            td_str = td.strftime("%Y-%m-%d")

            if i % rebalance_days == 0 and td_str in composite_scores:
                scores = composite_scores[td_str]
                sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                count = min(max_positions, max(1, int(len(codes) * top_pct)))
                top_stocks = dict(sorted_stocks[:count])
                weight = 1.0 / max(1, len(top_stocks))
                new_positions = {code: weight * portfolio_value for code in top_stocks}

                turnover = sum(abs(new_positions.get(c, 0) - positions.get(c, 0))
                               for c in set(new_positions) | set(positions))
                portfolio_value -= turnover * cost_rate
                positions = new_positions

            daily_pnl = 0.0
            from tradingagents.dataflows.a_stock import _load_ohlcv_astock
            for code, pos_val in positions.items():
                try:
                    stock_df = _load_ohlcv_astock(code, td_str)
                    stock_df = stock_df.set_index("Date")
                    if td_str in stock_df.index:
                        ret = stock_df["Close"].pct_change().get(td_str, 0)
                        daily_pnl += pos_val * (ret if not pd.isna(ret) else 0)
                except Exception:
                    pass

            portfolio_value += daily_pnl
            portfolio_values.append(portfolio_value)
            if positions:
                daily_rets.append(daily_pnl / max(portfolio_value - daily_pnl, 0.01))
            else:
                daily_rets.append(0.0)

        # Metrics
        equity = pd.Series(portfolio_values)
        returns = pd.Series(daily_rets)

        total_ret = equity.iloc[-1] - 1
        n_years = len(returns) / 252
        annual_ret = (1 + total_ret) ** (1 / max(n_years, 0.25)) - 1
        avg_daily = returns.mean()
        std_daily = max(returns.std(), 0.001)
        sharpe = (avg_daily / std_daily) * math.sqrt(252)
        peak = equity.expanding().max()
        max_dd = abs((equity - peak) / peak).min()
        wins = (returns > 0).sum()
        win_rate = wins / max(len(returns[returns != 0]), 1)

        return BacktestResult(
            name=f"Multi-factor ({len(factor_names)} factors)",
            total_return=total_ret,
            annual_return=annual_ret,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            win_loss_ratio=0.0,
            total_trades=len(returns),
            daily_returns=returns,
            equity_curve=equity,
        )

    except Exception as e:
        logger.error("Multi-factor backtest failed: %s", e, exc_info=True)
        return BacktestResult(error=str(e))
