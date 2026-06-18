"""LLM-assisted portfolio commentary grounded in deterministic signals."""

from __future__ import annotations

from typing import Any


def _fmt(value: Any, default: str = "—") -> str:
    return default if value is None or value == "" else str(value)


def build_portfolio_advice_prompt(summary: dict, signal_details: list[tuple[dict, dict]]) -> str:
    """Build a compact prompt containing account, factor, and technical evidence."""
    total_equity = float(summary.get("total_equity", 0) or 0)
    market_value = float(summary.get("market_value", 0) or 0)
    exposure = market_value / total_equity * 100 if total_equity > 0 else 0.0
    lines = [
        "你是A股模拟仓风控助手。请基于下列确定性规则信号生成持仓分析和操作建议。",
        "确定性规则信号、A股T+1和可卖数量优先于模型判断；不得改写信号，不得虚构行情或基本面。",
        (
            f"账户：总资产{total_equity:.2f}元，现金{float(summary.get('cash', 0) or 0):.2f}元，"
            f"持仓市值{market_value:.2f}元，仓位{exposure:.1f}%，"
            f"累计收益{float(summary.get('total_return', 0) or 0):+.2f}%"
        ),
        "持仓明细：",
    ]

    for position, signal in signal_details:
        tech = signal.get("technical", {})
        factors = signal.get("factor_summary", {})
        factor_rows = signal.get("factor_rows", [])[:6]
        key_factors = "、".join(
            f"{row.get('name_cn') or row.get('name', '未知因子')}({row.get('signal', 'NEUTRAL')})"
            for row in factor_rows
        ) or "无"
        levels = signal.get("levels", {})
        reasons = "；".join(signal.get("reasons", [])[:4]) or "无"
        risks = "；".join(signal.get("risk_notes", [])[:4]) or "无"
        lines.extend(
            [
                (
                    f"- {position.get('code', '')} {position.get('name', '')}："
                    f"持有{int(position.get('shares', 0) or 0)}股，可卖{int(position.get('sellable', 0) or 0)}股，"
                    f"成本{_fmt(position.get('avg_cost'))}，现价{_fmt(position.get('price'))}，"
                    f"盈亏{float(position.get('pnl_pct', 0) or 0):+.2f}%"
                ),
                (
                    f"  规则动作={signal.get('action_cn', '持有')}，信号分={_fmt(signal.get('score'))}，"
                    f"风险={_fmt(signal.get('risk_level'))}；"
                    f"RSI={_fmt(tech.get('rsi'))}，MA20={_fmt(tech.get('ma20'))}，"
                    f"MA60={_fmt(tech.get('ma60'))}，ATR%={_fmt(tech.get('atr_pct'))}"
                ),
                (
                    f"  因子票数=买入{int(factors.get('buy', 0) or 0)}/"
                    f"卖出{int(factors.get('sell', 0) or 0)}/中性{int(factors.get('neutral', 0) or 0)}；"
                    f"关键因子={key_factors}；"
                    f"止损={_fmt(levels.get('stop_loss'))}，止盈={_fmt(levels.get('take_profit'))}，"
                    f"加仓观察={_fmt(levels.get('add_price'))}"
                ),
                f"  依据={reasons}；风险提示={risks}",
            ]
        )

    lines.append(
        "请输出：1) 组合风险摘要；2) 每只持仓按规则动作给出执行顺序和数量原则；"
        "3) 明确哪些动作因T+1不可执行；4) 给出次日复核条件。使用简洁中文，不承诺收益。"
    )
    return "\n".join(lines)


def generate_portfolio_advice(
    summary: dict,
    signal_details: list[tuple[dict, dict]],
    *,
    provider: str,
    model: str,
) -> str:
    """Generate one grounded portfolio review with the configured LLM."""
    from langchain_core.messages import HumanMessage

    from tradingagents.llm_clients import create_llm_client

    prompt = build_portfolio_advice_prompt(summary, signal_details)
    llm = create_llm_client(provider=provider, model=model).get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    return str(response.content).strip()
