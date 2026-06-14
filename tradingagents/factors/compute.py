"""Historical factor computation engine — fixed date handling."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from .library import Factor, ALL_FACTORS, get_factor

logger = logging.getLogger(__name__)


def load_stock_df(code: str, end_date: str) -> pd.DataFrame | None:
    """Load and prepare a stock's OHLCV DataFrame with proper date index."""
    from tradingagents.dataflows.a_stock import _load_ohlcv_astock

    df = _load_ohlcv_astock(code, end_date)
    if df.empty:
        return None
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    return df.set_index("Date").sort_index()


def _nearest_date(series: pd.Series, target: str) -> Optional[float]:
    """Get factor value at or just before target date."""
    ts = pd.Timestamp(target)
    available = series.index[series.index <= ts]
    if len(available) == 0:
        return None
    val = series.loc[available[-1]]
    return float(val) if not pd.isna(val) else None


def compute_single(code: str, factor: Factor, target_date: str, end_date: str = None) -> float:
    """Compute a factor's value for one stock at a specific date.

    Returns the factor value at the nearest trading day <= target_date.
    """
    end = end_date or target_date
    df = load_stock_df(code, end)
    if df is None:
        return 0.0
    series = factor.compute_series(df)
    val = _nearest_date(series, target_date)
    return val if val is not None else 0.0


def compute_cross_section(
    codes: list[str],
    factor_names: list[str],
    date: str,
) -> pd.DataFrame:
    """Factor values for multiple stocks on a single date.

    Returns DataFrame: index=codes, columns=factor_names.
    """
    rows = {}
    for code in codes:
        df = load_stock_df(code, date)
        if df is None:
            rows[code] = {n: 0.0 for n in factor_names}
            continue
        row = {}
        for n in factor_names:
            f = get_factor(n)
            series = f.compute_series(df)
            val = _nearest_date(series, date)
            row[n] = val if val is not None else 0.0
        rows[code] = row
    return pd.DataFrame.from_dict(rows, orient="index")


def compute_stock_history_indicators(
    code: str, start_date: str, end_date: str,
) -> pd.DataFrame | None:
    """Compute ALL factors for one stock over time. Returns wide DataFrame."""
    df = load_stock_df(code, end_date)
    if df is None:
        return None
    df = df[df.index >= start_date]
    result = pd.DataFrame(index=df.index)
    for name, f in ALL_FACTORS.items():
        try:
            result[name] = f.compute_series(df)
        except Exception:
            result[name] = 0.0
    return result
