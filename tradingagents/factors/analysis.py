"""Factor analysis: IC, IR, correlation — fixed data pipeline."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_stock_data(codes: list[str], end_date: str) -> dict[str, pd.DataFrame]:
    """Load OHLCV data for multiple stocks, return dict code->DataFrame."""
    from tradingagents.dataflows.a_stock import _load_ohlcv_astock
    data = {}
    for c in codes:
        df = _load_ohlcv_astock(c, end_date)
        if not df.empty:
            df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
            data[c] = df.set_index("Date").sort_index()
    return data


def _factor_value(factor, df, date_str):
    """Get factor value at nearest date <= date_str."""
    ts = pd.Timestamp(date_str)
    series = factor.compute_series(df)
    avail = series.index[series.index <= ts]
    if len(avail) == 0:
        return 0.0
    val = series.loc[avail[-1]]
    return float(val) if not pd.isna(val) else 0.0


def _forward_return(code, data, ds, next_ds):
    """Compute forward return between two dates for a stock."""
    df = data.get(code)
    if df is None:
        return 0.0
    t1, t2 = pd.Timestamp(ds), pd.Timestamp(next_ds)
    if t1 not in df.index:
        a1 = df.index[df.index <= t1]
        if len(a1) == 0:
            return 0.0
        t1 = a1[-1]
    if t2 not in df.index:
        a2 = df.index[df.index <= t2]
        if len(a2) == 0:
            return 0.0
        t2 = a2[-1]
    if t1 >= t2:
        return 0.0
    return float(df["Close"].loc[t2] / df["Close"].loc[t1] - 1)


def _forward_return_after_days(code, data, ds, forward_days):
    """Compute a return after N observed trading rows, not N input dates."""
    df = data.get(code)
    if df is None or df.empty:
        return 0.0
    signal_date = pd.Timestamp(ds)
    available = df.index[df.index <= signal_date]
    if len(available) == 0:
        return 0.0
    start = available[-1]
    start_pos = int(df.index.get_loc(start))
    end_pos = start_pos + max(1, int(forward_days))
    if end_pos >= len(df.index):
        return 0.0
    end = df.index[end_pos]
    return float(df["Close"].loc[end] / df["Close"].loc[start] - 1)


def compute_ic(factor_name: str, codes: list[str], dates: list[str], forward_days: int = 5) -> dict:
    """Information Coefficient: factor score vs forward return."""
    from .library import get_factor

    factor = get_factor(factor_name)
    end_date = dates[-1] if dates else "2026-05-23"
    data = load_stock_data(codes, end_date)
    if not data:
        return {"ic_mean": 0, "ic_std": 0, "ic_ir": 0, "positive_ratio": 0, "ic_series": []}

    ic_values = []
    ic_dates = []
    for i, ds in enumerate(dates[:-1]):
        scores = {}
        for code, df in data.items():
            v = _factor_value(factor, df, ds)
            if factor.direction < 0:
                v = -v
            if abs(v) > 0.000001:
                scores[code] = v

        fwd = {}
        for code in scores:
            fwd[code] = _forward_return_after_days(code, data, ds, forward_days)

        common = set(scores) & {c for c, r in fwd.items() if abs(r) > 0.000001}
        if len(common) < 3:
            continue

        s_vals = [scores[c] for c in common]
        f_vals = [fwd[c] for c in common]
        if np.std(s_vals) < 0.0001 or np.std(f_vals) < 0.0001:
            continue

        s_rank = pd.Series(s_vals).rank()
        f_rank = pd.Series(f_vals).rank()
        ic = s_rank.corr(f_rank)
        if not np.isnan(ic):
            ic_values.append(ic)
            ic_dates.append(ds)

    if not ic_values:
        return {"ic_mean": 0, "ic_std": 0, "ic_ir": 0, "positive_ratio": 0, "ic_series": []}

    ic_arr = np.array(ic_values)
    return {
        "ic_mean": round(float(np.mean(ic_arr)), 4),
        "ic_std": round(float(np.std(ic_arr)), 4),
        "ic_ir": round(float(np.mean(ic_arr)) / max(float(np.std(ic_arr)), 0.001), 2),
        "positive_ratio": round(float((ic_arr > 0).mean()), 2),
        "ic_series": list(zip(ic_dates, [round(float(v), 4) for v in ic_values])),
    }


def summarize_ic_decay(ic_by_horizon: dict[int, list[float]]) -> dict:
    """Summarize RankIC strength and decay across forward-return horizons."""
    horizons = []
    for horizon in sorted(ic_by_horizon):
        values = np.asarray(ic_by_horizon[horizon], dtype=float)
        values = values[np.isfinite(values)]
        mean = float(values.mean()) if len(values) else 0.0
        std = float(values.std()) if len(values) else 0.0
        horizons.append(
            {
                "horizon": int(horizon),
                "ic_mean": round(mean, 4),
                "ic_std": round(std, 4),
                "ic_ir": round(mean / max(std, 0.001), 2),
                "positive_ratio": round(float((values > 0).mean()), 2) if len(values) else 0.0,
                "observations": int(len(values)),
            }
        )
    if not horizons:
        return {"horizons": [], "best_horizon": None, "half_life_horizon": None}
    best = max(horizons, key=lambda row: abs(row["ic_mean"]))
    baseline = abs(horizons[0]["ic_mean"])
    half_life = next(
        (row["horizon"] for row in horizons[1:] if abs(row["ic_mean"]) <= baseline / 2),
        None,
    )
    return {
        "horizons": horizons,
        "best_horizon": best["horizon"],
        "half_life_horizon": half_life,
    }


def orthogonalize_factor_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Sequentially residualize standardized factor columns cross-sectionally."""
    clean = frame.astype(float).replace([np.inf, -np.inf], np.nan)
    clean = clean.apply(lambda column: column.fillna(column.median()).fillna(0.0))
    result = pd.DataFrame(index=clean.index)
    basis: list[np.ndarray] = []
    for name in clean.columns:
        values = clean[name].to_numpy(dtype=float)
        std = float(values.std())
        vector = (values - values.mean()) / std if std > 1e-12 else np.zeros_like(values)
        for previous in basis:
            denominator = float(np.dot(previous, previous))
            if denominator > 1e-12:
                vector = vector - previous * float(np.dot(vector, previous) / denominator)
        vector = vector - vector.mean()
        residual_std = float(vector.std())
        if residual_std > 1e-12:
            vector = vector / residual_std
        else:
            vector = np.zeros_like(vector)
        result[name] = vector
        basis.append(vector)
    return result


