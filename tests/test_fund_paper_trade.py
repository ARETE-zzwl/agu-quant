from __future__ import annotations

from tradingagents.fund_paper_trade import FundPaperAccount, evaluate_allocation


def test_fund_account_subscribe_and_redeem_updates_cash_and_position(tmp_path):
    acc = FundPaperAccount("pytest", data_dir=tmp_path, initial_cash=10_000)

    order = acc.subscribe(
        code="110011",
        name="易方达优质精选混合",
        amount=1_000,
        nav=1.0,
        fund_type="混合型",
        fee_rate=0.001,
    )

    assert order.status == "filled"
    assert acc.cash == 9_000
    assert acc.positions["110011"].units == 999.0
    assert acc.positions["110011"].avg_cost == 1.0

    redeem = acc.redeem("110011", units=400, nav=1.1, fee_rate=0.002)

    assert redeem.status == "filled"
    assert acc.positions["110011"].units == 599.0
    assert acc.cash == 9_000 + 440 - 0.88


def test_fund_account_rejects_oversized_redeem(tmp_path):
    acc = FundPaperAccount("pytest", data_dir=tmp_path, initial_cash=10_000)
    acc.subscribe("510300", "沪深300ETF", amount=1_000, nav=2.0, fund_type="场内 ETF/LOF")

    order = acc.redeem("510300", units=1_000, nav=2.0)

    assert order.status == "rejected"
    assert "持仓不足" in order.reason


def test_evaluate_allocation_reports_weight_and_role_warnings():
    report = evaluate_allocation(
        [
            {"代码": "110011", "名称": "成长混合", "类型": "混合型", "定位": "进攻", "目标权重%": 70},
            {"代码": "510300", "名称": "沪深300ETF", "类型": "场内 ETF/LOF", "定位": "核心", "目标权重%": 45},
        ]
    )

    assert report["total_weight"] == 115
    assert report["role_weights"]["进攻"] == 70
    assert any("超过100%" in warning for warning in report["warnings"])
