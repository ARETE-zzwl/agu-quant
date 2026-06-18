"""A股模拟交易 — 完整还原A股交易规则.

规则:
- T+1: 当日买入次日才能卖出
- 涨跌停: 主板±10%, 科创/创业±20%, ST±5%
- 交易时间: 9:30-11:30, 13:00-15:00
- 手数: 主板100股, 科创/创业板200股
- 费用: 印花税0.05%(单边卖), 佣金0.025%(最低5元), 过户费0.001%
- 停牌/退市: 标记不可交易状态
"""

from __future__ import annotations

import json, os, re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Optional


# ── A-Share Constants ────────────────────────────────────────────────────────────

MARKET_OPEN = time(9, 30)
MARKET_CLOSE_AM = time(11, 30)
MARKET_OPEN_PM = time(13, 0)
MARKET_CLOSE = time(15, 0)
STAMP_DUTY = 0.0005       # 印花税 0.05% (仅卖出)
COMMISSION_RATE = 0.00025 # 佣金 0.025%
COMMISSION_MIN = 5.0      # 最低佣金 5元
TRANSFER_FEE = 0.00001    # 过户费 0.001%


def is_trading_time() -> bool:
    """Check if now is within A-share trading hours on a trading day."""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (MARKET_OPEN <= t <= MARKET_CLOSE_AM) or (MARKET_OPEN_PM <= t <= MARKET_CLOSE)


def _get_board(code: str) -> str:
    """Determine board from stock code."""
    if code.startswith("68"):
        return "star"     # 科创板
    if code.startswith("30"):
        return "chinext"  # 创业板
    if code.startswith(("6", "9")):
        return "main_sh"  # 沪市主板
    return "main_sz"      # 深市主板


def _lot_size(code: str) -> int:
    """Minimum trading unit (股)."""
    return 200 if _get_board(code) in ("star", "chinext") else 100


