"""Backtest the paper-trade signal engine with autonomous stock selection.

This script mirrors the Paper Trade page signal path:
evaluate_stock_signal -> BUY/ADD/REDUCE/TAKE_PROFIT/STOP_LOSS/EXIT actions.

Backtest convention:
- Signal is generated at the close of day T using data available through T.
- Orders are executed at the open of T+1.
- Empty slots are filled only by stocks whose entry signal is BUY.
- ADD buys half a target slot, REDUCE/TAKE_PROFIT sells half, EXIT/STOP_LOSS sells all.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from tradingagents.ranking.signal_engine import evaluate_stock_signal


DEFAULT_CODES = [
    "600519",
    "000858",
    "300750",
    "002594",
    "600036",
    "601318",
    "000001",
    "600276",
    "603259",
    "600900",
    "601857",
    "600030",
    "000725",
    "000333",
    "600585",
]

STAMP_DUTY = 0.0005
COMMISSION_RATE = 0.00025
COMMISSION_MIN = 5.0
TRANSFER_FEE = 0.00001


@dataclass
class Lot:
    buy_date: pd.Timestamp
    shares: int


@dataclass
class SimPosition:
    code: str
    shares: int
    avg_cost: float
    lots: list[Lot] = field(default_factory=list)

    def sellable(self, trade_date: pd.Timestamp) -> int:
        return sum(lot.shares for lot in self.lots if lot.buy_date.normalize() < trade_date.normalize())

    def add(self, trade_date: pd.Timestamp, shares: int, price: float) -> None:
        new_total = self.shares + shares
        self.avg_cost = (self.avg_cost * self.shares + price * shares) / new_total
        self.shares = new_total
        self.lots.append(Lot(trade_date.normalize(), shares))

    def remove(self, trade_date: pd.Timestamp, shares: int) -> int:
        remaining = shares
        for lot in self.lots:
            if remaining <= 0:
                break
            if lot.buy_date.normalize() >= trade_date.normalize():
                continue
            take = min(lot.shares, remaining)
            lot.shares -= take
            remaining -= take
        self.lots = [lot for lot in self.lots if lot.shares > 0]
        sold = shares - remaining
        self.shares -= sold
        return sold


def parse_codes(raw: str | None, codes_file: str | None) -> list[str]:
    if codes_file:
        text = Path(codes_file).read_text(encoding="utf-8")
        return [c.strip() for c in text.replace(",", "\n").splitlines() if c.strip()]
    if raw:
        return [c.strip() for c in raw.replace(",", "\n").splitlines() if c.strip()]
    return DEFAULT_CODES


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _lot_size(code: str) -> int:
    return 200 if str(code).startswith(("30", "68")) else 100


def _floor_lot(shares: float, code: str) -> int:
    lot = _lot_size(code)
    return int(shares // lot) * lot


def _limit_pct(code: str, name: str = "") -> float:
    if "ST" in str(name).upper():
        return 0.05
    return 0.20 if str(code).startswith(("30", "68")) else 0.10


def _calc_fee(amount: float, is_sell: bool = False) -> float:
    commission = max(COMMISSION_MIN, round(amount * COMMISSION_RATE, 2))
    stamp = round(amount * STAMP_DUTY, 2) if is_sell else 0.0
    transfer = round(amount * TRANSFER_FEE, 2)
    return commission + stamp + transfer


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"]).dt.normalize()
        out = out.set_index("Date")
    else:
        out.index = pd.to_datetime(out.index).normalize()
    out = out.sort_index()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["Open", "Close"])


def load_ohlcv_data(codes: list[str], start_date: str, end_date: str) -> dict[str, pd.DataFrame]:
    from tradingagents.dataflows.a_stock import _load_ohlcv_astock, _normalize_ticker

    start_ts = pd.Timestamp(start_date)
    warmup_ts = start_ts - pd.Timedelta(days=180)
    data: dict[str, pd.DataFrame] = {}
    for raw in codes:
        try:
            code = _normalize_ticker(raw)
            df = _prepare_df(_load_ohlcv_astock(code, end_date))
            df = df[df.index >= warmup_ts]
            if len(df) >= 70:
                data[code] = df
        except Exception as exc:
            print(f"skip {raw}: {exc}")
    return data


def _calendar(data: dict[str, pd.DataFrame], start_date: str, end_date: str) -> pd.DatetimeIndex:
    if not data:
        return pd.DatetimeIndex([])
    common = set.intersection(*(set(df.index) for df in data.values()))
    cal = pd.DatetimeIndex(sorted(common))
    return cal[(cal >= pd.Timestamp(start_date) - pd.Timedelta(days=5)) & (cal <= pd.Timestamp(end_date))]


def _quote_for(data: dict[str, pd.DataFrame], code: str, date: pd.Timestamp) -> dict[str, Any]:
    df = data[code]
    row = df.loc[date]
    pos = df.index.get_loc(date)
    prev_close = float(df["Close"].iloc[pos - 1]) if pos > 0 else float(row["Close"])
    price = float(row["Close"])
    pct = _limit_pct(code)
    return {
        "code": code,
        "price": price,
        "change_pct": (price / prev_close - 1) * 100 if prev_close > 0 else 0.0,
        "limit_up": round(prev_close * (1 + pct), 2),
        "limit_down": round(prev_close * (1 - pct), 2),
    }


def _can_buy(code: str, prev_close: float, price: float) -> bool:
    return price > 0 and price < round(prev_close * (1 + _limit_pct(code)), 2)


def _can_sell(code: str, prev_close: float, price: float) -> bool:
    return price > 0 and price > round(prev_close * (1 - _limit_pct(code)), 2)


def _market_value(
    positions: dict[str, SimPosition],
    data: dict[str, pd.DataFrame],
    date: pd.Timestamp,
    price_col: str = "Close",
) -> float:
    total = 0.0
    for code, pos in positions.items():
        if date in data[code].index:
            total += pos.shares * float(data[code].loc[date, price_col])
    return total


def _buy(
    *,
    positions: dict[str, SimPosition],
    trades: list[dict[str, Any]],
    cash: float,
    code: str,
    trade_date: pd.Timestamp,
    price: float,
    budget: float,
) -> float:
    if budget <= 0 or price <= 0:
        return cash
    shares = _floor_lot(budget / price, code)
    if shares <= 0:
        return cash
    amount = shares * price
    fee = _calc_fee(amount, is_sell=False)
    if amount + fee > cash:
        shares = _floor_lot(cash / (price * 1.002), code)
        amount = shares * price
        fee = _calc_fee(amount, is_sell=False)
    if shares <= 0 or amount + fee > cash:
        return cash

    cash -= amount + fee
    if code in positions:
        positions[code].add(trade_date, shares, price)
    else:
        positions[code] = SimPosition(
            code=code,
            shares=shares,
            avg_cost=price,
            lots=[Lot(trade_date.normalize(), shares)],
        )
    trades.append(
        {
            "date": trade_date.strftime("%Y-%m-%d"),
            "code": code,
            "action": "BUY",
            "price": round(price, 3),
            "shares": shares,
            "amount": round(amount, 2),
            "fee": round(fee, 2),
        }
    )
    return cash


def _sell(
    *,
    positions: dict[str, SimPosition],
    trades: list[dict[str, Any]],
    cash: float,
    code: str,
    trade_date: pd.Timestamp,
    price: float,
    shares: int,
    action: str,
) -> float:
    pos = positions.get(code)
    if not pos or shares <= 0:
        return cash
    shares = min(shares, pos.sellable(trade_date))
    shares = _floor_lot(shares, code)
    if shares <= 0:
        return cash
    sold = pos.remove(trade_date, shares)
    if sold <= 0:
        return cash
    amount = sold * price
    fee = _calc_fee(amount, is_sell=True)
    cash += amount - fee
    trades.append(
        {
            "date": trade_date.strftime("%Y-%m-%d"),
            "code": code,
            "action": action,
            "price": round(price, 3),
            "shares": sold,
            "amount": round(amount, 2),
            "fee": round(fee, 2),
        }
    )
    if pos.shares <= 0:
        del positions[code]
    return cash


def portfolio_metrics(equity_curve: pd.DataFrame, trades: list[dict[str, Any]]) -> dict[str, float]:
    if equity_curve.empty:
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "avg_exposure": 0.0,
            "total_trades": 0.0,
        }
    eq = equity_curve["equity"].astype(float)
    rets = eq.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1)
    years = max(len(rets) / 252, 0.1)
    annual = float((1 + total_return) ** (1 / years) - 1) if total_return > -0.99 else -1.0
    std = float(rets.std())
    sharpe = float(rets.mean() / std * math.sqrt(252)) if std > 1e-9 else 0.0
    drawdown = eq / eq.cummax() - 1
    active = rets[rets != 0]
    exposure = equity_curve["market_value"] / equity_curve["equity"].replace(0, np.nan)
    return {
        "total_return": total_return,
        "annual_return": annual,
        "sharpe_ratio": sharpe,
        "max_drawdown": abs(float(drawdown.min())),
        "win_rate": float((active > 0).mean()) if len(active) else 0.0,
        "avg_exposure": float(exposure.fillna(0).mean()),
        "total_trades": float(len(trades)),
    }


def run_paper_signal_backtest(
    codes: list[str],
    start_date: str,
    end_date: str,
    *,
    strategy_key: str = "balanced",
    initial_cash: float = 1_000_000,
    max_positions: int = 10,
    factor_window_days: int = 20,
    entry_actions: set[str] | None = None,
    min_entry_score: float = 75,
    data: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    data = {code: _prepare_df(df) for code, df in (data or load_ohlcv_data(codes, start_date, end_date)).items()}
    if len(data) < 2:
        raise ValueError("usable data is fewer than 2 stocks")

    cal = _calendar(data, start_date, end_date)
    if len(cal) < 40:
        raise ValueError("not enough common trading days")

    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    cash = float(initial_cash)
    entry_actions = entry_actions or {"BUY"}
    positions: dict[str, SimPosition] = {}
    trades: list[dict[str, Any]] = []
    action_counts: dict[str, int] = {}
    equity_rows: list[dict[str, Any]] = [
        {
            "date": cal[0].strftime("%Y-%m-%d"),
            "cash": round(cash, 2),
            "market_value": 0.0,
            "equity": round(cash, 2),
            "positions": 0,
        }
    ]

    for i in range(1, len(cal) - 1):
        signal_date = cal[i]
        trade_date = cal[i + 1]
        if trade_date < start_ts or trade_date > end_ts:
            continue

        signal_equity = cash + _market_value(positions, data, signal_date, "Close")
        target_value = signal_equity / max(1, max_positions)
        sell_orders: list[tuple[str, str, int]] = []
        add_candidates: list[tuple[str, dict[str, Any]]] = []

        for code in list(positions):
            if signal_date not in data[code].index or trade_date not in data[code].index:
                continue
            pos = positions[code]
            quote = _quote_for(data, code, signal_date)
            hist = data[code].loc[:signal_date].tail(260)
            signal = evaluate_stock_signal(
                hist,
                strategy_key=strategy_key,
                quote=quote,
                position={
                    "avg_cost": pos.avg_cost,
                    "shares": pos.shares,
                    "sellable": pos.sellable(signal_date),
                },
                factor_window_days=factor_window_days,
            )
            action = signal.get("action", "HOLD")
            action_counts[action] = action_counts.get(action, 0) + 1
            sellable_next = pos.sellable(trade_date)
            if action in {"STOP_LOSS", "EXIT"}:
                sell_orders.append((code, action, sellable_next))
            elif action in {"REDUCE", "TAKE_PROFIT"}:
                sell_orders.append((code, action, _floor_lot(sellable_next * 0.5, code)))
            elif action == "ADD":
                add_candidates.append((code, signal))

        for code, action, shares in sell_orders:
            if code not in positions or shares <= 0:
                continue
            prev_close = float(data[code].loc[signal_date, "Close"])
            open_price = float(data[code].loc[trade_date, "Open"])
            if _can_sell(code, prev_close, open_price):
                cash = _sell(
                    positions=positions,
                    trades=trades,
                    cash=cash,
                    code=code,
                    trade_date=trade_date,
                    price=open_price,
                    shares=shares,
                    action=action,
                )

        for code, signal in sorted(add_candidates, key=lambda x: x[1].get("score", 0), reverse=True):
            if code not in positions or len(positions) > max_positions:
                continue
            prev_close = float(data[code].loc[signal_date, "Close"])
            open_price = float(data[code].loc[trade_date, "Open"])
            if not _can_buy(code, prev_close, open_price):
                continue
            current_value = positions[code].shares * prev_close
            budget = min(cash * 0.98, max(0.0, target_value * 1.5 - current_value), target_value * 0.5)
            cash = _buy(
                positions=positions,
                trades=trades,
                cash=cash,
                code=code,
                trade_date=trade_date,
                price=open_price,
                budget=budget,
            )

        empty_slots = max_positions - len(positions)
        if empty_slots > 0:
            entry_candidates: list[tuple[str, dict[str, Any]]] = []
            for code in data:
                if code in positions or signal_date not in data[code].index or trade_date not in data[code].index:
                    continue
                hist = data[code].loc[:signal_date].tail(260)
                signal = evaluate_stock_signal(
                    hist,
                    strategy_key=strategy_key,
                    quote=_quote_for(data, code, signal_date),
                    factor_window_days=factor_window_days,
                )
                action = signal.get("action", "NEUTRAL")
                action_counts[action] = action_counts.get(action, 0) + 1
                if (
                    action in entry_actions
                    and float(signal.get("score", 0) or 0) >= min_entry_score
                    and signal.get("risk_level") != "高"
                ):
                    entry_candidates.append((code, signal))

            entry_candidates.sort(key=lambda x: (x[1].get("score", 0), x[1].get("confidence", 0)), reverse=True)
            for code, _signal in entry_candidates[:empty_slots]:
                prev_close = float(data[code].loc[signal_date, "Close"])
                open_price = float(data[code].loc[trade_date, "Open"])
                if not _can_buy(code, prev_close, open_price):
                    continue
                budget = min(cash * 0.98, target_value)
                cash = _buy(
                    positions=positions,
                    trades=trades,
                    cash=cash,
                    code=code,
                    trade_date=trade_date,
                    price=open_price,
                    budget=budget,
                )

        mv = _market_value(positions, data, trade_date, "Close")
        equity_rows.append(
            {
                "date": trade_date.strftime("%Y-%m-%d"),
                "cash": round(cash, 2),
                "market_value": round(mv, 2),
                "equity": round(cash + mv, 2),
                "positions": len(positions),
            }
        )

    equity_curve = pd.DataFrame(equity_rows).drop_duplicates(subset=["date"], keep="last")
    metrics = portfolio_metrics(equity_curve, trades)
    return {
        "strategy_key": strategy_key,
        "codes": sorted(data),
        "start_date": start_date,
        "end_date": end_date,
        "metrics": metrics,
        "equity_curve": equity_curve,
        "trades": trades,
        "action_counts": action_counts,
        "entry_actions": sorted(entry_actions),
        "min_entry_score": min_entry_score,
        "positions": positions,
    }


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codes", help="Comma or newline separated stock codes.")
    parser.add_argument("--codes-file", help="UTF-8 file with one stock code per line.")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--strategy", default="balanced")
    parser.add_argument("--initial-cash", type=float, default=1_000_000)
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--factor-window-days", type=int, default=20)
    parser.add_argument(
        "--entry-actions",
        default="BUY",
        help="Comma-separated entry actions allowed for empty slots, e.g. BUY,WATCH.",
    )
    parser.add_argument("--min-entry-score", type=float, default=75)
    parser.add_argument("--output-csv", help="Optional equity curve CSV path.")
    parser.add_argument("--trades-csv", help="Optional trades CSV path.")
    args = parser.parse_args()

    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = args.start_date or (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
    codes = parse_codes(args.codes, args.codes_file)

    result = run_paper_signal_backtest(
        codes,
        start_date,
        end_date,
        strategy_key=args.strategy,
        initial_cash=args.initial_cash,
        max_positions=args.max_positions,
        factor_window_days=args.factor_window_days,
        entry_actions={a.strip().upper() for a in args.entry_actions.split(",") if a.strip()},
        min_entry_score=args.min_entry_score,
    )
    metrics = result["metrics"]

    print(f"Period: {result['start_date']} to {result['end_date']}")
    print(f"Strategy: {result['strategy_key']}")
    print(f"Universe requested: {len(codes)}; loaded: {len(result['codes'])}")
    print(f"Total return: {percent(metrics['total_return'])}")
    print(f"Annual return: {percent(metrics['annual_return'])}")
    print(f"Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"Max drawdown: {percent(metrics['max_drawdown'])}")
    print(f"Win rate: {percent(metrics['win_rate'])}")
    print(f"Average exposure: {percent(metrics['avg_exposure'])}")
    print(f"Filled trades: {int(metrics['total_trades'])}")
    print(f"Entry actions: {result['entry_actions']}; min entry score: {result['min_entry_score']}")
    print(f"Action counts: {result['action_counts']}")

    if args.output_csv:
        write_csv(args.output_csv, result["equity_curve"].to_dict("records"))
        print(f"Equity CSV written: {args.output_csv}")
    if args.trades_csv:
        write_csv(args.trades_csv, result["trades"])
        print(f"Trades CSV written: {args.trades_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
