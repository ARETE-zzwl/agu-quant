"""One-click current stock recommendation pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .scoring_engine import ScoringEngine
from .signal_engine import evaluate_code_signal
from .strategy_ensemble import build_strategy_consensus
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


def run_paper_trade_quick_select(
    *,
    strategy_key: str = "paper_signal_opt",
    universe_size: int = 60,
    recommend_n: int = 8,
    min_entry_score: float | None = None,
    entry_actions: set[str] | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Fast one-click stock selection for the paper-trade page.

    Unlike run_one_click_recommendation, this does not re-backtest all strategy
    presets. It applies the selected strategy to a liquid universe, then confirms
    candidates with the same signal engine used by paper-trade positions.
    """
    end_date = end_date or datetime.now().strftime("%Y-%m-%d")
    catalog = ScoringEngine.get_strategies()
    cfg = catalog.get(strategy_key, catalog.get("paper_signal_opt", catalog["balanced"]))
    strategy_key = strategy_key if strategy_key in catalog else "paper_signal_opt"
    min_entry_score = float(min_entry_score if min_entry_score is not None else cfg.get("paper_min_entry_score", 75))
    entry_actions = entry_actions or set(cfg.get("paper_entry_actions", ["BUY"]))

    universe = get_liquid_universe(universe_size)
    if len(universe) < 2:
        raise ValueError("当前可用股票池不足，无法一键选股")

    engine = ScoringEngine(strategy=strategy_key)
    scored = engine.score_all([dict(s) for s in universe])
    current_candidates = scored[: min(len(scored), max(recommend_n * 5, 25))]
    action_bonus = {"BUY": 12, "WATCH": 4, "NEUTRAL": -2, "AVOID": -20}
    rows: list[dict[str, Any]] = []

    for stock in current_candidates:
        signal = evaluate_code_signal(
            stock["code"],
            end_date,
            strategy_key=strategy_key,
            quote=stock,
            cross_score=stock.get("_score", 50),
        )
        action = signal.get("action", "NEUTRAL")
        risk = signal.get("risk_level", "未知")
        levels = signal.get("levels", {})
        final_score = round(
            stock.get("_score", 0) * 0.50
            + signal.get("score", 50) * 0.50
            + action_bonus.get(action, 0),
            1,
        )
        row = {
            "代码": stock["code"],
            "名称": stock.get("name", ""),
            "操作": signal.get("action_cn", "中性"),
            "动作Key": action,
            "综合分": final_score,
            "选股分": stock.get("_score", 0),
            "信号分": signal.get("score", 0),
            "置信度": signal.get("confidence", 0),
            "风险": risk,
            "现价": stock.get("price", 0),
            "涨跌幅%": stock.get("change_pct", 0),
            "换手%": stock.get("turnover", 0),
            "PE": stock.get("pe", 0),
            "PB": stock.get("pb", 0),
            "止损": levels.get("stop_loss", ""),
            "止盈": levels.get("take_profit", ""),
            "补仓观察": levels.get("add_price", ""),
            "理由": "；".join(signal.get("reasons", [])[:3]),
            "风险提示": "；".join(signal.get("risk_notes", [])[:2]),
        }
        if (
            action in entry_actions
            and risk != "高"
            and signal.get("score", 0) >= min_entry_score
            and stock.get("change_pct", 0) < 8
        ):
            rows.append(row)

    rows.sort(key=lambda r: (r["综合分"], r["信号分"], r["置信度"]), reverse=True)
    return {
        "date": end_date,
        "strategy_key": strategy_key,
        "strategy_label": cfg.get("label", strategy_key),
        "strategy_desc": cfg.get("desc", ""),
        "universe_size": len(universe),
        "entry_actions": sorted(entry_actions),
        "min_entry_score": min_entry_score,
        "recommendations": rows[:recommend_n],
    }