def build_signal_order_plan(signal: dict, position: dict) -> dict:
    """Translate one deterministic holding signal into a proposed order."""
    action = str(signal.get("action") or "HOLD")
    code = str(position.get("code") or "")
    shares = max(0, int(position.get("shares", 0) or 0))
    sellable = max(0, min(shares, int(position.get("sellable", 0) or 0)))
    lot = _lot_size(code)

    if action in {"STOP_LOSS", "EXIT"}:
        if sellable <= 0:
            reason = "平仓信号已触发，但受T+1限制，当前无可卖股份"
        else:
            reason = "平仓信号：卖出全部可卖持仓"
        return {
            "kind": "clear",
            "action": "卖出",
            "shares": sellable,
            "enabled": sellable > 0,
            "reason": reason,
        }

    if action in {"TAKE_PROFIT", "REDUCE"}:
        target = (sellable // 2 // lot) * lot
        if target <= 0 and sellable > 0:
            target = sellable
        return {
            "kind": "reduce",
            "action": "卖出",
            "shares": target,
            "enabled": target > 0,
            "reason": "止盈/减仓信号：先卖出约一半可卖持仓" if target else "减仓信号已触发，但受T+1限制",
        }

    if action == "ADD":
        target = max(lot, (shares // 4 // lot) * lot)
        return {
            "kind": "add",
            "action": "买入",
            "shares": target,
            "enabled": True,
            "reason": "加仓信号：建议单次不超过当前持仓的25%",
        }

    return {
        "kind": "hold",
        "action": "",
        "shares": 0,
        "enabled": False,
        "reason": "当前策略信号为持有，不生成卖出、加仓或清仓委托",
    }


def _price_limit_pct(code: str, name: str = "") -> float:
    """Daily price limit percentage."""
    if "ST" in name.upper() or "*ST" in name.upper():
        return 0.05
    board = _get_board(code)
    return 0.20 if board in ("star", "chinext") else 0.10


def _calc_limit_prices(code: str, prev_close: float, name: str = "") -> tuple:
    """Return (limit_up, limit_down) for a stock."""
    pct = _price_limit_pct(code, name)
    limit_up = round(prev_close * (1 + pct), 2)
    limit_down = round(prev_close * (1 - pct), 2)
    return limit_up, limit_down


def _calc_fee(amount: float, is_sell: bool = False) -> float:
    """Calculate total transaction fee."""
    commission = max(COMMISSION_MIN, round(amount * COMMISSION_RATE, 2))
    stamp = round(amount * STAMP_DUTY, 2) if is_sell else 0
    transfer = round(amount * TRANSFER_FEE, 2)
    return commission + stamp + transfer


# ── Data Classes ─────────────────────────────────────────────────────────────────

@dataclass
class Position:
    code: str
    name: str = ""
    shares: int = 0
    buyable_shares: int = 0  # shares available to sell (T+1 settled)
    avg_cost: float = 0.0
    current_price: float = 0.0
    prev_close: float = 0.0
    buy_date: str = ""       # most recent buy date YYYY-MM-DD
    board: str = ""

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def pnl(self) -> float:
        return (self.current_price - self.avg_cost) * self.shares

    @property
    def pnl_pct(self) -> float:
        return (self.current_price / self.avg_cost - 1) * 100 if self.avg_cost > 0 else 0

    def to_dict(self) -> dict:
        return {
            "code": self.code, "name": self.name, "shares": self.shares,
            "buyable": self.buyable_shares, "avg_cost": self.avg_cost,
            "current_price": self.current_price, "prev_close": self.prev_close,
            "buy_date": self.buy_date, "board": self.board,
        }


@dataclass
class Order:
    id: str
    time: str
    code: str
    action: str  # BUY / SELL
    price: float
    shares: int
    amount: float
    fee: float
    status: str  # filled / rejected / pending_t1
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "time": self.time, "code": self.code,
            "action": self.action, "price": self.price, "shares": self.shares,
            "amount": self.amount, "fee": self.fee,
            "status": self.status, "reason": self.reason,
        }


# Allowed keys for backward-compatible deserialization
_POSITION_KEYS = {"code", "name", "shares", "buyable_shares", "avg_cost",
                   "current_price", "prev_close", "buy_date", "board"}
_ORDER_KEYS = {"id", "time", "code", "action", "price", "shares", "amount",
                "fee", "status", "reason"}


# ── Account ──────────────────────────────────────────────────────────────────────

class PaperAccount:
    """A股模拟交易账户."""

    def __init__(self, name: str = "default", initial_cash: float = 1_000_000):
        self.name = name
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self._order_id = 0
        self._data_dir = Path.home() / ".tradingagents" / "paper_trade"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._data_dir / f"{name}.json"

    def _next_id(self) -> str:
        self._order_id += 1
        return f"ORD{self._order_id:06d}"

    # ── Stock Info ───────────────────────────────────────────────────────────

    def _get_stock_info(self, code: str) -> dict:
        """Fetch stock info: name, prev_close, current price."""
        from tradingagents.dataflows.a_stock import _tencent_quote, _normalize_ticker
        code = _normalize_ticker(code)
        quotes = _tencent_quote([code])
        q = quotes.get(code, {})
        return {
            "code": code,
            "name": q.get("name", code),
            "price": q.get("price", 0),
            "prev_close": q.get("last_close", 0),
            "limit_up": q.get("limit_up", 0),
            "limit_down": q.get("limit_down", 0),
        }

    # ── Buy ──────────────────────────────────────────────────────────────────

    def buy(self, code: str, shares: int = None, amount: float = None) -> Order:
        """买入股票，遵守A股规则."""
        info = self._get_stock_info(code)
        code = info["code"]
        name = info["name"]
        price = info["price"]
        prev_close = info["prev_close"]
        limit_up, limit_down = info["limit_up"], info["limit_down"]

        # 1. 检查交易时间
        if not is_trading_time():
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "BUY", price, 0, 0, 0, "rejected",
                         "非交易时间 (9:30-11:30, 13:00-15:00)")

        # 2. 检查价格有效性
        if price <= 0:
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "BUY", 0, 0, 0, 0, "rejected", "无法获取实时价格")
        if price >= limit_up:
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "BUY", price, 0, 0, 0, "rejected",
                         f"涨停({limit_up})，无法买入")

        # 3. 计算手数
        lot = _lot_size(code)
        if shares is None and amount is not None:
            shares = int(amount / price / lot) * lot
        if shares is None or shares < lot:
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "BUY", price, 0, 0, 0, "rejected",
                         f"最少买入{lot}股({_get_board(code)}板块)")

        # 4. 资金检查
        cost = price * shares
        fee = _calc_fee(cost, is_sell=False)
        total = cost + fee
        if total > self.cash:
            max_shares = int(self.cash / (price * (1 + COMMISSION_RATE + TRANSFER_FEE)) / lot) * lot
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "BUY", price, shares, cost, fee, "rejected",
                         f"资金不足: 需要{total:,.0f}元, 可用{self.cash:,.0f}元 (最多{max_shares}股)")

        # 5. 执行买入
        self.cash -= total
        today = datetime.now().strftime("%Y-%m-%d")

        if code in self.positions:
            pos = self.positions[code]
            if pos.buy_date == today:
                # Same day additional buy: these shares also locked until tomorrow
                new_total = pos.shares + shares
                pos.avg_cost = round(
                    (pos.shares * pos.avg_cost + cost) / new_total, 3
                )
                pos.shares = new_total
            else:
                # New buy on different day: previous shares unlocked, new shares locked
                new_total = pos.shares + shares
                pos.avg_cost = round(
                    (pos.shares * pos.avg_cost + cost) / new_total, 3
                )
                pos.shares = new_total
                pos.buyable_shares = pos.shares - shares  # old shares available
                pos.buy_date = today
        else:
            self.positions[code] = Position(
                code=code, name=name, shares=shares, buyable_shares=0,
                avg_cost=price, current_price=price, prev_close=prev_close,
                buy_date=today, board=_get_board(code),
            )

        order = Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                      code, "BUY", price, shares, cost, fee, "filled",
                      f"T+1: 明日({_next_trade_day()})起可卖出")
        self.orders.append(order)
        self._save()
        return order

    # ── Sell ─────────────────────────────────────────────────────────────────

    def sell(self, code: str, shares: int = None) -> Order:
        """卖出股票，遵守A股规则."""
        info = self._get_stock_info(code)
        code = info["code"]
        price = info["price"]
        prev_close = info["prev_close"]
        limit_up, limit_down = info["limit_up"], info["limit_down"]

        # 1. 检查持仓
        pos = self.positions.get(code)
        if not pos:
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "SELL", price, 0, 0, 0, "rejected", f"无{code}持仓")

        # 2. 检查交易时间
        if not is_trading_time():
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "SELL", price, 0, 0, 0, "rejected",
                         "非交易时间 (9:30-11:30, 13:00-15:00)")

        # 3. 价格有效性
        if price <= 0:
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "SELL", 0, 0, 0, 0, "rejected", "无法获取实时价格")
        if price <= limit_down:
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "SELL", price, 0, 0, 0, "rejected",
                         f"跌停({limit_down})，无法卖出")

        # 4. T+1 检查: 当日买入的不能卖出
        today = datetime.now().strftime("%Y-%m-%d")
        if pos.buy_date == today and pos.buyable_shares == 0:
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "SELL", price, 0, 0, 0, "rejected",
                         f"T+1限制: 今日买入的股票明日才能卖出 (买入日期:{pos.buy_date})")

        available = pos.buyable_shares if pos.buy_date == today else pos.shares
        if shares is None:
            shares = available
        if shares > available:
            return Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                         code, "SELL", price, shares, 0, 0, "rejected",
                         f"可卖数量不足: 持有{pos.shares}股, T+1可卖{available}股")

        # 5. 执行卖出
        revenue = price * shares
        fee = _calc_fee(revenue, is_sell=True)
        self.cash += revenue - fee

        pos.shares -= shares
        pos.buyable_shares = max(0, pos.buyable_shares - shares)
        if pos.shares == 0:
            del self.positions[code]
        else:
            pos.current_price = price

        order = Order(self._next_id(), datetime.now().strftime("%H:%M:%S"),
                      code, "SELL", price, shares, revenue, fee, "filled",
                      f"已卖出{shares}股, 费用{fee:.2f}元")
        self.orders.append(order)
        self._save()
        return order

    # ── Session Continuity ───────────────────────────────────────────────────

    def on_startup(self):
        """Call after load() or creation to reconcile state with current date."""
        self.refresh_prices()
        self._unlock_t1()
        self._take_snapshot()
        self._save()

    def _unlock_t1(self):
        """Unlock T+1 shares based on current date."""
        today = datetime.now().strftime("%Y-%m-%d")
        for pos in self.positions.values():
            if pos.buy_date and pos.buy_date != today:
                pos.buyable_shares = pos.shares

    def _take_snapshot(self):
        """Record daily equity snapshot for P&L history."""
        today = datetime.now().strftime("%Y-%m-%d")
        if not hasattr(self, "_snapshots"):
            self._snapshots: dict[str, float] = {}
        self._snapshots[today] = self.total_equity
        # Keep last 365 days
        if len(self._snapshots) > 365:
            oldest = sorted(self._snapshots.keys())[0]
            del self._snapshots[oldest]

    def get_snapshots(self) -> list[tuple[str, float]]:
        """Return sorted daily equity snapshots for charting."""
        if not hasattr(self, "_snapshots"):
            self._snapshots = {}
        return sorted(self._snapshots.items())

    # ── Update & Query ───────────────────────────────────────────────────────

    def refresh_prices(self):
        """从腾讯财经刷新所有持仓价格并解锁T+1."""
        codes = list(self.positions.keys())
        if not codes:
            return
        from tradingagents.dataflows.a_stock import _tencent_quote
        quotes = _tencent_quote(codes)
        today = datetime.now().strftime("%Y-%m-%d")
        for code, pos in self.positions.items():
            q = quotes.get(code, {})
            if q:
                pos.current_price = q.get("price", pos.current_price)
                pos.prev_close = q.get("last_close", pos.prev_close)
                pos.name = q.get("name", pos.name)
            if pos.buy_date and pos.buy_date != today and pos.buyable_shares < pos.shares:
                pos.buyable_shares = pos.shares
        self._take_snapshot()
        self._save()

    @property
    def total_market_value(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    @property
    def total_equity(self) -> float:
        return self.cash + self.total_market_value

    @property
    def total_pnl(self) -> float:
        return self.total_equity - self.initial_cash

    @property
    def total_return(self) -> float:
        return (self.total_equity / self.initial_cash - 1) * 100

    def summary(self) -> dict:
        pos_list = []
        for p in self.positions.values():
            sellable = p.buyable_shares if p.buy_date == datetime.now().strftime("%Y-%m-%d") else p.shares
            pos_list.append({
                "code": p.code, "name": p.name, "shares": p.shares,
                "sellable": sellable, "avg_cost": round(p.avg_cost, 2),
                "price": round(p.current_price, 2), "value": round(p.market_value, 2),
                "pnl": round(p.pnl, 2), "pnl_pct": round(p.pnl_pct, 2),
                "board": p.board, "buy_date": p.buy_date,
            })
        return {
            "cash": round(self.cash, 2),
            "market_value": round(self.total_market_value, 2),
            "total_equity": round(self.total_equity, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_return": round(self.total_return, 2),
            "positions": pos_list,
            "order_count": len(self.orders),
        }

    # ── Persistence ──────────────────────────────────────────────────────────

    def _save(self):
        data = {
            "name": self.name, "initial_cash": self.initial_cash,
            "cash": self.cash, "_order_id": self._order_id,
            "positions": {c: p.to_dict() for c, p in self.positions.items()},
            "orders": [o.to_dict() for o in self.orders[-200:]],
            "snapshots": getattr(self, "_snapshots", {}),
        }
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> bool:
        if not self._file.exists():
            return False
        with open(self._file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.initial_cash = data["initial_cash"]
        self.cash = data["cash"]
        self._order_id = data.get("_order_id", 0)
        self.positions = {}
        for c, pdict in data.get("positions", {}).items():
            # backward compat: old data may use different field names
            if "buyable" in pdict and "buyable_shares" not in pdict:
                pdict["buyable_shares"] = pdict.pop("buyable")
            # Remove unknown keys
            pdict = {k: v for k, v in pdict.items() if k in _POSITION_KEYS}
            self.positions[c] = Position(**pdict)
        self.orders = [Order(**{k: v for k, v in o.items() if k in _ORDER_KEYS})
                       for o in data.get("orders", [])]
        self._snapshots = data.get("snapshots", {})
        self.on_startup()
        return True

    def reset(self):
        self.cash = self.initial_cash
        self.positions.clear()
        self.orders.clear()
        self._order_id = 0
        if self._file.exists():
            self._file.unlink()


def _next_trade_day() -> str:
    """Return next trading day in YYYY-MM-DD."""
    d = datetime.now() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def get_account(name: str = "default") -> PaperAccount:
    acc = PaperAccount(name)
    if not acc.load():
        acc._save()
        acc._take_snapshot()
    return acc
