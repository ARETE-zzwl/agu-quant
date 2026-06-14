"""Unified stock signal engine for screening, monitoring, and paper trading.

The engine intentionally stays small: it combines the existing cross-sectional
score, time-series technical state, selected factor votes, and A-share risk
overlays into one action recommendation.
"""

from __future__ import annotations

from math import isfinite
from typing import Any

import numpy as np
import pandas as pd

from .scoring_engine import ScoringEngine


ACTION_CN = {
    "BUY": "买入",
    "WATCH": "观察",
    "NEUTRAL": "中性",
    "AVOID": "回避",
    "HOLD": "持有",
    "ADD": "补仓/加仓",
    "REDUCE": "减仓",
    "TAKE_PROFIT": "止盈",
    "STOP_LOSS": "止损/平仓",
    "EXIT": "平仓",
}

CATEGORY_TO_WEIGHT_KEY = {
    "价值估值": "value_quality",
    "质量成长": "value_quality",
    "动量趋势": "momentum",
    "技术形态": "momentum",
    "资金流动": "money_flow",
    "情绪行为": "sentiment",
    "波动风险": "sentiment",
    "复合联动": "momentum",
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if isfinite(f) else default


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"]).dt.normalize()
        out = out.set_index("Date")
    else:
        out.index = pd.to_datetime(out.index).normalize()
    out = out.sort_index()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["Close"])


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window, min_periods=1).mean()
    loss = (-delta.clip(upper=0)).rolling(window, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window, min_periods=1).mean()


def _last(series: pd.Series, default: float = 0.0) -> float:
    clean = series.dropna()
    return _safe_float(clean.iloc[-1], default) if len(clean) else default


def _ret(close: pd.Series, days: int) -> float:
    if len(close) <= days:
        return 0.0
    base = _safe_float(close.iloc[-days - 1])
    if base <= 0:
        return 0.0
    return _safe_float(close.iloc[-1] / base - 1)


def _limit_pct(code: str, name: str = "") -> float:
    if "ST" in str(name).upper():
        return 0.05
    return 0.20 if str(code).startswith(("30", "68")) else 0.10


def _factor_votes(
    df: pd.DataFrame,
    strategy_key: str,
    factor_window_days: int,
) -> tuple[float, dict, list[dict]]:
    """Return factor strength in roughly [-25, 25], summary, and top rows."""
    try:
        from tradingagents.factors import get_top_by_ic
    except Exception:
        return 0.0, {"buy": 0, "sell": 0, "neutral": 0}, []

    catalog = ScoringEngine.get_strategies()
    cfg = catalog.get(strategy_key, catalog["balanced"])
    weights = cfg["weights"]
    recent = df.tail(max(20, factor_window_days))

    buy = sell = neutral = 0
    weighted_sum = 0.0
    weight_total = 0.0
    rows: list[dict] = []

    for factor in get_top_by_ic(top_n=30):
        try:
            sig = factor.signal(recent)
            vote = 1 if sig == "BUY" else -1 if sig == "SELL" else 0
            key = CATEGORY_TO_WEIGHT_KEY.get(factor.category, "momentum")
            weight = weights.get(key, 0.2) * (1 + min(abs(factor.ic_value) * 10, 0.8))
            weighted_sum += vote * weight
            weight_total += abs(weight)
            if sig == "BUY":
                buy += 1
            elif sig == "SELL":
                sell += 1
            else:
                neutral += 1
            series = factor.compute_series(recent)
            val = _last(series)
            rows.append(
                {
                    "name": factor.name,
                    "name_cn": factor.name_cn or factor.name,
                    "category": factor.category,
                    "signal": sig,
                    "value": round(val, 4),
                    "weight": round(weight, 3),
                    "desc": factor.desc_cn,
                }
            )
        except Exception:
            continue

    if weight_total <= 0:
        return 0.0, {"buy": buy, "sell": sell, "neutral": neutral}, rows
    strength = _clamp(weighted_sum / weight_total * 25, -25, 25)
    rows.sort(key=lambda r: abs(r["weight"]), reverse=True)
    return strength, {"buy": buy, "sell": sell, "neutral": neutral}, rows