def select_stable_factors(
    reports: list[dict],
    correlation: pd.DataFrame,
    *,
    max_factors: int = 8,
    min_abs_ic: float = 0.02,
    min_positive_ratio: float = 0.55,
    max_correlation: float = 0.7,
) -> list[dict]:
    """Greedily retain strong, stable factors that are not near-duplicates."""
    eligible = []
    for report in reports:
        ic_mean = float(report.get("ic_mean", 0) or 0)
        positive_ratio = float(report.get("positive_ratio", 0) or 0)
        ic_ir = float(report.get("ic_ir", 0) or 0)
        if abs(ic_mean) < min_abs_ic or positive_ratio < min_positive_ratio:
            continue
        quality_score = abs(ic_mean) * (0.5 + positive_ratio) * max(abs(ic_ir), 0.1)
        eligible.append({**report, "selection_score": round(quality_score, 6)})
    eligible.sort(key=lambda row: row["selection_score"], reverse=True)

    selected: list[dict] = []
    for report in eligible:
        name = report["factor"]
        too_correlated = False
        for chosen in selected:
            other = chosen["factor"]
            if name in correlation.index and other in correlation.columns:
                value = correlation.loc[name, other]
                if pd.notna(value) and abs(float(value)) > max_correlation:
                    too_correlated = True
                    break
        if not too_correlated:
            selected.append(report)
        if len(selected) >= max(1, int(max_factors)):
            break
    return selected


def factor_correlation(factor_names: list[str], codes: list[str], date: str) -> pd.DataFrame:
    """Cross-sectional factor correlation on a single date."""
    from .library import get_factor
    end_date = date
    data = load_stock_data(codes, end_date)
    if not data:
        return pd.DataFrame(index=factor_names, columns=factor_names, data=0.0)

    factors = [get_factor(n) for n in factor_names]
    rows = {}
    for code, df in data.items():
        rows[code] = {n: _factor_value(f, df, date) for n, f in zip(factor_names, factors)}

    mat = pd.DataFrame.from_dict(rows, orient="index")
    mat = mat.replace(0, np.nan).dropna()
    if len(mat) < 3:
        return pd.DataFrame(index=factor_names, columns=factor_names, data=0.0)

    return mat.corr().fillna(0)


def factor_turnover(factor_name: str, codes: list[str], date1: str, date2: str, top_pct: float = 0.2) -> float:
    """Portfolio turnover between two dates."""
    from .library import get_factor
    data = load_stock_data(codes, max(date1, date2))
    factor = get_factor(factor_name)

    def top_set(ds):
        scores = {}
        for code, df in data.items():
            scores[code] = _factor_value(factor, df, ds)
        srt = sorted(scores.items(), key=lambda x: x[1],
                     reverse=(factor.direction > 0))
        n = max(1, int(len(srt) * top_pct))
        return {c for c, _ in srt[:n]}

    t1 = top_set(date1)
    t2 = top_set(date2)
    if not t1:
        return 0.0
    return 1 - len(t1 & t2) / len(t1)


def factor_report(factor_name: str, codes: list[str], dates: list[str],
                  top_pct: float = 0.2, rebalance_days: int = 5) -> dict:
    """Comprehensive factor report."""
    from .backtest import run_factor_backtest

    ic = compute_ic(factor_name, codes, dates)
    bt = run_factor_backtest(
        factor_name, codes, dates[0], dates[-1],
        top_pct=top_pct, rebalance_days=rebalance_days,
    )

    turnover_val = 0.0
    if len(dates) >= 2:
        turnover_val = factor_turnover(factor_name, codes, dates[0], dates[1], top_pct)

    return {
        "factor": factor_name,
        "ic_mean": ic["ic_mean"],
        "ic_std": ic["ic_std"],
        "ic_ir": ic["ic_ir"],
        "positive_ratio": ic["positive_ratio"],
        "sharpe_ratio": round(bt.sharpe_ratio, 2),
        "annual_return": round(bt.annual_return, 4),
        "max_drawdown": round(bt.max_drawdown, 4),
        "win_rate": round(bt.win_rate, 4),
        "turnover": round(turnover_val, 2),
        "stability": round(ic["positive_ratio"] * (1 - min(abs(bt.max_drawdown), 0.5)), 2),
        "score": round(
            ic["ic_ir"] * 3 + bt.sharpe_ratio * 2 + ic["positive_ratio"] * 2
            - min(abs(bt.max_drawdown), 0.5) * 2, 1,
        ),
    }
