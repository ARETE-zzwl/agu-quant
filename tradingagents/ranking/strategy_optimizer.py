"""Backtest-based strategy scoring and automatic five-factor weight tuning."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCORE_KEYS = ["value_quality", "momentum", "money_flow", "sentiment", "size"]

WEIGHT_LABELS = {
    "value_quality": "价值品质",
    "momentum": "动量趋势",
    "money_flow": "资金流向",
    "sentiment": "情绪/反转",
    "size": "规模/低波",
}

# The five live-scoring dimensions are mapped to backtestable historical factors.
# `size` uses stability/low-risk proxies because the current local OHLCV cache does
# not contain historical market-cap snapshots.
DEFAULT_CATEGORY_FACTORS = {
    "value_quality": ["earnings_yield", "quality_value", "value_mom", "low_risk_quality"],
    "momentum": ["mom_3m", "vol_adj_mom", "ma_crossover", "trend_quality"],
    "money_flow": ["volume_price_trend", "capital_flow_diff", "smart_money_index", "fund_tech_confirm"],
    "sentiment": ["intraday_reversal", "boll_position", "rsi_signal", "reversal_risk"],
    "size": ["price_stability", "idio_vol", "max_drawdown_1y", "low_risk_quality"],
}

OPTIMIZED_FILE = Path.home() / ".tradingagents" / "optimized_strategies.json"


def normalize_strategy_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """Return all five strategy weights normalized to sum to 1."""
    weights = weights or {}
    cleaned = {k: max(0.0, float(weights.get(k, 0) or 0)) for k in SCORE_KEYS}
    total = sum(cleaned.values())
    if total <= 0:
        return {k: 1 / len(SCORE_KEYS) for k in SCORE_KEYS}
    return {k: round(cleaned[k] / total, 6) for k in SCORE_KEYS}


def objective_score(metrics: dict[str, float]) -> float:
    """Score a backtest result; higher is better.

    Uses risk-adjusted return, drawdown penalty, win-rate, and turnover penalty.
    This is intentionally conservative for A-share paper trading.
    """
    annual = max(-0.8, min(0.8, float(metrics.get("annual_return", 0) or 0)))
    sharpe = max(-3.0, min(3.0, float(metrics.get("sharpe_ratio", 0) or 0)))
    drawdown = min(0.6, abs(float(metrics.get("max_drawdown", 0) or 0)))
    win_rate = max(0.0, min(1.0, float(metrics.get("win_rate", 0) or 0)))
    turnover = max(0.0, min(1.0, float(metrics.get("avg_turnover", 0) or 0)))
    return round(
        annual * 120
        + sharpe * 18
        + (win_rate - 0.5) * 35
        - drawdown * 90
        - turnover * 8,
        3,
    )


def _nearest_value(series: pd.Series, date: pd.Timestamp) -> float | None:
    available = series.index[series.index <= date]
    if len(available) == 0:
        return None
    value = series.loc[available[-1]]
    if pd.isna(value):
        return None
    return float(value)


def _load_data(codes: list[str], start_date: str, end_date: str) -> dict[str, pd.DataFrame]:
    from tradingagents.dataflows.a_stock import _load_ohlcv_astock

    data: dict[str, pd.DataFrame] = {}
    start_ts = pd.Timestamp(start_date)
    warmup_ts = start_ts - pd.Timedelta(days=420)
    for code in codes:
        try:
            df = _load_ohlcv_astock(code, end_date)
            if df.empty:
                continue
            df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
            df = df[df["Date"] >= warmup_ts].set_index("Date").sort_index()
            if len(df) >= 45:
                data[code] = df
        except Exception:
            continue
    return data


def _rank_values(values: dict[str, float]) -> pd.Series:
    if not values:
        return pd.Series(dtype=float)
    s = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return pd.Series(dtype=float)
    if s.nunique() <= 1:
        return pd.Series(0.5, index=s.index)
    return s.rank(pct=True)


def prepare_strategy_backtest(
    codes: list[str],
    start_date: str,
    end_date: str,
    factor_map: dict[str, list[str]] | None = None,
    rebalance_days: int = 5,
) -> dict[str, Any]:
    """Load data and precompute category rank scores for repeated weight tests."""
    from tradingagents.factors import get_factor

    factor_map = factor_map or DEFAULT_CATEGORY_FACTORS
    codes = [c.strip() for c in codes if c and c.strip()]
    data = _load_data(codes, start_date, end_date)
    if len(data) < 2:
        raise ValueError("可用股票数据不足，至少需要2只股票")

    close = pd.DataFrame({c: df["Close"] for c, df in data.items()}).sort_index()
    close = close.loc[pd.Timestamp(start_date):pd.Timestamp(end_date)].ffill()
    close = close.dropna(how="all")
    if len(close) < 20:
        raise ValueError("回测区间内有效交易日不足")

    returns = close.pct_change().fillna(0)
    calendar = close.index
    rebalance_dates = list(calendar[::max(1, int(rebalance_days))])

    factor_series: dict[tuple[str, str], pd.Series] = {}
    all_factor_names = sorted({f for factors in factor_map.values() for f in factors})
    for fname in all_factor_names:
        factor = get_factor(fname)
        for code, df in data.items():
            try:
                series = factor.compute_series(df)
                series.index = pd.to_datetime(series.index).normalize()
                if factor.direction < 0:
                    series = -series
                factor_series[(fname, code)] = series
            except Exception:
                continue

    category_scores: dict[pd.Timestamp, dict[str, pd.Series]] = {}
    for date in rebalance_dates:
        category_scores[date] = {}
        for category, factor_names in factor_map.items():
            factor_ranks = []
            for fname in factor_names:
                values = {}
                for code in data:
                    series = factor_series.get((fname, code))
                    if series is None:
                        continue
                    value = _nearest_value(series, date)
                    if value is not None:
                        values[code] = value
                ranks = _rank_values(values)
                if not ranks.empty:
                    factor_ranks.append(ranks)

            if factor_ranks:
                category_scores[date][category] = pd.concat(factor_ranks, axis=1).mean(axis=1)
            else:
                category_scores[date][category] = pd.Series(0.5, index=list(data.keys()))

    return {
        "codes": list(data.keys()),
        "calendar": calendar,
        "returns": returns,
        "category_scores": category_scores,
        "factor_map": factor_map,
        "start_date": start_date,
        "end_date": end_date,
    }


def run_weight_backtest(
    prepared: dict[str, Any],
    weights: dict[str, float],
    *,
    top_pct: float = 0.2,
    max_positions: int = 10,
    rebalance_days: int = 5,
    cost_rate: float = 0.0012,
) -> dict[str, Any]:
    """Backtest normalized category weights on precomputed category scores."""
    weights = normalize_strategy_weights(weights)
    calendar: pd.DatetimeIndex = prepared["calendar"]
    returns: pd.DataFrame = prepared["returns"]
    category_scores: dict[pd.Timestamp, dict[str, pd.Series]] = prepared["category_scores"]

    equity = [1.0]
    daily_returns: list[float] = []
    current_positions: set[str] = set()
    turnovers: list[float] = []
    last_rebalance_date = None

    for i in range(1, len(calendar)):
        signal_date = calendar[i - 1]
        should_rebalance = last_rebalance_date is None or (i - 1) % max(1, rebalance_days) == 0
        if should_rebalance:
            score = pd.Series(0.0, index=returns.columns)
            score_data = category_scores.get(signal_date)
            if score_data is None:
                nearest = [d for d in category_scores if d <= signal_date]
                score_data = category_scores[nearest[-1]] if nearest else {}
            for key, weight in weights.items():
                s = score_data.get(key, pd.Series(0.5, index=returns.columns))
                score = score.add(s.reindex(returns.columns).fillna(0.5) * weight, fill_value=0)

            top_count = min(max_positions, max(1, int(len(score.dropna()) * top_pct)))
            new_positions = set(score.sort_values(ascending=False).head(top_count).index)
            if current_positions:
                overlap = len(current_positions & new_positions)
                turnover = 1 - overlap / max(len(current_positions), 1)
            else:
                turnover = 1.0
            turnovers.append(turnover)
            current_positions = new_positions
            last_rebalance_date = signal_date
            equity[-1] *= max(0.0, 1 - turnover * cost_rate)

        trade_date = calendar[i]
        if current_positions:
            row = returns.loc[trade_date, list(current_positions)].replace([np.inf, -np.inf], np.nan).fillna(0)
            daily_ret = float(row.mean())
        else:
            daily_ret = 0.0
        daily_returns.append(daily_ret)
        equity.append(equity[-1] * (1 + daily_ret))

    eq = pd.Series(equity, index=calendar[:len(equity)])
    rets = pd.Series(daily_returns, index=calendar[1:len(daily_returns) + 1])
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1)
    years = max(len(rets) / 252, 0.1)
    annual_return = float((1 + total_return) ** (1 / years) - 1) if total_return > -0.99 else -1.0
    std = float(rets.std())
    sharpe = float(rets.mean() / std * math.sqrt(252)) if std > 1e-9 else 0.0
    drawdown = eq / eq.cummax() - 1
    max_drawdown = abs(float(drawdown.min()))
    active = rets[rets != 0]
    win_rate = float((active > 0).mean()) if len(active) else 0.0

    metrics = {
        "total_return": total_return,
        "annual_return": annual_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "avg_turnover": float(np.mean(turnovers)) if turnovers else 0.0,
        "total_trades": len(turnovers),
    }
    metrics["objective_score"] = objective_score(metrics)
    return {
        "weights": weights,
        "metrics": metrics,
        "equity_curve": eq,
        "daily_returns": rets,
    }


def generate_weight_candidates(base_weights: dict[str, float] | None = None) -> list[dict[str, float]]:
    """Generate conservative candidates around presets and research priors."""
    base = normalize_strategy_weights(base_weights)
    seeds = [
        base,
        {"value_quality": 0.20, "momentum": 0.20, "money_flow": 0.20, "sentiment": 0.20, "size": 0.20},
        {"value_quality": 0.35, "momentum": 0.15, "money_flow": 0.20, "sentiment": 0.10, "size": 0.20},
        {"value_quality": 0.20, "momentum": 0.30, "money_flow": 0.25, "sentiment": 0.15, "size": 0.10},
        {"value_quality": 0.25, "momentum": 0.15, "money_flow": 0.15, "sentiment": 0.15, "size": 0.30},
        {"value_quality": 0.10, "momentum": 0.25, "money_flow": 0.30, "sentiment": 0.25, "size": 0.10},
    ]
    candidates: list[dict[str, float]] = []
    for seed in seeds:
        candidates.append(normalize_strategy_weights(seed))
        for key in SCORE_KEYS:
            boosted = dict(seed)
            boosted[key] = boosted.get(key, 0) + 0.15
            candidates.append(normalize_strategy_weights(boosted))
    # Deduplicate while preserving order.
    seen = set()
    unique = []
    for c in candidates:
        marker = tuple(round(c[k], 4) for k in SCORE_KEYS)
        if marker not in seen:
            seen.add(marker)
            unique.append(c)
    return unique


def optimize_prepared_weights(
    prepared: dict[str, Any],
    candidates: list[dict[str, float]],
    **backtest_kwargs,
) -> dict[str, Any]:
    """Run all candidate weights and return the best result plus ranking."""
    results = []
    for weights in candidates:
        result = run_weight_backtest(prepared, weights, **backtest_kwargs)
        results.append(result)
    results.sort(key=lambda r: r["metrics"]["objective_score"], reverse=True)
    return {
        "best": results[0],
        "candidates": results,
        "prepared_meta": {
            "codes": prepared.get("codes", []),
            "start_date": prepared.get("start_date", ""),
            "end_date": prepared.get("end_date", ""),
        },
    }


def compare_prepared_strategies(
    prepared: dict[str, Any],
    strategies: dict[str, dict],
    **backtest_kwargs,
) -> list[dict[str, Any]]:
    """Backtest named strategies on prepared data and rank them by objective."""
    rows: list[dict[str, Any]] = []
    for key, cfg in strategies.items():
        weights = cfg.get("weights")
        if not weights:
            continue
        result = run_weight_backtest(prepared, weights, **backtest_kwargs)
        rows.append(
            {
                "key": key,
                "label": cfg.get("label", key),
                "desc": cfg.get("desc", ""),
                "filters": cfg.get("filters", {}),
                "weights": result["weights"],
                "metrics": result["metrics"],
                "equity_curve": result.get("equity_curve"),
            }
        )
    rows.sort(key=lambda r: r["metrics"]["objective_score"], reverse=True)
    return rows


def compare_strategy_presets(
    codes: list[str],
    start_date: str,
    end_date: str,
    *,
    strategy_keys: list[str] | None = None,
    top_pct: float = 0.2,
    rebalance_days: int = 10,
    max_positions: int = 10,
    cost_rate: float = 0.0012,
) -> dict[str, Any]:
    """Prepare data once and compare ScoringEngine preset strategies."""
    from .scoring_engine import ScoringEngine

    catalog = ScoringEngine.get_strategies()
    if strategy_keys:
        selected = {k: catalog[k] for k in strategy_keys if k in catalog}
    else:
        selected = {k: v for k, v in catalog.items() if k != "custom"}
    prepared = prepare_strategy_backtest(codes, start_date, end_date, rebalance_days=rebalance_days)
    ranked = compare_prepared_strategies(
        prepared,
        selected,
        top_pct=top_pct,
        rebalance_days=rebalance_days,
        max_positions=max_positions,
        cost_rate=cost_rate,
    )
    return {
        "ranked": ranked,
        "best": ranked[0] if ranked else None,
        "prepared_meta": {
            "codes": prepared.get("codes", []),
            "start_date": start_date,
            "end_date": end_date,
        },
    }


def optimize_strategy_weights(
    codes: list[str],
    start_date: str,
    end_date: str,
    *,
    base_weights: dict[str, float] | None = None,
    top_pct: float = 0.2,
    rebalance_days: int = 5,
    max_positions: int = 10,
    cost_rate: float = 0.0012,
) -> dict[str, Any]:
    """Prepare data, test candidate weights, and return the best strategy."""
    prepared = prepare_strategy_backtest(codes, start_date, end_date, rebalance_days=rebalance_days)
    candidates = generate_weight_candidates(base_weights)
    result = optimize_prepared_weights(
        prepared,
        candidates,
        top_pct=top_pct,
        rebalance_days=rebalance_days,
        max_positions=max_positions,
        cost_rate=cost_rate,
    )
    return result


def load_optimized_strategies() -> dict[str, dict]:
    if not OPTIMIZED_FILE.exists():
        return {}
    try:
        with open(OPTIMIZED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_optimized_strategy(
    base_key: str,
    base_label: str,
    weights: dict[str, float],
    metrics: dict[str, float],
    *,
    start_date: str,
    end_date: str,
    codes: list[str],
    filters: dict | None = None,
) -> str:
    """Persist an optimized strategy so ScoringEngine pages can reuse it."""
    OPTIMIZED_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = load_optimized_strategies()
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    key = f"opt_{base_key}_{stamp}"
    data[key] = {
        "label": f"回测调权-{base_label}",
        "desc": (
            f"{start_date}~{end_date} 回测生成；"
            f"年化{metrics.get('annual_return', 0)*100:.1f}%、"
            f"夏普{metrics.get('sharpe_ratio', 0):.2f}、"
            f"回撤{metrics.get('max_drawdown', 0)*100:.1f}%"
        ),
        "filters": filters or {},
        "weights": normalize_strategy_weights(weights),
        "optimized": True,
        "metrics": metrics,
        "source": {
            "base_key": base_key,
            "start_date": start_date,
            "end_date": end_date,
            "codes": codes,
        },
    }
    with open(OPTIMIZED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return key
