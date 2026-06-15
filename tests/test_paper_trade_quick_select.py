from __future__ import annotations

from tradingagents.ranking import recommendation_engine as rec


def test_paper_trade_quick_select_accepts_high_score_watch(monkeypatch):
    universe = [
        {
            "code": "AAA",
            "name": "强势低波",
            "price": 10,
            "change_pct": 1.2,
            "turnover": 4,
            "amount": 2e8,
            "pe": 12,
            "pb": 1.2,
            "roe": 15,
            "market_cap": 8e10,
            "main_force_net": 1e7,
        },
        {
            "code": "BBB",
            "name": "高风险",
            "price": 20,
            "change_pct": 2.0,
            "turnover": 5,
            "amount": 3e8,
            "pe": 18,
            "pb": 1.8,
            "roe": 12,
            "market_cap": 6e10,
            "main_force_net": 1e6,
        },
    ]

    def fake_signal(code, end_date, strategy_key="balanced", **kwargs):
        if code == "AAA":
            return {
                "action": "WATCH",
                "action_cn": "观察",
                "score": 68,
                "confidence": 75,
                "risk_level": "低",
                "levels": {"stop_loss": 9.2, "take_profit": 12.4, "add_price": 9.8},
                "reasons": ["信号分达标"],
                "risk_notes": [],
            }
        return {
            "action": "BUY",
            "action_cn": "买入",
            "score": 80,
            "confidence": 80,
            "risk_level": "高",
            "levels": {},
            "reasons": [],
            "risk_notes": ["风险过高"],
        }

    monkeypatch.setattr(rec, "get_liquid_universe", lambda universe_size: universe)
    monkeypatch.setattr(rec, "evaluate_code_signal", fake_signal)

    result = rec.run_paper_trade_quick_select(
        strategy_key="paper_signal_opt",
        universe_size=2,
        recommend_n=5,
        min_entry_score=65,
        entry_actions={"BUY", "WATCH"},
        end_date="2026-06-14",
    )

    assert result["strategy_key"] == "paper_signal_opt"
    assert [row["代码"] for row in result["recommendations"]] == ["AAA"]
    assert result["recommendations"][0]["动作Key"] == "WATCH"
