from tradingagents.ranking.strategy_ensemble import build_strategy_consensus


def _candidate(code: str, score: float, action: str = "BUY", risk: str = "低") -> dict:
    return {
        "代码": code,
        "名称": code,
        "综合分": score,
        "动作Key": action,
        "风险": risk,
        "现价": 10,
    }


def test_consensus_rewards_cross_strategy_support_over_single_strategy_rank():
    result = build_strategy_consensus(
        [
            {"key": "s1", "label": "策略一", "objective_score": 30, "candidates": [_candidate("ONLY", 99), _candidate("BOTH", 80)]},
            {"key": "s2", "label": "策略二", "objective_score": 20, "candidates": [_candidate("BOTH", 85), _candidate("OTHER", 70)]},
        ],
        max_strategies=2,
    )

    assert result["strategies_used"] == ["s1", "s2"]
    assert result["candidates"][0]["code"] == "BOTH"
    assert result["candidates"][0]["support_count"] == 2
    assert result["candidates"][0]["strategy_labels"] == ["策略一", "策略二"]


def test_consensus_filters_high_risk_and_non_entry_signals():
    result = build_strategy_consensus(
        [
            {
                "key": "s1",
                "label": "策略一",
                "objective_score": 10,
                "candidates": [
                    _candidate("GOOD", 80),
                    _candidate("RISK", 90, risk="高"),
                    _candidate("NEUTRAL", 95, action="NEUTRAL"),
                ],
            }
        ]
    )

    assert [row["code"] for row in result["candidates"]] == ["GOOD"]


def test_consensus_uses_only_requested_top_strategies():
    result = build_strategy_consensus(
        [
            {"key": "s1", "label": "一", "objective_score": 30, "candidates": [_candidate("A", 80)]},
            {"key": "s2", "label": "二", "objective_score": 20, "candidates": [_candidate("B", 80)]},
            {"key": "s3", "label": "三", "objective_score": 10, "candidates": [_candidate("C", 80)]},
        ],
        max_strategies=2,
    )

    assert result["strategies_used"] == ["s1", "s2"]
    assert "C" not in {row["code"] for row in result["candidates"]}
