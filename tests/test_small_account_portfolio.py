from tradingagents.ranking.small_account import build_small_account_plan, lot_size_for


def test_small_account_plan_respects_cash_lots_and_position_limit():
    candidates = [
        {"代码": "600001", "名称": "甲", "现价": 10.0, "综合分": 90, "动作Key": "BUY", "风险": "低"},
        {"代码": "000002", "名称": "乙", "现价": 20.0, "综合分": 80, "动作Key": "WATCH", "风险": "中"},
        {"代码": "600003", "名称": "丙", "现价": 5.0, "综合分": 70, "动作Key": "BUY", "风险": "低"},
    ]

    plan = build_small_account_plan(candidates, cash=12_000, max_positions=2, reserve_ratio=0.10)

    assert len(plan["orders"]) == 2
    assert [order["code"] for order in plan["orders"]] == ["600001", "000002"]
    assert all(order["shares"] % order["lot_size"] == 0 for order in plan["orders"])
    assert plan["invested"] <= 10_800
    assert plan["remaining_cash"] == round(12_000 - plan["invested"], 2)


def test_small_account_plan_skips_unaffordable_and_high_risk_candidates():
    candidates = [
        {"代码": "688001", "名称": "科创高价", "现价": 80.0, "综合分": 99, "动作Key": "BUY", "风险": "低"},
        {"代码": "600002", "名称": "高风险", "现价": 8.0, "综合分": 95, "动作Key": "BUY", "风险": "高"},
        {"代码": "300003", "名称": "创业样本", "现价": 30.0, "综合分": 80, "动作Key": "BUY", "风险": "低"},
    ]

    plan = build_small_account_plan(candidates, cash=10_000, max_positions=2, reserve_ratio=0)

    assert lot_size_for("688001") == 200
    assert lot_size_for("300003") == 100
    assert [order["code"] for order in plan["orders"]] == ["300003"]
    assert {row["code"] for row in plan["skipped"]} == {"688001", "600002"}


def test_small_account_plan_does_not_treat_neutral_rankings_as_orders():
    plan = build_small_account_plan(
        [{"代码": "600001", "现价": 10, "综合分": 90, "动作Key": "NEUTRAL", "风险": "低"}],
        cash=20_000,
        max_positions=1,
    )

    assert plan["orders"] == []
    assert plan["skipped"][0]["reason"] == "当前信号不可买入"
