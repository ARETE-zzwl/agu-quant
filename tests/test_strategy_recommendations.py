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
