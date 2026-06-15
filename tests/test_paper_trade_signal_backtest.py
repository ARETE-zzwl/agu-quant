from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backtest_paper_trade_signals.py"
SPEC = importlib.util.spec_from_file_location("backtest_paper_trade_signals", SCRIPT_PATH)
bt = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = bt
SPEC.loader.exec_module(bt)


def _ohlcv(prices: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(prices), freq="B")
    close = pd.Series(prices, index=dates)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close.shift(1).fillna(close.iloc[0]).values,
            "High": (close * 1.01).values,
            "Low": (close * 0.99).values,
            "Close": close.values,
            "Volume": [1_000_000] * len(prices),
        }
    )


def test_paper_signal_backtest_buys_and_manages_position(monkeypatch):
    prices_a = [10 + i * 0.05 for i in range(70)]
    prices_b = [20 - i * 0.02 for i in range(70)]
    data = {"AAA": _ohlcv(prices_a), "BBB": _ohlcv(prices_b)}

    def fake_signal(df, strategy_key="balanced", *, quote=None, position=None, **kwargs):
        code = quote["code"]
        if position is None:
            action = "BUY" if code == "AAA" else "NEUTRAL"
            return {"action": action, "score": 80 if action == "BUY" else 50, "confidence": 80}
        if quote["price"] / position["avg_cost"] - 1 > 0.03:
            return {"action": "TAKE_PROFIT", "score": 60, "confidence": 70}
        return {"action": "HOLD", "score": 65, "confidence": 65}

    monkeypatch.setattr(bt, "evaluate_stock_signal", fake_signal)

    result = bt.run_paper_signal_backtest(
        ["AAA", "BBB"],
        "2026-01-15",
        "2026-04-09",
        data=data,
        max_positions=1,
    )

    actions = [trade["action"] for trade in result["trades"]]
    assert "BUY" in actions
    assert "TAKE_PROFIT" in actions
    assert result["metrics"]["total_trades"] >= 2
    assert result["equity_curve"]["positions"].max() == 1


def test_paper_signal_backtest_can_enter_high_score_watchlist(monkeypatch):
    data = {
        "AAA": _ohlcv([10 + i * 0.04 for i in range(70)]),
        "BBB": _ohlcv([20 + i * 0.01 for i in range(70)]),
    }

    def fake_signal(df, strategy_key="balanced", *, quote=None, position=None, **kwargs):
        if position is not None:
            return {"action": "HOLD", "score": 65, "confidence": 60}
        return {"action": "WATCH", "score": 68, "confidence": 70, "risk_level": "低"}

    monkeypatch.setattr(bt, "evaluate_stock_signal", fake_signal)

    strict = bt.run_paper_signal_backtest(
        ["AAA", "BBB"],
        "2026-01-15",
        "2026-04-09",
        data=data,
        max_positions=1,
    )
    expanded = bt.run_paper_signal_backtest(
        ["AAA", "BBB"],
        "2026-01-15",
        "2026-04-09",
        data=data,
        max_positions=1,
        entry_actions={"BUY", "WATCH"},
        min_entry_score=65,
    )

    assert strict["metrics"]["total_trades"] == 0
    assert expanded["metrics"]["total_trades"] > 0
