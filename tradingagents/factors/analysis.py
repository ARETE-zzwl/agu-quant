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


def compute_ic(factor_name: str, codes: list[str], dates: list[str], forward_days: int = 5) -> dict:
    """Information Coefficient: factor score vs forward return."""
    from .library import get_factor

    factor = get_factor(factor_name)
    end_date = dates[-1] if dates else "2026-05-23"
    data = load_stock_data(codes, end_date)
    if not data:
        return {"ic_mean": 0, "ic_std": 0, "ic_ir": 0, "positive_ratio": 0, "ic_series": []}

    ic_values = []
    for i, ds in enumerate(dates[:-1]):
        scores = {}
        for code, df in data.items():
            v = _factor_value(factor, df, ds)
            if abs(v) > 0.000001:
                scores[code] = v

        next_ds = dates[min(i + 1, len(dates) - 1)]
        fwd = {}
        for code in scores:
            fwd[code] = _forward_return(code, data, ds, next_ds)

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

    if not ic_values:
        return {"ic_mean": 0, "ic_std": 0, "ic_ir": 0, "positive_ratio": 0, "ic_series": []}

    ic_arr = np.array(ic_values)
    return {
        "ic_mean": round(float(np.mean(ic_arr)), 4),
        "ic_std": round(float(np.std(ic_arr)), 4),
        "ic_ir": round(float(np.mean(ic_arr)) / max(float(np.std(ic_arr)), 0.001), 2),
        "positive_ratio": round(float((ic_arr > 0).mean()), 2),
        "ic_series": list(zip(dates[:len(ic_values)], [round(float(v), 4) for v in ic_values])),
    }


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
