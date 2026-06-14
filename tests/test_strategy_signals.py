from __future__ import annotations

import pandas as pd

from tradingagents.ranking.signal_engine import evaluate_stock_signal


def _ohlcv(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="B")
    close = pd.Series(closes, index=dates)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close.shift(1).fillna(close.iloc[0]).values,
            "High": (close * 1.01).values,
            "Low": (close * 0.99).values,
            "Close": close.values,
            "Volume": [1_000_000 + i * 1000 for i in range(len(closes))],
        }
    )


def test_bullish_trend_prefers_buy_or_watch():
    df = _ohlcv([10 + i * 0.08 for i in range(90)])

    result = evaluate_stock_signal(df, strategy_key="balanced")

    assert result["score"] >= 60
    assert result["action"] in {"BUY", "WATCH"}
    assert result["levels"]["stop_loss"] < result["technical"]["price"]


def test_weak_losing_position_prefers_exit_or_stop_loss():
    df = _ohlcv([20 - i * 0.12 for i in range(90)])

    result = evaluate_stock_signal(
        df,
        strategy_key="balanced",
        position={"avg_cost": 20.0, "shares": 100, "sellable": 100},
    )

    assert result["action"] in {"EXIT", "STOP_LOSS", "REDUCE"}
    assert result["position"]["pnl_pct"] < 0


def test_overheated_profitable_position_prefers_take_profit_or_reduce():
    prices = [10 + i * 0.05 for i in range(70)] + [14, 14.6, 15.2, 15.8, 16.4]
    df = _ohlcv(prices)

    result = evaluate_stock_signal(
        df,
        strategy_key="trend_breakout",
        position={"avg_cost": 10.0, "shares": 100, "sellable": 100},
    )

    assert result["action"] in {"TAKE_PROFIT", "REDUCE", "HOLD", "ADD"}
    assert result["position"]["pnl_pct"] > 20
    assert "take_profit" in result["levels"]
