"""Backtest simplified Chan theory strategies."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .analyzer import analyze_chan


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"]).dt.normalize()
        out = out.set_index("Date")
    else:
        out.index = pd.to_datetime(out.index).normalize()
    return out.sort_index()


def _strategy_match(signals: list[dict], strategy: str, side: str) -> bool:
    if strategy == "combined":
        allowed = {"B1", "B2", "B3"} if side == "buy" else {"S1", "S2", "S3"}
    elif strategy == "t1_divergence":
        allowed = {"B1"} if side == "buy" else {"S1"}
    elif strategy == "t2_confirm":
        allowed = {"B2"} if side == "buy" else {"S2"}
    elif strategy == "t3_breakout":
        allowed = {"B3"} if side == "buy" else {"S3"}
    else:
        allowed = {"B1", "B2", "B3"} if side == "buy" else {"S1", "S2", "S3"}
    return any(s["side"] == side and s["type"] in allowed for s in signals)


def run_chan_backtest(
    df: pd.DataFrame,
    strategy: str = "combined",
    min_stroke_bars: int = 5,
    initial_cash: float = 1.0,
    cost_rate: float = 0.0012,
    stop_loss_pct: float = 0.08,
) -> dict[str, Any]:
    """Backtest Chan buy/sell point strategies using next-open execution."""
    data = _prepare_df(df)
    if len(data) < 80:
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "trades": [],
            "equity_curve": pd.Series([initial_cash]),
        }

    cash = initial_cash
    shares = 0.0
    entry_price = 0.0
    trades: list[dict] = []
    equity_vals = []
    equity_dates = []
    daily_returns = []
    last_equity = initial_cash

    start_i = max(60, min_stroke_bars * 8)
    for i in range(start_i, len(data) - 1):
        hist = data.iloc[:i + 1]
        next_bar = data.iloc[i + 1]
        exec_price = float(next_bar["Open"] if next_bar["Open"] > 0 else next_bar["Close"])
        analysis = analyze_chan(hist, min_stroke_bars=min_stroke_bars)
        signals = analysis.get("signals", [])

        equity = cash + shares * float(data["Close"].iloc[i])
        if shares > 0:
            stop_hit = exec_price <= entry_price * (1 - stop_loss_pct)
            sell_signal = _strategy_match(signals, strategy, "sell")
            if stop_hit or sell_signal:
                revenue = shares * exec_price * (1 - cost_rate)
                pnl_pct = exec_price / entry_price - 1
                cash = revenue
                trades.append({
                    "date": data.index[i + 1],
                    "action": "SELL",
                    "price": round(exec_price, 3),
                    "pnl_pct": round(pnl_pct * 100, 2),
                    "reason": "止损" if stop_hit else "缠论卖点",
                })
                shares = 0.0
                entry_price = 0.0
        else:
            if _strategy_match(signals, strategy, "buy"):
                shares = cash * (1 - cost_rate) / exec_price
                entry_price = exec_price
                cash = 0.0
                trades.append({
                    "date": data.index[i + 1],
                    "action": "BUY",
                    "price": round(exec_price, 3),
                    "pnl_pct": 0.0,
                    "reason": "缠论买点",
                })

        equity = cash + shares * float(data["Close"].iloc[i + 1])
        equity_dates.append(data.index[i + 1])
        equity_vals.append(equity)
        daily_returns.append(equity / last_equity - 1 if last_equity > 0 else 0)
        last_equity = equity

    equity_curve = pd.Series(equity_vals, index=equity_dates)
    if equity_curve.empty:
        equity_curve = pd.Series([initial_cash])

    total_return = float(equity_curve.iloc[-1] / initial_cash - 1)
    rets = pd.Series(daily_returns)
    years = max(len(rets) / 252, 0.1)
    annual_return = (1 + total_return) ** (1 / years) - 1 if total_return > -0.99 else -1.0
    sharpe = float(rets.mean() / rets.std() * math.sqrt(252)) if rets.std() > 1e-9 else 0.0
    drawdown = equity_curve / equity_curve.cummax() - 1
    max_drawdown = abs(float(drawdown.min())) if not drawdown.empty else 0.0
    sell_trades = [t for t in trades if t["action"] == "SELL"]
    win_rate = sum(1 for t in sell_trades if t["pnl_pct"] > 0) / max(len(sell_trades), 1)

    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "total_trades": len(sell_trades),
        "trades": trades,
        "equity_curve": equity_curve,
    }
