"""Dedicated workflow for accounts that can hold only one or two stocks."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from tradingagents.ranking.small_account_strategy import run_small_account_strategy
from web.components.common import inject_css, require_premium_page


st.set_page_config(page_title="小资金策略", page_icon="🪙", layout="wide", initial_sidebar_state="collapsed")
inject_css()
require_premium_page("小资金策略")


def _paper_import_payload(result: dict) -> dict:
    plan_codes = {order["code"] for order in result.get("plan", {}).get("orders", [])}
    candidates = result.get("consensus_analysis", {}).get("candidates", [])
    recommendations = [
        row["source"] for row in candidates
        if row.get("code") in plan_codes and isinstance(row.get("source"), dict)
    ]
    return {
        "strategy_key": "small_capital_consensus",
        "strategy_label": "小资金多策略共识",
        "strategy_desc": "独立小资金策略生成；模拟仓仍会复核交易时段、价格、现金与整手规则。",
        "universe_size": result.get("universe_size", 0),
        "entry_actions": ["BUY", "WATCH"],
        "min_entry_score": 0,
        "recommendations": recommendations,
    }


st.markdown(
    '<div style="margin-bottom:1rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">🪙 小资金策略</span>'
    '<span style="color:#8f8a82;font-size:0.85rem;margin-left:0.8rem;">独立回测 · 1–2只持仓 · 整手资金计划</span></div>',
    unsafe_allow_html=True,
)
st.caption("本页是独立策略工作流，不修改 AI 荐股页的原有 10 只持仓回测口径。")

primary = st.columns([1.3, 1, 1, 1.1])
cash = primary[0].number_input(
    "可用资金（元）",
    min_value=5_000,
    max_value=5_000_000,
    value=50_000,
    step=5_000,
)
max_positions = primary[1].selectbox("最多持有", [1, 2], index=1, format_func=lambda count: f"{count} 只")
reserve_pct = primary[2].select_slider(
    "现金预留",
    options=[0, 5, 8, 10, 15, 20],
    value=8,
    format_func=lambda value: f"{value}%",
)
run_strategy = primary[3].button("运行小资金策略", type="primary", use_container_width=True)

with st.expander("研究参数", expanded=False):
    advanced = st.columns(3)
    universe_size = advanced[0].selectbox("股票池规模", [40, 60, 100], index=1)
    lookback_days = advanced[1].selectbox(
        "回测周期",
        [180, 365, 730],
        index=1,
        format_func=lambda days: f"近{days}天",
    )
    recommend_n = advanced[2].selectbox("共识候选", [5, 10], index=0, format_func=lambda count: f"Top {count}")

if run_strategy:
    with st.status("正在运行独立小资金策略...", expanded=True) as status:
        try:
            st.write("用 1–2 只持仓上限重新比较策略")
            st.write("聚合前三策略的当前候选与风险信号")
            st.write("按价格、整手、手续费和现金预留生成计划")
            result = run_small_account_strategy(
                cash=cash,
                max_positions=max_positions,
                reserve_ratio=reserve_pct / 100,
                universe_size=universe_size,
                recommend_n=recommend_n,
                lookback_days=lookback_days,
            )
            st.session_state["small_capital_result"] = result
            status.update(label="小资金策略计算完成", state="complete")
        except Exception as exc:
            status.update(label="小资金策略计算失败", state="error")
            st.error(f"计算失败：{exc}")

result = st.session_state.get("small_capital_result")
if result:
    plan = result["plan"]
    consensus = result.get("consensus_analysis", {})
    result_max_positions = result.get("settings", {}).get("max_positions", 2)
    tabs = st.tabs(["小资金策略结果", "策略依据", "风险口径"])

    with tabs[0]:
        metrics = st.columns(4)
        metrics[0].metric("可用资金", f"¥{plan['cash']:,.0f}")
        metrics[1].metric("计划投入", f"¥{plan['invested']:,.0f}")
        metrics[2].metric("剩余现金", f"¥{plan['remaining_cash']:,.0f}")
        metrics[3].metric("计划持仓", f"{len(plan['orders'])}/{result_max_positions} 只")

        if plan["orders"]:
            st.dataframe(
                pd.DataFrame([
                    {
                        "代码": order["code"],
                        "名称": order["name"],
                        "参考价": order["price"],
                        "整手": order["lot_size"],
                        "计划股数": order["shares"],
                        "预计成本": order["estimated_cost"],
                        "资金权重": f"{order['weight']:.1%}",
                        "信号": order["signal"],
                    }
                    for order in plan["orders"]
                ]),
                use_container_width=True,
                hide_index=True,
            )
            payload = _paper_import_payload(result)
            if st.button("加入模拟仓候选", type="primary", disabled=not payload["recommendations"]):
                st.session_state["paper_import_candidates"] = payload
                st.session_state["small_account_plan"] = plan
                st.switch_page("pages/7_Paper_Trade.py")
        else:
            st.info("没有候选同时满足共识、风险和一手可买条件。保持现金也是策略结果。")

    with tabs[1]:
        st.markdown(f"**参与共识：** {' · '.join(consensus.get('strategy_labels', [])) or '暂无'}")
        st.caption("覆盖策略数占共识分 60%，各策略内部名次占 40%；只接受买入/观察且非高风险信号。")
        candidate_rows = consensus.get("candidates", [])
        if candidate_rows:
            st.dataframe(
                pd.DataFrame([
                    {
                        "代码": row["code"],
                        "名称": row["name"],
                        "共识分": row["consensus_score"],
                        "支持数": row["support_count"],
                        "支持策略": "、".join(row["strategy_labels"]),
                        "风险": row["risk"],
                    }
                    for row in candidate_rows
                ]),
                use_container_width=True,
                hide_index=True,
            )

    with tabs[2]:
        st.warning("1–2 只持仓会放大个股风险和短窗口年化数字，不应把回测年化当作收益预期。")
        st.markdown(
            "- 科创板按最低 200 股评估，其他当前支持板块按 100 股评估。\n"
            "- 计划保留所选现金比例，并估算最低佣金和过户费。\n"
            "- 共识为空、价格过高或不足一手时不会强行推荐。\n"
            "- 模拟成交继续受 T+1、交易时段、涨跌停和实时可用现金约束。"
        )

st.markdown("---")
st.caption("小资金策略仅用于研究与模拟验证，不构成投资建议。")