def evaluate_stock_signal(
    df: pd.DataFrame,
    strategy_key: str = "balanced",
    *,
    quote: dict | None = None,
    position: dict | None = None,
    factor_window_days: int = 20,
    cross_score: float | None = None,
) -> dict:
    """Evaluate one stock and return a unified action recommendation.

    `position` may include `avg_cost`, `shares`, and `sellable`. When supplied,
    the action is interpreted as a持仓管理 signal; otherwise it is an entry
    signal for screening/monitoring.
    """
    quote = quote or {}
    df = _prepare_df(df)
    if len(df) < 30:
        return {
            "action": "NEUTRAL",
            "action_cn": ACTION_CN["NEUTRAL"],
            "score": 50,
            "confidence": 20,
            "risk_level": "未知",
            "reasons": ["历史K线不足，暂不生成交易动作"],
            "risk_notes": ["至少需要30根K线"],
            "technical": {},
            "levels": {},
            "factor_summary": {"buy": 0, "sell": 0, "neutral": 0},
            "factor_rows": [],
            "position": {},
        }

    code = str(quote.get("code") or quote.get("代码") or "")
    name = str(quote.get("name") or quote.get("名称") or "")
    close = df["Close"]
    price = _safe_float(quote.get("price"), _safe_float(close.iloc[-1]))
    ma5 = _last(close.rolling(5, min_periods=1).mean())
    ma20 = _last(close.rolling(20, min_periods=1).mean())
    ma60 = _last(close.rolling(60, min_periods=1).mean(), ma20)
    atr = _last(_atr(df))
    atr_pct = atr / price if price > 0 else 0
    rsi = _last(_rsi(close))
    ret5, ret20, ret60 = _ret(close, 5), _ret(close, 20), _ret(close, 60)
    vol20 = _last(df["Volume"].rolling(20, min_periods=1).mean(), 1)
    volume_ratio = _safe_float(df["Volume"].iloc[-1]) / max(vol20, 1)
    support20 = _last(df["Low"].tail(20).rolling(20, min_periods=1).min())
    resistance20 = _last(df["High"].tail(20).rolling(20, min_periods=1).max())

    ma_fast = close.ewm(span=12, min_periods=1, adjust=False).mean()
    ma_slow = close.ewm(span=26, min_periods=1, adjust=False).mean()
    macd_hist = _last((ma_fast - ma_slow) - (ma_fast - ma_slow).ewm(span=9, min_periods=1, adjust=False).mean())

    bb_mid = close.rolling(20, min_periods=1).mean()
    bb_std = close.rolling(20, min_periods=1).std().fillna(0)
    bb_up = _last(bb_mid + 2 * bb_std, price)
    bb_low = _last(bb_mid - 2 * bb_std, price)
    boll_pos = (price - bb_low) / max(bb_up - bb_low, 0.01)
    drawdown20 = price / max(_safe_float(close.tail(20).max()), price) - 1
    drawdown60 = price / max(_safe_float(close.tail(60).max()), price) - 1

    trend_strength = 0.0
    trend_strength += 8 if price > ma20 else -8
    trend_strength += 8 if price > ma60 else -8
    trend_strength += 8 if ma20 > ma60 else -8
    trend_strength += 5 if macd_hist > 0 else -5
    trend_strength += _clamp(ret20 * 120, -12, 12)
    trend_strength += _clamp(ret60 * 80, -10, 10)

    reversal_strength = 0.0
    if rsi < 30:
        reversal_strength += 12
    elif rsi < 42:
        reversal_strength += 5
    elif rsi > 75:
        reversal_strength -= 12
    elif rsi > 65:
        reversal_strength -= 5
    if boll_pos < 0.15:
        reversal_strength += 8
    elif boll_pos > 0.90:
        reversal_strength -= 6
    if drawdown20 < -0.12 and price > ma5:
        reversal_strength += 5

    volume_strength = 0.0
    if volume_ratio > 1.2 and ret5 > 0:
        volume_strength += 6
    if volume_ratio > 1.8 and ret5 < 0:
        volume_strength -= 8
    if volume_ratio < 0.7 and abs(ret5) < 0.02:
        volume_strength += 2

    factor_strength, factor_summary, factor_rows = _factor_votes(df, strategy_key, factor_window_days)
    cross_strength = _clamp((_safe_float(cross_score, 50) - 50) * 0.35, -18, 18) if cross_score is not None else 0

    change_pct = _safe_float(quote.get("change_pct"))
    limit_pct = _limit_pct(code, name)
    limit_up = _safe_float(quote.get("limit_up"))
    limit_down = _safe_float(quote.get("limit_down"))
    near_limit_up = bool((limit_up and price >= limit_up * 0.995) or change_pct >= limit_pct * 100 - 1)
    near_limit_down = bool((limit_down and price <= limit_down * 1.005) or change_pct <= -limit_pct * 100 + 1)

    risk_points = 0.0
    risk_notes: list[str] = []
    if atr_pct > 0.08:
        risk_points += 15
        risk_notes.append("波动率过高，仓位应降档")
    elif atr_pct > 0.05:
        risk_points += 8
        risk_notes.append("短期波动偏高")
    if price < ma60:
        risk_points += 8
        risk_notes.append("价格低于MA60，中期趋势偏弱")
    if drawdown60 < -0.20:
        risk_points += 8
        risk_notes.append("60日回撤较深")
    if volume_ratio > 3:
        risk_points += 6
        risk_notes.append("异常放量，注意事件冲击")
    if near_limit_up:
        risk_points += 8
        risk_notes.append("接近涨停，不建议追高")
    if near_limit_down:
        risk_points += 12
        risk_notes.append("接近跌停，流动性风险较高")

    risk_level = "低" if risk_points <= 10 else "中" if risk_points <= 24 else "高"
    raw_strength = trend_strength + reversal_strength + volume_strength + factor_strength * 0.55 + cross_strength
    score = int(round(_clamp(50 + raw_strength - risk_points * 0.35, 0, 100)))
    confidence = int(round(_clamp(45 + min(len(df), 120) / 4 + abs(raw_strength) * 0.25 - risk_points * 0.3, 20, 92)))

    stop_loss = round(max(support20 * 0.985, price - 2.2 * atr), 2)
    take_profit = round(max(resistance20, price + 2.8 * atr), 2)
    add_price = round(max(ma20, price - atr), 2)

    reasons: list[str] = []
    if price > ma20 and ma20 > ma60:
        reasons.append("价格站上MA20且MA20高于MA60，趋势结构偏多")
    elif price < ma20 and price < ma60:
        reasons.append("价格同时低于MA20和MA60，趋势结构偏弱")
    if factor_summary["buy"] > factor_summary["sell"]:
        reasons.append(f"高IC因子买入票多于卖出票（{factor_summary['buy']} 对 {factor_summary['sell']}）")
    elif factor_summary["sell"] > factor_summary["buy"]:
        reasons.append(f"高IC因子卖出票多于买入票（{factor_summary['sell']} 对 {factor_summary['buy']}）")
    if volume_ratio > 1.2 and ret5 > 0:
        reasons.append("近5日上涨并放量，量价配合较好")
    if rsi < 35:
        reasons.append("RSI处于偏低区间，存在超跌修复条件")
    elif rsi > 70:
        reasons.append("RSI偏高，短线不宜盲目追涨")
    if cross_score is not None:
        reasons.append(f"全市场横截面评分为 {int(round(_safe_float(cross_score)))} 分")
    if not reasons:
        reasons.append("多空信号接近均衡，等待更明确的价格或资金确认")

    pos_out: dict[str, Any] = {}
    if position:
        avg_cost = _safe_float(position.get("avg_cost") or position.get("成本"))
        shares = int(_safe_float(position.get("shares") or position.get("持有")))
        sellable = int(_safe_float(position.get("sellable", position.get("buyable_shares", shares))))
        pnl_pct = (price / avg_cost - 1) * 100 if avg_cost > 0 else _safe_float(position.get("pnl_pct"))
        pos_out = {
            "avg_cost": round(avg_cost, 3),
            "shares": shares,
            "sellable": sellable,
            "pnl_pct": round(pnl_pct, 2),
        }

        if (price <= stop_loss or pnl_pct <= -8) and score < 62:
            action = "STOP_LOSS"
        elif score <= 35 or (price < ma60 and ret20 < -0.05):
            action = "EXIT"
        elif pnl_pct >= 18 and (rsi > 68 or score < 72):
            action = "TAKE_PROFIT"
        elif score < 50 and pnl_pct > 3:
            action = "REDUCE"
        elif pnl_pct <= -4 and score >= 68 and price > ma20 and not near_limit_up:
            action = "ADD"
        elif score >= 75 and pnl_pct > -2 and price > ma20 and not near_limit_up:
            action = "ADD"
        else:
            action = "HOLD"

        if sellable <= 0 and action in {"STOP_LOSS", "EXIT", "REDUCE", "TAKE_PROFIT"}:
            risk_notes.append("当前持仓受T+1限制，可卖数量为0，信号只能延后执行")
    else:
        if near_limit_down or risk_level == "高" and score < 68:
            action = "AVOID"
        elif score >= 75 and trend_strength > 10 and risk_level != "高" and not near_limit_up:
            action = "BUY"
        elif score >= 60:
            action = "WATCH"
        elif score <= 40:
            action = "AVOID"
        else:
            action = "NEUTRAL"

    return {
        "action": action,
        "action_cn": ACTION_CN[action],
        "score": score,
        "confidence": confidence,
        "risk_level": risk_level,
        "strength": round(raw_strength, 2),
        "reasons": reasons[:5],
        "risk_notes": risk_notes[:5],
        "technical": {
            "price": round(price, 3),
            "ma5": round(ma5, 3),
            "ma20": round(ma20, 3),
            "ma60": round(ma60, 3),
            "rsi": round(rsi, 1),
            "atr_pct": round(atr_pct * 100, 2),
            "ret5": round(ret5 * 100, 2),
            "ret20": round(ret20 * 100, 2),
            "ret60": round(ret60 * 100, 2),
            "volume_ratio": round(volume_ratio, 2),
            "boll_pos": round(boll_pos, 2),
            "drawdown60": round(drawdown60 * 100, 2),
        },
        "levels": {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "add_price": add_price,
            "support": round(support20, 2),
            "resistance": round(resistance20, 2),
        },
        "factor_summary": factor_summary,
        "factor_rows": factor_rows[:20],
        "position": pos_out,
    }


def evaluate_code_signal(
    code: str,
    end_date: str,
    strategy_key: str = "balanced",
    *,
    quote: dict | None = None,
    position: dict | None = None,
    factor_window_days: int = 20,
    cross_score: float | None = None,
) -> dict:
    """Load OHLCV for `code` and evaluate the unified signal."""
    from tradingagents.dataflows.a_stock import _load_ohlcv_astock, _normalize_ticker

    norm = _normalize_ticker(code)
    q = dict(quote or {})
    q.setdefault("code", norm)
    try:
        df = _load_ohlcv_astock(norm, end_date)
    except Exception as exc:
        return {
            "action": "NEUTRAL",
            "action_cn": ACTION_CN["NEUTRAL"],
            "score": 50,
            "confidence": 10,
            "risk_level": "未知",
            "reasons": [f"K线加载失败: {exc}"],
            "risk_notes": ["无法生成交易动作"],
            "technical": {},
            "levels": {},
            "factor_summary": {"buy": 0, "sell": 0, "neutral": 0},
            "factor_rows": [],
            "position": {},
        }
    return evaluate_stock_signal(
        df,
        strategy_key=strategy_key,
        quote=q,
        position=position,
        factor_window_days=factor_window_days,
        cross_score=cross_score,
    )
