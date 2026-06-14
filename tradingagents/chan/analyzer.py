"""Rule-based Chan theory analyzer.

This is a deterministic, backtestable subset of Chan theory. It intentionally
uses explicit rules instead of subjective manual charting:
- three-bar fractals,
- alternating strokes with a minimum bar distance,
- centers from overlapping ranges of three consecutive strokes,
- divergence approximated by weaker MACD histogram area / stroke power.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class Fractal:
    idx: int
    date: Any
    kind: str  # top / bottom
    price: float

    def to_dict(self) -> dict:
        return {"idx": self.idx, "date": self.date, "kind": self.kind, "price": round(self.price, 3)}


@dataclass
class Stroke:
    start_idx: int
    end_idx: int
    start_date: Any
    end_date: Any
    direction: str  # up / down
    start_price: float
    end_price: float
    high: float
    low: float
    bars: int
    pct: float
    power: float
    macd_area: float

    def to_dict(self) -> dict:
        return {
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "direction": self.direction,
            "start_price": round(self.start_price, 3),
            "end_price": round(self.end_price, 3),
            "high": round(self.high, 3),
            "low": round(self.low, 3),
            "bars": self.bars,
            "pct": round(self.pct * 100, 2),
            "power": round(self.power, 4),
            "macd_area": round(self.macd_area, 4),
        }


@dataclass
class Center:
    start_idx: int
    end_idx: int
    low: float
    high: float
    stroke_start: int
    stroke_end: int
    strength: int

    def to_dict(self) -> dict:
        return {
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "low": round(self.low, 3),
            "high": round(self.high, 3),
            "stroke_start": self.stroke_start,
            "stroke_end": self.stroke_end,
            "strength": self.strength,
        }


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
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
    return out.dropna(subset=["High", "Low", "Close"])


def _macd_hist(close: pd.Series) -> pd.Series:
    fast = close.ewm(span=12, adjust=False, min_periods=1).mean()
    slow = close.ewm(span=26, adjust=False, min_periods=1).mean()
    dif = fast - slow
    dea = dif.ewm(span=9, adjust=False, min_periods=1).mean()
    return dif - dea


def detect_fractals(df: pd.DataFrame) -> list[Fractal]:
    fractals: list[Fractal] = []
    highs = df["High"].values
    lows = df["Low"].values
    dates = list(df.index)
    for i in range(1, len(df) - 1):
        if highs[i] > highs[i - 1] and highs[i] >= highs[i + 1]:
            fractals.append(Fractal(i, dates[i], "top", float(highs[i])))
        if lows[i] < lows[i - 1] and lows[i] <= lows[i + 1]:
            fractals.append(Fractal(i, dates[i], "bottom", float(lows[i])))
    fractals.sort(key=lambda x: x.idx)
    return fractals


def _more_extreme(a: Fractal, b: Fractal) -> Fractal:
    if a.kind == "top":
        return b if b.price >= a.price else a
    return b if b.price <= a.price else a


def build_strokes(df: pd.DataFrame, fractals: list[Fractal], min_stroke_bars: int = 5) -> list[Stroke]:
    if len(fractals) < 2:
        return []

    hist = _macd_hist(df["Close"])
    cleaned: list[Fractal] = []
    for f in fractals:
        if not cleaned:
            cleaned.append(f)
            continue
        last = cleaned[-1]
        if f.kind == last.kind:
            cleaned[-1] = _more_extreme(last, f)
            continue
        if f.idx - last.idx < min_stroke_bars:
            if (last.kind == "bottom" and f.kind == "top" and f.price > last.price) or (
                last.kind == "top" and f.kind == "bottom" and f.price < last.price
            ):
                continue
            cleaned[-1] = f
            continue
        cleaned.append(f)

    strokes: list[Stroke] = []
    for a, b in zip(cleaned, cleaned[1:]):
        if a.kind == b.kind or b.idx <= a.idx:
            continue
        direction = "up" if a.kind == "bottom" and b.kind == "top" else "down"
        if direction == "up" and b.price <= a.price:
            continue
        if direction == "down" and b.price >= a.price:
            continue
        seg = df.iloc[a.idx:b.idx + 1]
        macd_area = float(hist.iloc[a.idx:b.idx + 1].abs().sum())
        price_move = abs(b.price - a.price) / max(abs(a.price), 0.01)
        volume_factor = float(np.log10(max(seg["Volume"].mean(), 1)))
        strokes.append(
            Stroke(
                start_idx=a.idx,
                end_idx=b.idx,
                start_date=a.date,
                end_date=b.date,
                direction=direction,
                start_price=a.price,
                end_price=b.price,
                high=float(seg["High"].max()),
                low=float(seg["Low"].min()),
                bars=b.idx - a.idx,
                pct=(b.price / max(a.price, 0.01) - 1),
                power=price_move * volume_factor,
                macd_area=macd_area,
            )
        )
    return strokes


def build_centers(strokes: list[Stroke]) -> list[Center]:
    centers: list[Center] = []
    for i in range(len(strokes) - 2):
        tri = strokes[i:i + 3]
        lows = [s.low for s in tri]
        highs = [s.high for s in tri]
        low = max(lows)
        high = min(highs)
        if low <= high:
            start_idx = min(s.start_idx for s in tri)
            end_idx = max(s.end_idx for s in tri)
            if centers and low <= centers[-1].high and high >= centers[-1].low:
                prev = centers[-1]
                prev.low = max(prev.low, low)
                prev.high = min(prev.high, high)
                prev.end_idx = end_idx
                prev.stroke_end = i + 2
                prev.strength += 1
            else:
                centers.append(Center(start_idx, end_idx, low, high, i, i + 2, 1))
    return centers


def _latest_divergence(strokes: list[Stroke]) -> dict | None:
    if len(strokes) < 3:
        return None
    last = strokes[-1]
    prev_same = next((s for s in reversed(strokes[:-1]) if s.direction == last.direction), None)
    if prev_same is None:
        return None

    weaker = last.macd_area < prev_same.macd_area * 0.82 or last.power < prev_same.power * 0.82
    if not weaker:
        return None
    if last.direction == "down" and last.end_price < prev_same.end_price:
        return {"kind": "bullish", "text": "下跌新低但力度衰减，出现底背驰近似"}
    if last.direction == "up" and last.end_price > prev_same.end_price:
        return {"kind": "bearish", "text": "上涨新高但力度衰减，出现顶背驰近似"}
    return None


def _signals(df: pd.DataFrame, strokes: list[Stroke], centers: list[Center]) -> list[dict]:
    if not strokes:
        return []
    close = float(df["Close"].iloc[-1])
    last = strokes[-1]
    prev = strokes[-2] if len(strokes) >= 2 else None
    latest_center = centers[-1] if centers else None
    div = _latest_divergence(strokes)
    signals: list[dict] = []

    if div and div["kind"] == "bullish":
        signals.append({"type": "B1", "side": "buy", "strength": 72, "reason": div["text"]})
    if div and div["kind"] == "bearish":
        signals.append({"type": "S1", "side": "sell", "strength": 72, "reason": div["text"]})

    if prev and last.direction == "up" and prev.direction == "down":
        prior_down = next((s for s in reversed(strokes[:-2]) if s.direction == "down"), None)
        if prior_down and prev.end_price >= prior_down.end_price * 0.995:
            signals.append({"type": "B2", "side": "buy", "strength": 66, "reason": "下跌后回升且不再有效创新低，二买确认近似"})
    if prev and last.direction == "down" and prev.direction == "up":
        prior_up = next((s for s in reversed(strokes[:-2]) if s.direction == "up"), None)
        if prior_up and prev.end_price <= prior_up.end_price * 1.005:
            signals.append({"type": "S2", "side": "sell", "strength": 66, "reason": "上涨后回落且不再有效创新高，二卖确认近似"})

    if latest_center:
        if close > latest_center.high and last.low > latest_center.high * 0.985:
            signals.append({"type": "B3", "side": "buy", "strength": 76, "reason": "价格离开中枢后回抽未跌回中枢，三买突破确认"})
        if close < latest_center.low and last.high < latest_center.low * 1.015:
            signals.append({"type": "S3", "side": "sell", "strength": 76, "reason": "价格跌破中枢后反抽未回中枢，三卖破位确认"})

    return signals


def _agent_summary(df: pd.DataFrame, strokes: list[Stroke], centers: list[Center], signals: list[dict]) -> dict:
    close = float(df["Close"].iloc[-1])
    latest_center = centers[-1] if centers else None
    last_stroke = strokes[-1] if strokes else None
    buy_strength = max([s["strength"] for s in signals if s["side"] == "buy"], default=0)
    sell_strength = max([s["strength"] for s in signals if s["side"] == "sell"], default=0)

    if sell_strength >= 72:
        action, score = "SELL", max(65, sell_strength)
        action_cn = "减仓/卖出"
    elif buy_strength >= 72:
        action, score = "BUY", buy_strength
        action_cn = "试买/买入"
    elif buy_strength >= 60:
        action, score = "WATCH_BUY", buy_strength
        action_cn = "观察买点"
    elif sell_strength >= 60:
        action, score = "WATCH_SELL", sell_strength
        action_cn = "观察卖点"
    else:
        action, score, action_cn = "HOLD", 50, "等待"

    reasons = []
    if last_stroke:
        reasons.append(f"最新一笔为{('向上' if last_stroke.direction == 'up' else '向下')}，幅度{last_stroke.pct*100:.1f}%")
    if latest_center:
        if close > latest_center.high:
            reasons.append(f"现价在最近中枢上沿{latest_center.high:.2f}上方")
        elif close < latest_center.low:
            reasons.append(f"现价跌破最近中枢下沿{latest_center.low:.2f}")
        else:
            reasons.append(f"现价处于中枢{latest_center.low:.2f}-{latest_center.high:.2f}内震荡")
    reasons.extend(s["reason"] for s in signals[:2])

    if latest_center:
        stop_loss = latest_center.low * 0.985 if action in {"BUY", "WATCH_BUY"} else close * 0.94
        take_profit = max(latest_center.high * 1.06, close * 1.08)
    else:
        stop_loss = close * 0.93
        take_profit = close * 1.10

    return {
        "action": action,
        "action_cn": action_cn,
        "score": int(score),
        "price": round(close, 3),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "reasons": reasons[:5],
        "risk_notes": [
            "缠论结构信号有主观化风险，本系统采用可回测简化规则",
            "一买/一卖偏左侧，二买/三买确认度通常更高",
        ],
    }


def analyze_chan(df: pd.DataFrame, min_stroke_bars: int = 5) -> dict:
    """Analyze a price series using simplified Chan theory rules."""
    prepared = _prepare_df(df)
    if len(prepared) < max(12, min_stroke_bars * 4):
        return {
            "fractals": [],
            "strokes": [],
            "centers": [],
            "signals": [],
            "summary": {"action": "HOLD", "action_cn": "数据不足", "score": 0, "reasons": ["K线数量不足"]},
            "action": "HOLD",
        }
    fractals = detect_fractals(prepared)
    strokes = build_strokes(prepared, fractals, min_stroke_bars=min_stroke_bars)
    centers = build_centers(strokes)
    signals = _signals(prepared, strokes, centers)
    summary = _agent_summary(prepared, strokes, centers, signals)
    return {
        "fractals": [f.to_dict() for f in fractals],
        "strokes": [s.to_dict() for s in strokes],
        "centers": [c.to_dict() for c in centers],
        "signals": signals,
        "summary": summary,
        "action": summary["action"],
        "df": prepared,
    }
