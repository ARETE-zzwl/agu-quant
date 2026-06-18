from tradingagents.ranking.portfolio_advisor import build_portfolio_advice_prompt


def test_portfolio_advice_prompt_includes_positions_signals_factors_and_t1():
    summary = {
        "cash": 200_000,
        "market_value": 800_000,
        "total_equity": 1_000_000,
        "total_return": 3.5,
    }
    position = {
        "code": "600519",
        "name": "贵州茅台",
        "shares": 500,
        "sellable": 300,
        "avg_cost": 1500,
        "price": 1600,
        "pnl_pct": 6.67,
    }
    signal = {
        "action": "REDUCE",
        "action_cn": "减仓",
        "score": 48,
        "risk_level": "中",
        "technical": {"rsi": 72, "ma20": 1580, "ma60": 1510, "atr_pct": 3.2},
        "factor_summary": {"buy": 8, "sell": 13, "neutral": 4},
        "factor_rows": [
            {"name_cn": "RSI反转", "signal": "SELL", "weight": 0.31},
            {"name_cn": "价值质量", "signal": "BUY", "weight": 0.24},
        ],
        "levels": {"stop_loss": 1518, "take_profit": 1680, "add_price": 1570},
        "reasons": ["RSI偏高", "卖出因子占优"],
        "risk_notes": ["短期波动偏高"],
    }

    prompt = build_portfolio_advice_prompt(summary, [(position, signal)])

    assert "600519 贵州茅台" in prompt
    assert "减仓" in prompt
    assert "RSI=72" in prompt
    assert "买入8/卖出13/中性4" in prompt
    assert "RSI反转(SELL)" in prompt
    assert "可卖300股" in prompt
    assert "T+1" in prompt
    assert "确定性规则信号" in prompt
