"""Cash-aware A-share order planning for concentrated small accounts."""

from __future__ import annotations

from typing import Any


def lot_size_for(code: str) -> int:
    """Return the minimum buy unit used by the planner.

    STAR Market orders start at 200 shares. Other supported A-share boards use
    100 shares for the small-account affordability check.
    """
    return 200 if str(code).startswith("68") else 100


def _buy_cost(price: float, shares: int) -> float:
    amount = price * shares
    commission = max(5.0, round(amount * 0.00025, 2))
    transfer_fee = round(amount * 0.00001, 2)
    return round(amount + commission + transfer_fee, 2)


def _first(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _normalize_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": str(_first(row, "code", "代码", default="")),
        "name": str(_first(row, "name", "名称", default="")),
        "price": float(_first(row, "price", "现价", default=0) or 0),
        "score": float(_first(row, "score", "综合分", "_final_score", "_score", default=0) or 0),
        "action": str(_first(row, "action", "动作Key", default="BUY") or "BUY").upper(),
        "risk": str(_first(row, "risk", "风险", default="未知") or "未知"),
        "source": row,
    }


def build_small_account_plan(
    candidates: list[dict[str, Any]],
    *,
    cash: float,
    max_positions: int = 2,
    reserve_ratio: float = 0.08,
) -> dict[str, Any]:
    """Build a buy plan that obeys cash, lot and entry-signal constraints."""
    cash = max(0.0, float(cash))
    max_positions = max(1, int(max_positions))
    reserve_ratio = min(0.9, max(0.0, float(reserve_ratio)))
    budget = round(cash * (1 - reserve_ratio), 2)
    available = budget
    skipped: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []

    normalized = sorted(
        (_normalize_candidate(row) for row in candidates),
        key=lambda row: row["score"],
        reverse=True,
    )
    for row in normalized:
        reason = ""
        if not row["code"] or row["price"] <= 0:
            reason = "价格或代码无效"
        elif row["risk"] == "高":
            reason = "高风险信号已排除"
        elif row["action"] not in {"BUY", "WATCH", "买入", "观察"}:
            reason = "当前信号不可买入"
        elif len(selected) >= max_positions:
            reason = "已达到持仓数量上限"
        else:
            lot = lot_size_for(row["code"])
            minimum_cost = _buy_cost(row["price"], lot)
            if minimum_cost > available:
                reason = "资金不足一手"
            else:
                selected.append({**row, "lot_size": lot, "shares": lot})
                available = round(available - minimum_cost, 2)
        if reason:
            skipped.append({"code": row["code"], "name": row["name"], "reason": reason})

    def total_cost() -> float:
        return round(sum(_buy_cost(row["price"], row["shares"]) for row in selected), 2)

    # Give each selected position an equal share of the budget left after its
    # first lot. This avoids an iteration per lot for larger accounts.
    minimum_total = total_cost()
    extra_per_position = (budget - minimum_total) / len(selected) if selected else 0
    for row in selected:
        lot_value = row["price"] * row["lot_size"]
        extra_lots = max(0, int(extra_per_position // lot_value))
        if extra_lots:
            base_cost = _buy_cost(row["price"], row["shares"])
            proposed_shares = row["shares"] + extra_lots * row["lot_size"]
            while proposed_shares > row["shares"]:
                extra_cost = _buy_cost(row["price"], proposed_shares) - base_cost
                if extra_cost <= extra_per_position:
                    break
                proposed_shares -= row["lot_size"]
            row["shares"] = proposed_shares

    # Spend the small rounding remainder one lot at a time, prioritizing the
    # least-funded position. The equal-slice step keeps this loop bounded.
    while selected:
        current_total = total_cost()
        choices = sorted(selected, key=lambda row: (row["price"] * row["shares"], -row["score"]))
        added = False
        for row in choices:
            next_cost = _buy_cost(row["price"], row["shares"] + row["lot_size"])
            current_cost = _buy_cost(row["price"], row["shares"])
            if current_total + next_cost - current_cost <= budget:
                row["shares"] += row["lot_size"]
                added = True
                break
        if not added:
            break

    invested = total_cost()
    orders = []
    for row in selected:
        estimated_cost = _buy_cost(row["price"], row["shares"])
        orders.append(
            {
                "code": row["code"],
                "name": row["name"],
                "price": row["price"],
                "lot_size": row["lot_size"],
                "shares": row["shares"],
                "estimated_cost": estimated_cost,
                "weight": round(estimated_cost / invested, 4) if invested else 0,
                "score": row["score"],
                "signal": row["action"],
            }
        )

    return {
        "cash": round(cash, 2),
        "budget": budget,
        "target_reserve": round(cash - budget, 2),
        "invested": invested,
        "remaining_cash": round(cash - invested, 2),
        "orders": orders,
        "skipped": skipped,
    }
