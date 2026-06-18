"""Explainable rank consensus across independently backtested strategies."""

from __future__ import annotations

from typing import Any


def build_strategy_consensus(
    strategy_results: list[dict[str, Any]],
    *,
    max_strategies: int = 3,
    max_candidates: int = 10,
) -> dict[str, Any]:
    """Combine top-strategy candidate ranks without fitting another model."""
    ranked = sorted(
        strategy_results,
        key=lambda row: float(row.get("objective_score", 0) or 0),
        reverse=True,
    )[: max(1, int(max_strategies))]
    if not ranked:
        return {"strategies_used": [], "candidates": []}

    raw_weights = [1 / (index + 1) for index in range(len(ranked))]
    weight_total = sum(raw_weights)
    strategy_weights = [weight / weight_total for weight in raw_weights]
    aggregated: dict[str, dict[str, Any]] = {}

    for strategy, strategy_weight in zip(ranked, strategy_weights):
        candidates = strategy.get("candidates", [])
        count = max(len(candidates), 1)
        for index, candidate in enumerate(candidates):
            action = str(candidate.get("动作Key", candidate.get("action", ""))).upper()
            risk = str(candidate.get("风险", candidate.get("risk", "未知")))
            if action not in {"BUY", "WATCH", "买入", "观察"} or risk == "高":
                continue
            code = str(candidate.get("代码", candidate.get("code", "")))
            if not code:
                continue
            rank_score = (count - index) / count
            item = aggregated.setdefault(
                code,
                {
                    "code": code,
                    "name": candidate.get("名称", candidate.get("name", "")),
                    "rank_points": 0.0,
                    "strategy_labels": [],
                    "representative": candidate,
                    "representative_score": float(candidate.get("综合分", candidate.get("score", 0)) or 0),
                },
            )
            item["rank_points"] += strategy_weight * rank_score
            item["strategy_labels"].append(strategy.get("label", strategy.get("key", "")))
            candidate_score = float(candidate.get("综合分", candidate.get("score", 0)) or 0)
            if candidate_score > item["representative_score"]:
                item["representative"] = candidate
                item["representative_score"] = candidate_score

    candidates = []
    strategy_count = len(ranked)
    for item in aggregated.values():
        support_count = len(item["strategy_labels"])
        support_ratio = support_count / strategy_count
        consensus_score = round(support_ratio * 60 + item["rank_points"] * 40, 2)
        representative = item["representative"]
        candidates.append(
            {
                "code": item["code"],
                "name": item["name"],
                "consensus_score": consensus_score,
                "support_count": support_count,
                "strategy_labels": item["strategy_labels"],
                "price": float(representative.get("现价", representative.get("price", 0)) or 0),
                "score": item["representative_score"],
                "action": representative.get("动作Key", representative.get("action", "")),
                "risk": representative.get("风险", representative.get("risk", "未知")),
                "source": representative,
            }
        )

    candidates.sort(key=lambda row: (row["consensus_score"], row["score"]), reverse=True)
    return {
        "strategies_used": [str(row.get("key", "")) for row in ranked],
        "strategy_labels": [str(row.get("label", row.get("key", ""))) for row in ranked],
        "candidates": candidates[: max(1, int(max_candidates))],
    }
