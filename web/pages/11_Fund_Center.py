"""Fund Center — standalone fund research and paper-observation workspace."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from web.components.common import inject_css


st.set_page_config(page_title="基金中心", page_icon="💼", layout="wide", initial_sidebar_state="expanded")
inject_css()


st.markdown(
    '<div style="margin-bottom:0.5rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">💼 基金中心</span>'
    '<span style="color:#666;font-size:0.85rem;margin-left:0.8rem;">'
    '独立基金系统 · 净值分析 · 定投回测 · 基金模拟舱</span></div>',
    unsafe_allow_html=True,
)

st.caption("基金模块与股票 AI 荐股、股票监控、股票模拟盘分开建设；后续基金数据和基金交易规则只在本页闭环。")

top = st.columns(4)
top[0].metric("基金入口", "独立页面")
top[1].metric("数据源规划", "天天基金/东财")
top[2].metric("交易规则", "场内/场外分离")
top[3].metric("状态", "待接入数据")

tab_screen, tab_detail, tab_portfolio, tab_paper = st.tabs([
    "基金筛选", "基金详情", "基金组合", "基金模拟舱"
])

with tab_screen:
    st.markdown("### 基金筛选")
    c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
    query = c1.text_input("基金代码/名称", placeholder="例: 110011 或 易方达中小盘")
    fund_type = c2.selectbox("基金类型", ["全部", "股票型", "混合型", "债券型", "指数型", "ETF/LOF", "QDII", "货币型"])
    horizon = c3.selectbox("评价周期", ["近1月", "近3月", "近6月", "近1年", "近3年"], index=3)
    risk = c4.selectbox("风险偏好", ["稳健", "均衡", "进取"], index=1)

    b1, b2 = st.columns([1, 3])
    if b1.button("筛选基金", type="primary", width="stretch"):
        st.info("基金数据接口尚未接入；该入口已预留给基金筛选结果。")
    b2.caption(f"当前筛选条件：{query or '未输入'} · {fund_type} · {horizon} · {risk}")

    empty_rows = pd.DataFrame(
        columns=[
            "基金代码", "基金名称", "类型", "近1年收益", "最大回撤", "夏普", "同类排名", "操作",
        ]
    )
    st.dataframe(empty_rows, width="stretch", hide_index=True, height=220)

with tab_detail:
    st.markdown("### 基金详情")
    d1, d2, d3 = st.columns([1.2, 1, 1])
    fund_code = d1.text_input("基金代码", placeholder="例: 110011", key="fund_detail_code")
    d2.selectbox("净值周期", ["日净值", "周净值", "月净值"], index=0)
    d3.selectbox("对比基准", ["沪深300", "中证500", "中证偏股基金指数", "中证债券基金指数"])

    metrics = st.columns(5)
    for col, label in zip(metrics, ["单位净值", "累计净值", "近1年收益", "最大回撤", "夏普"]):
        col.metric(label, "—")
    if fund_code:
        st.info("下一步会在这里展示净值曲线、阶段收益、回撤、基金经理、规模费率和重仓持股。")
    else:
        st.caption("输入基金代码后展示基金净值和风险收益画像。")

with tab_portfolio:
    st.markdown("### 基金组合")
    st.caption("基金组合会独立于股票组合：用于基金配置比例、定投计划和组合风险暴露。")
    allocation = pd.DataFrame(
        [
            {"基金代码": "", "基金名称": "", "目标权重%": 0, "用途": "核心/卫星/防守"},
        ]
    )
    st.data_editor(allocation, width="stretch", hide_index=True, num_rows="dynamic")
    p1, p2, p3 = st.columns(3)
    p1.metric("组合数量", "0")
    p2.metric("目标仓位", "0%")
    p3.metric("定投计划", "未设置")

with tab_paper:
    st.markdown("### 基金模拟舱")
    st.caption("基金模拟舱会和股票模拟盘分开：场内ETF/LOF按交易价格，场外基金按净值申购/赎回和确认日建模。")
    rule_rows = pd.DataFrame(
        [
            {"基金类型": "场内 ETF/LOF", "交易价格": "实时/收盘价", "确认": "成交即持仓", "费用": "佣金/滑点"},
            {"基金类型": "场外开放式", "交易价格": "申购/赎回净值", "确认": "T+1/T+2", "费用": "申购费/赎回费"},
        ]
    )
    st.dataframe(rule_rows, width="stretch", hide_index=True)
    st.button("加入基金模拟舱", disabled=True, width="stretch")