def recommend_strategy_candidates(
    universe: list[dict],
    *,
    strategy_key: str,
    recommend_n: int = 10,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Rank the current candidates for any strategy in a backtest result.

    Candidates are always returned, even when their current signal is neutral.
    ``入选状态`` separates an executable signal from a research-only ranking so
    users can inspect non-winning strategies without silently loosening risk rules.
    """
    if len(universe) < 2:
        raise ValueError("当前可用股票池不足，无法生成策略选股结果")

    end_date = end_date or datetime.now().strftime("%Y-%m-%d")
    catalog = ScoringEngine.get_strategies()
    selected_key = strategy_key if strategy_key in catalog else "balanced"
    cfg = catalog[selected_key]
    scored = ScoringEngine(strategy=selected_key).score_all([dict(s) for s in universe])
    current_candidates = scored[: min(len(scored), max(recommend_n * 4, 20))]
    action_bonus = {"BUY": 12, "WATCH": 4, "NEUTRAL": -2, "AVOID": -20}
    rows: list[dict[str, Any]] = []

    for stock in current_candidates:
        signal = evaluate_code_signal(
            stock["code"],
            end_date,
            strategy_key=selected_key,
            quote=stock,
            cross_score=stock.get("_score", 50),
        )
        levels = signal.get("levels", {})
        tech = signal.get("technical", {})
        action_key = signal.get("action", "NEUTRAL")
        action_cn = signal.get("action_cn", "中性")
        risk = signal.get("risk_level", "未知")
        final_score = round(
            stock.get("_score", 0) * 0.55
            + signal.get("score", 50) * 0.45
            + action_bonus.get(action_key, 0),
            1,
        )
        risk_notes = "；".join(signal.get("risk_notes", [])[:2])
        if stock.get("change_pct", 0) > 7 and action_key == "BUY":
            action_key = "WATCH"
            action_cn = "观察"
            risk_notes = ((risk_notes + "；") if risk_notes else "") + "日内涨幅较大，避免追高"

        if action_key == "BUY" and risk != "高" and final_score >= 68:
            selection_status = "可执行"
        elif action_key in {"BUY", "WATCH"} and risk != "高" and final_score >= 58:
            selection_status = "观察"
        else:
            selection_status = "仅排名"

        rows.append(
            {
                "代码": stock["code"],
                "名称": stock.get("name", ""),
                "操作": action_cn,
                "动作Key": action_key,
                "入选状态": selection_status,
                "综合分": final_score,
                "选股分": stock.get("_score", 0),
                "信号分": signal.get("score", 0),
                "置信度": signal.get("confidence", 0),
                "风险": risk,
                "现价": stock.get("price", tech.get("price", 0)),
                "涨跌幅%": stock.get("change_pct", 0),
                "换手%": stock.get("turnover", 0),
                "PE": stock.get("pe", 0),
                "PB": stock.get("pb", 0),
                "止损": levels.get("stop_loss", ""),
                "止盈": levels.get("take_profit", ""),
                "补仓观察": levels.get("add_price", ""),
                "理由": "；".join(signal.get("reasons", [])[:2]),
                "风险提示": risk_notes,
            }
        )

    rows.sort(key=lambda row: (row["综合分"], row["信号分"]), reverse=True)
    candidates = rows[:recommend_n]
    return {
        "date": end_date,
        "strategy": {
            "key": selected_key,
            "label": cfg.get("label", selected_key),
            "desc": cfg.get("desc", ""),
        },
        "candidates": candidates,
        "recommendations": [row for row in candidates if row["入选状态"] != "仅排名"],
        "strict_buy_count": sum(row["入选状态"] == "可执行" for row in rows),
        "watch_count": sum(row["入选状态"] == "观察" for row in rows),
    }


def run_one_click_recommendation(
    *,
    universe_size: int = 60,
    recommend_n: int = 10,
    lookback_days: int = 180,
    top_pct: float = 0.2,
    rebalance_days: int = 10,
    max_positions: int = 10,
    include_consensus: bool = False,
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
    selection = recommend_strategy_candidates(
        universe,
        strategy_key=best["key"],
        recommend_n=recommend_n,
        end_date=end_date,
    )
    result = {
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
        "strategy_rows": _strategy_rows(ranked_strategies),
        "universe": universe,
        "recommendations": selection["recommendations"],
        "strategy_candidates": selection["candidates"],
        "strict_buy_count": selection["strict_buy_count"],
        "watch_count": selection["watch_count"],
    }
    if include_consensus:
        consensus_inputs = []
        for strategy in ranked_strategies[:3]:
            strategy_selection = selection
            if strategy["key"] != best["key"]:
                strategy_selection = recommend_strategy_candidates(
                    universe,
                    strategy_key=strategy["key"],
                    recommend_n=recommend_n,
                    end_date=end_date,
                )
            consensus_inputs.append(
                {
                    "key": strategy["key"],
                    "label": strategy["label"],
                    "objective_score": strategy["metrics"]["objective_score"],
                    "candidates": strategy_selection["candidates"],
                }
            )
        result["consensus_analysis"] = build_strategy_consensus(
            consensus_inputs,
            max_strategies=3,
            max_candidates=recommend_n,
        )
    return result
