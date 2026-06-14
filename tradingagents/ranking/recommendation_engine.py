"""One-click current stock recommendation pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .scoring_engine import ScoringEngine
from .signal_engine import evaluate_code_signal
from .strategy_optimizer import compare_strategy_presets


def get_liquid_universe(size: int = 60, market: str = "all") -> list[dict]:
    """Return a liquid A-share universe using current turnover amount ranking."""
    from tradingagents.dataflows.a_stock import screen_stocks

    stocks, _ = screen_stocks(
        market=market,
        sort_by="f6",
        sort_desc=True,
        page_size=max(20, min(size, 200)),
    )
    cleaned = []
    for s in stocks:
        name = str(s.get("name", ""))
        if "ST" in name.upper() or s.get("price", 0) <= 0:
            continue
        if s.get("amount", 0) <= 0:
            continue
        cleaned.append(s)
    return cleaned[:size]


def _strategy_rows(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for i, item in enumerate(ranked, start=1):
        m = item["metrics"]
        rows.append(
            {
                "排名": i,
                "策略": item["label"],
                "策略Key": item["key"],
                "目标分": round(m["objective_score"], 2),
                "年化%": round(m["annual_return"] * 100, 2),
                "夏普": round(m["sharpe_ratio"], 2),
                "回撤%": round(m["max_drawdown"] * 100, 2),
                "胜率%": round(m["win_rate"] * 100, 1),
                "换手": round(m["avg_turnover"], 3),
            }
        )
    return rows


def run_one_click_recommendation(
    *,
    universe_size: int = 60,
    recommend_n: int = 10,
    lookback_days: int = 180,
    top_pct: float = 0.2,
    rebalance_days: int = 10,
    max_positions: int = 10,
) -> dict[str, Any]:
    """Backtest strategies and recommend current candidates in one call."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    universe = get_liquid_universe(universe_size)
    if len(universe) < 5:
        raise ValueError("当前可用股票池不足，无法进行策略回测推荐")

    codes = [s["code"] for s in universe]
    comparison = compare_strategy_presets(
        codes,
        start_date,
        end_date,
        top_pct=top_pct,
        rebalance_days=rebalance_days,
        max_positions=max_positions,
    )
    ranked_strategies = comparison["ranked"]
    if not ranked_strategies:
        raise ValueError("策略回测没有可用结果")

    best = ranked_strategies[0]
    engine = ScoringEngine(strategy=best["key"])
    scored = engine.score_all([dict(s) for s in universe])

    current_candidates = scored[: min(len(scored), max(recommend_n * 4, 20))]
    action_bonus = {"BUY": 12, "WATCH": 4, "NEUTRAL": -2, "AVOID": -20}
    recommendations = []
    watchlist = []

    for stock in current_candidates:
        signal = evaluate_code_signal(
            stock["code"],
            end_date,
            strategy_key=best["key"],
            quote=stock,
            cross_score=stock.get("_score", 50),
        )
        levels = signal.get("levels", {})
        tech = signal.get("technical", {})
        final_score = round(
            stock.get("_score", 0) * 0.55
            + signal.get("score", 50) * 0.45
            + action_bonus.get(signal.get("action"), 0),
            1,
        )
        row = {
            "代码": stock["code"],
            "名称": stock.get("name", ""),
            "操作": signal.get("action_cn", "中性"),
            "动作Key": signal.get("action", "NEUTRAL"),
            "综合分": final_score,
            "选股分": stock.get("_score", 0),
            "信号分": signal.get("score", 0),
            "风险": signal.get("risk_level", "未知"),
            "现价": stock.get("price", tech.get("price", 0)),
            "涨跌幅%": stock.get("change_pct", 0),
            "PE": stock.get("pe", 0),
            "止损": levels.get("stop_loss", ""),
            "止盈": levels.get("take_profit", ""),
            "补仓观察": levels.get("add_price", ""),
            "理由": "；".join(signal.get("reasons", [])[:2]),
            "风险提示": "；".join(signal.get("risk_notes", [])[:2]),
        }
        action_key = signal.get("action")
        if stock.get("change_pct", 0) > 7 and action_key == "BUY":
            row["操作"] = "观察"
            row["动作Key"] = "WATCH"
            action_key = "WATCH"
            row["风险提示"] = (
                (row["风险提示"] + "；") if row["风险提示"] else ""
            ) + "日内涨幅较大，避免追高"

        if action_key == "BUY" and signal.get("risk_level") != "高" and final_score >= 68:
            recommendations.append(row)
        elif action_key in {"BUY", "WATCH"} and signal.get("risk_level") != "高" and final_score >= 58:
            watchlist.append(row)

    recommendations.sort(key=lambda r: r["综合分"], reverse=True)
    watchlist.sort(key=lambda r: r["综合分"], reverse=True)
    picks = (recommendations + [r for r in watchlist if r not in recommendations])[:recommend_n]

    return {
        "date": end_date,
        "start_date": start_date,
        "universe_size": len(universe),
        "notes": [
            "股票池按当前成交额选取，回测用于策略相对排序，存在当前样本偏差。",
            "短周期年化收益可能被放大，实盘应结合回撤、胜率、换手和止损执行。",
        ],
        "best_strategy": {
            "key": best["key"],
            "label": best["label"],
            "desc": best.get("desc", ""),
            "metrics": best["metrics"],
            "weights": best["weights"],
        },
        "strategy_rows": _strategy_rows(ranked_strategies[:12]),
        "recommendations": picks,
        "strict_buy_count": len(recommendations),
        "watch_count": len(watchlist),
    }
