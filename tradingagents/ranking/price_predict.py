"""Price target prediction based on volatility, factors, and technical levels."""

from __future__ import annotations

import numpy as np
import pandas as pd


def predict_targets(code: str, end_date: str) -> dict:
    """Predict short/medium-term price targets based on historical data.

    Returns:
        dict with keys:
        - current_price, stop_loss, take_profit_1, take_profit_2
        - support, resistance, volatility_20d
        - trend: 'bullish'/'bearish'/'neutral'
        - confidence: 'high'/'medium'/'low'
        - expected_return_1m, expected_return_3m (annualized %)
        - reasoning: str
    """
    from tradingagents.dataflows.a_stock import _load_ohlcv_astock

    df = _load_ohlcv_astock(code, end_date)
    if df.empty:
        return {"error": "no data"}
    df = df.set_index(pd.to_datetime(df["Date"]).dt.normalize()).sort_index()
    if len(df) < 60:
        return {"error": "insufficient data"}

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    current = float(close.iloc[-1])

    # Volatility
    ret = close.pct_change().dropna()
    vol_20d = float(ret.tail(20).std())
    vol_60d = float(ret.tail(60).std())

    # Support / Resistance
    recent_60 = close.tail(60)
    support_1 = float(recent_60.rolling(20).min().min())
    support_2 = float(recent_60.rolling(60).min().min())
    resistance_1 = float(recent_60.rolling(20).max().max())
    resistance_2 = float(recent_60.rolling(60).max().max())

    # Moving averages
    ma20 = float(close.tail(20).mean())
    ma60 = float(close.tail(60).mean()) if len(close) >= 60 else ma20

    # Trend strength
    trend_20d = (current / ma20 - 1)
    trend_60d = (current / ma60 - 1) if len(close) >= 60 else 0

    if trend_20d > 0.02 and trend_60d > 0:
        trend = "bullish"
    elif trend_20d < -0.02 and trend_60d < 0:
        trend = "bearish"
    else:
        trend = "neutral"

    # ATR for stop loss
    atr = float(pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1).tail(14).mean())

    # Dynamic target levels
    if trend == "bullish":
        stop_loss = round(current - 2.5 * atr, 2)
        take_profit_1 = round(min(resistance_1, current * (1 + vol_20d * 3)), 2)
        take_profit_2 = round(min(resistance_2, current * (1 + vol_20d * 5)), 2)
    elif trend == "bearish":
        stop_loss = round(current + 2.5 * atr, 2)
        take_profit_1 = round(max(support_1, current * (1 - vol_20d * 3)), 2)
        take_profit_2 = round(max(support_2, current * (1 - vol_20d * 5)), 2)
    else:
        stop_loss = round(current - 2 * atr, 2)
        take_profit_1 = round(current * (1 + vol_20d * 2.5), 2)
        take_profit_2 = round(current * (1 + vol_20d * 4), 2)

    # Expected returns
    exp_ret_1m = round(trend_20d * 252 / 12 * 100, 1) if trend == "bullish" else \
        round(trend_20d * 252 / 12 * 100 * 0.5, 1)
    exp_ret_3m = round(trend_60d * 252 / 4 * 100, 1) if trend == "bullish" else \
        round(trend_60d * 252 / 4 * 100 * 0.5, 1)

    # Confidence
    vol_ratio = vol_20d / max(vol_60d, 0.001)
    if vol_ratio < 0.8 and trend != "neutral":
        confidence = "high"
    elif vol_ratio < 1.5:
        confidence = "medium"
    else:
        confidence = "low"

    # Reasoning
    reasons = []
    if current > ma20:
        reasons.append(f"价格在MA20({ma20:.1f})上方，短期偏强")
    else:
        reasons.append(f"价格在MA20({ma20:.1f})下方，短期承压")
    if current > ma60:
        reasons.append(f"MA60({ma60:.1f})支撑有效")
    else:
        reasons.append(f"MA60({ma60:.1f})构成压力")
    if abs(trend_20d) < 0.01:
        reasons.append("20日趋势不明显，处于震荡区间")
    if vol_ratio < 0.8:
        reasons.append("波动收窄中，突破概率增大")
    elif vol_ratio > 1.5:
        reasons.append("波动扩张中，方向性信号需确认")

    return {
        "current_price": current,
        "stop_loss": stop_loss,
        "take_profit_1": take_profit_1,
        "take_profit_2": take_profit_2,
        "support": support_1,
        "resistance": resistance_1,
        "volatility_20d": round(vol_20d * 100, 2),
        "trend": trend,
        "confidence": confidence,
        "expected_return_1m": exp_ret_1m,
        "expected_return_3m": exp_ret_3m,
        "reasoning": "；".join(reasons),
        "risk_reward": round(abs(take_profit_1 - current) / max(abs(stop_loss - current), 0.01), 1),
    }


def predict_batch(codes: list[str], end_date: str) -> list[dict]:
    """Predict targets for multiple stocks."""
    results = []
    for c in codes:
        try:
            p = predict_targets(c, end_date)
            p["code"] = c
            results.append(p)
        except Exception as e:
            results.append({"code": c, "error": str(e)})
    return results
