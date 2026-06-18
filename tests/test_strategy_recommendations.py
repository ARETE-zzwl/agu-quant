from __future__ import annotations

from tradingagents.ranking import recommendation_engine as rec


def _universe() -> list[dict]:
    return [
        {
            "code": "AAA",
            "name": "趋势样本",
            "price": 10,
            "change_pct": 2.0,
            "turnover": 5,
            "amount": 3e8,
            "pe": 16,
            "pb": 1.5,
            "roe": 14,
            "market_cap": 8e10,
            "main_force_net": 2e7,
        },
        {
            "code": "BBB",
            "name": "观察样本",
            "price": 12,
            "change_pct": -0.5,
            "turnover": 3,
            "amount": 2e8,
            "pe": 22,
            "pb": 2.1,
            "roe": 9,
            "market_cap": 5e10,
            "main_force_net": -1e6,
        },
    ]


def test_strategy_candidates_are_available_for_any_ranked_strategy(monkeypatch):
    def fake_signal(code, end_date, strategy_key="balanced", **kwargs):
        return {
            "action": "BUY" if code == "AAA" else "NEUTRAL",
            "action_cn": "买入" if code == "AAA" else "中性",
            "score": 78 if code == "AAA" else 52,
            "confidence": 80 if code == "AAA" else 55,
            "risk_level": "低" if code == "AAA" else "中",
            "levels": {"stop_loss": 9.2, "take_profit": 12.5, "add_price": 9.8},
            "technical": {},
            "reasons": ["测试信号"],
            "risk_notes": [],
        }

    monkeypatch.setattr(rec, "evaluate_code_signal", fake_signal)

    result = rec.recommend_strategy_candidates(
        _universe(),
        strategy_key="research_value_momentum",
        recommend_n=2,
        end_date="2026-06-18",
    )

    assert result["strategy"]["key"] == "research_value_momentum"
    assert len(result["candidates"]) == 2
    assert {row["代码"] for row in result["candidates"]} == {"AAA", "BBB"}
    assert result["candidates"][0]["入选状态"] in {"可执行", "观察", "仅排名"}


def test_strategy_rows_do_not_truncate_non_winners():
    ranked = [
        {
            "key": f"strategy_{i}",
            "label": f"策略{i}",
            "metrics": {
                "objective_score": 30 - i,
                "annual_return": 0.1,
                "sharpe_ratio": 1.0,
                "max_drawdown": -0.1,
                "win_rate": 0.55,
                "avg_turnover": 0.2,
            },
        }
        for i in range(18)
    ]

    rows = rec._strategy_rows(ranked)

    assert len(rows) == 18
    assert rows[-1]["排名"] == 18


def _mock_one_click_dependencies(monkeypatch):
    ranked = [
        {
            "key": f"s{i}",
            "label": f"策略{i}",
            "desc": "",
            "weights": {},
            "metrics": {
                "objective_score": 30 - i,
                "annual_return": 0.1,
                "sharpe_ratio": 1.0,
                "max_drawdown": 0.1,
                "win_rate": 0.55,
                "avg_turnover": 0.2,
            },
        }
        for i in range(4)
    ]
    monkeypatch.setattr(rec, "get_liquid_universe", lambda size: _universe() * 3)
    monkeypatch.setattr(rec, "compare_strategy_presets", lambda *args, **kwargs: {"ranked": ranked})
    calls = []

    def fake_recommend(universe, *, strategy_key, recommend_n, end_date):
        calls.append(strategy_key)
        rows = [_candidate for _candidate in [
            {
                "代码": "AAA",
                "名称": "共识样本",
                "动作Key": "BUY",
                "风险": "低",
                "综合分": 80,
                "现价": 10,
            }
        ]]
        return {
            "candidates": rows,
            "recommendations": rows,
            "strict_buy_count": 1,
            "watch_count": 0,
        }

    monkeypatch.setattr(rec, "recommend_strategy_candidates", fake_recommend)
    return calls


def test_one_click_keeps_original_best_strategy_path_by_default(monkeypatch):
    calls = _mock_one_click_dependencies(monkeypatch)

    result = rec.run_one_click_recommendation(universe_size=6, recommend_n=2, max_positions=10)

    assert "consensus_analysis" not in result
    assert calls == ["s0"]


def test_one_click_builds_consensus_only_when_explicitly_requested(monkeypatch):
    calls = _mock_one_click_dependencies(monkeypatch)

    result = rec.run_one_click_recommendation(
        universe_size=6,
        recommend_n=2,
        max_positions=2,
        include_consensus=True,
    )

    assert result["consensus_analysis"]["strategies_used"] == ["s0", "s1", "s2"]
    assert result["consensus_analysis"]["candidates"][0]["support_count"] == 3
    assert calls == ["s0", "s1", "s2"]
