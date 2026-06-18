"""Persistent fund paper-trading account used by the Streamlit fund center."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from tradingagents.fund_center import normalize_fund_code


@dataclass
class FundPosition:
    code: str
    name: str
    fund_type: str
    units: float
    avg_cost: float
    latest_nav: float
    updated_at: str


@dataclass
class FundOrder:
    id: str
    time: str
    action: str
    code: str
    name: str
    fund_type: str
    nav: float
    units: float
    amount: float
    fee: float
    status: str
    reason: str = ""


class FundPaperAccount:
    def __init__(
        self,
        name: str = "default",
        *,
        data_dir: str | Path | None = None,
        initial_cash: float = 100_000.0,
    ) -> None:
        self.name = name
        self.initial_cash = float(initial_cash)
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".tradingagents" / "fund_paper"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.data_dir / f"{name}.json"
        self.cash = float(initial_cash)
        self.positions: dict[str, FundPosition] = {}
        self.orders: list[FundOrder] = []
        self.load()

    def load(self) -> None:
        if not self._file.exists():
            return
        data = json.loads(self._file.read_text(encoding="utf-8"))
        self.initial_cash = float(data.get("initial_cash", self.initial_cash))
        self.cash = float(data.get("cash", self.cash))
        self.positions = {
            code: FundPosition(**item)
            for code, item in (data.get("positions") or {}).items()
        }
        self.orders = [FundOrder(**item) for item in data.get("orders", [])]

    def save(self) -> None:
        payload = {
            "name": self.name,
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "positions": {code: asdict(pos) for code, pos in self.positions.items()},
            "orders": [asdict(order) for order in self.orders],
        }
        self._file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset(self) -> None:
        self.cash = self.initial_cash
        self.positions.clear()
        self.orders.clear()
        self.save()

    def mark_to_nav(self, code: str, nav: float) -> None:
        code = normalize_fund_code(code)
        if code in self.positions and nav > 0:
            self.positions[code].latest_nav = float(nav)
            self.positions[code].updated_at = datetime.now().isoformat(timespec="seconds")
            self.save()

    def subscribe(
        self,
        code: str,
        name: str,
        *,
        amount: float,
        nav: float,
        fund_type: str,
        fee_rate: float = 0.0015,
    ) -> FundOrder:
        code = normalize_fund_code(code)
        amount = float(amount)
        nav = float(nav)
        if amount <= 0 or nav <= 0:
            return self._record_order("SUBSCRIBE", code, name, fund_type, nav, 0.0, amount, 0.0, "rejected", "金额或净值无效")
        if amount > self.cash:
            return self._record_order("SUBSCRIBE", code, name, fund_type, nav, 0.0, amount, 0.0, "rejected", "现金不足")

        fee = round(amount * max(fee_rate, 0.0), 4)
        net_amount = amount - fee
        units = round(net_amount / nav, 4)
        self.cash = round(self.cash - amount, 4)
        old = self.positions.get(code)
        now = datetime.now().isoformat(timespec="seconds")
        if old:
            total_units = old.units + units
            avg_cost = ((old.units * old.avg_cost) + (units * nav)) / total_units if total_units else nav
            old.units = round(total_units, 4)
            old.avg_cost = round(avg_cost, 4)
            old.latest_nav = nav
            old.updated_at = now
            old.name = name or old.name
            old.fund_type = fund_type or old.fund_type
        else:
            self.positions[code] = FundPosition(code, name, fund_type, units, round(nav, 4), nav, now)
        return self._record_order("SUBSCRIBE", code, name, fund_type, nav, units, amount, fee, "filled", "申购成交，按当前净值估算份额")

    def redeem(
        self,
        code: str,
        *,
        units: float,
        nav: float,
        fee_rate: float = 0.005,
    ) -> FundOrder:
        code = normalize_fund_code(code)
        units = float(units)
        nav = float(nav)
        pos = self.positions.get(code)
        if not pos:
            return self._record_order("REDEEM", code, code, "", nav, units, 0.0, 0.0, "rejected", "无持仓")
        if units <= 0 or nav <= 0:
            return self._record_order("REDEEM", code, pos.name, pos.fund_type, nav, units, 0.0, 0.0, "rejected", "份额或净值无效")
        if units > pos.units:
            return self._record_order("REDEEM", code, pos.name, pos.fund_type, nav, units, 0.0, 0.0, "rejected", "持仓不足")

        gross = units * nav
        fee = round(gross * max(fee_rate, 0.0), 4)
        cash_in = round(gross - fee, 4)
        self.cash = round(self.cash + cash_in, 4)
        pos.units = round(pos.units - units, 4)
        pos.latest_nav = nav
        pos.updated_at = datetime.now().isoformat(timespec="seconds")
        if pos.units <= 0.0001:
            del self.positions[code]
        return self._record_order("REDEEM", code, pos.name, pos.fund_type, nav, units, gross, fee, "filled", "赎回成交，按当前净值估算到账")

    def buy_exchange(
        self,
        code: str,
        name: str,
        *,
        amount: float,
        price: float,
        fee_rate: float = 0.00015,
    ) -> FundOrder:
        return self.subscribe(code, name, amount=amount, nav=price, fund_type="场内 ETF/LOF", fee_rate=fee_rate)

    def sell_exchange(
        self,
        code: str,
        *,
        units: float,
        price: float,
        fee_rate: float = 0.00015,
    ) -> FundOrder:
        return self.redeem(code, units=units, nav=price, fee_rate=fee_rate)

    def _record_order(
        self,
        action: str,
        code: str,
        name: str,
        fund_type: str,
        nav: float,
        units: float,
        amount: float,
        fee: float,
        status: str,
        reason: str,
    ) -> FundOrder:
        order = FundOrder(
            id=datetime.now().strftime("%Y%m%d%H%M%S%f"),
            time=datetime.now().isoformat(timespec="seconds"),
            action=action,
            code=code,
            name=name,
            fund_type=fund_type,
            nav=round(float(nav or 0), 4),
            units=round(float(units or 0), 4),
            amount=round(float(amount or 0), 4),
            fee=round(float(fee or 0), 4),
            status=status,
            reason=reason,
        )
        self.orders.append(order)
        self.save()
        return order

    def summary(self) -> dict[str, Any]:
        position_rows = []
        market_value = 0.0
        cost_value = 0.0
        for pos in self.positions.values():
            value = pos.units * pos.latest_nav
            cost = pos.units * pos.avg_cost
            pnl = value - cost
            market_value += value
            cost_value += cost
            position_rows.append(
                {
                    "code": pos.code,
                    "name": pos.name,
                    "fund_type": pos.fund_type,
                    "units": round(pos.units, 4),
                    "avg_cost": round(pos.avg_cost, 4),
                    "latest_nav": round(pos.latest_nav, 4),
                    "value": round(value, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / cost * 100) if cost else 0.0, 2),
                    "updated_at": pos.updated_at,
                }
            )
        total_equity = self.cash + market_value
        return {
            "cash": round(self.cash, 2),
            "market_value": round(market_value, 2),
            "cost_value": round(cost_value, 2),
            "total_equity": round(total_equity, 2),
            "total_return": round((total_equity / self.initial_cash - 1) * 100, 2),
            "total_pnl": round(total_equity - self.initial_cash, 2),
            "positions": sorted(position_rows, key=lambda row: row["value"], reverse=True),
            "orders": self.orders,
        }


def get_fund_account(name: str = "default") -> FundPaperAccount:
    return FundPaperAccount(name)


def _row_value(row: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return default


def evaluate_allocation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cleaned = []
    role_weights: dict[str, float] = {}
    type_weights: dict[str, float] = {}
    warnings = []

    for row in rows:
        code = str(_row_value(row, "代码", "code")).strip()
        name = str(_row_value(row, "名称", "name", default=code)).strip()
        fund_type = str(_row_value(row, "类型", "fund_type", default="其他")).strip() or "其他"
        role = str(_row_value(row, "定位", "role", default="卫星")).strip() or "卫星"
        try:
            weight = float(_row_value(row, "目标权重%", "weight", default=0) or 0)
        except (TypeError, ValueError):
            weight = 0.0
        if weight <= 0:
            continue
        cleaned.append({"代码": code, "名称": name, "类型": fund_type, "定位": role, "目标权重%": weight})
        role_weights[role] = role_weights.get(role, 0.0) + weight
        type_weights[fund_type] = type_weights.get(fund_type, 0.0) + weight
        if weight > 45:
            warnings.append(f"{name or code} 单只权重超过45%，组合波动可能过于集中")

    total_weight = round(sum(row["目标权重%"] for row in cleaned), 2)
    if total_weight > 100:
        warnings.append(f"目标权重合计超过100%（当前{total_weight:.1f}%），需要压缩配置")
    if total_weight < 95:
        warnings.append(f"目标权重合计低于95%（当前{total_weight:.1f}%），现金仓位偏高")
    if cleaned and role_weights.get("核心", 0.0) < 30:
        warnings.append("核心仓位低于30%，组合可能缺少稳定底仓")

    return {
        "rows": cleaned,
        "total_weight": total_weight,
        "role_weights": {k: round(v, 2) for k, v in role_weights.items()},
        "type_weights": {k: round(v, 2) for k, v in type_weights.items()},
        "warnings": warnings,
    }
