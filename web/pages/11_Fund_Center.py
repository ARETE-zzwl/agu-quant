"""Fund Center — standalone fund research and paper-observation workspace."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from web.components.common import inject_css


st.set_page_config(
    page_title="基金中心",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()


FUND_TYPES = ["全部", "股票型", "混合型", "债券型", "指数型", "ETF/LOF", "QDII", "货币型"]
HORIZONS = ["近1月", "近3月", "近6月", "近1年", "近3年"]
RISK_LEVELS = ["稳健", "均衡", "进取"]
BENCHMARKS = ["沪深300", "中证500", "中证偏股基金指数", "中证债券基金指数"]

STAGE_ROWS = pd.DataFrame(
    [
        {"模块": "基金筛选", "用户动作": "输入代码/名称、基金类型、周期、风险偏好", "当前状态": "前端就绪，等待基金数据源"},
        {"模块": "基金详情", "用户动作": "查看净值、回撤、经理、规模费率、重仓", "当前状态": "画像结构已预留"},
        {"模块": "基金组合", "用户动作": "配置核心/卫星/防守基金和目标权重", "当前状态": "组合录入已独立"},
        {"模块": "基金模拟舱", "用户动作": "按场内/场外规则模拟申购、赎回、持有", "当前状态": "交易规则已拆分"},
    ]
)

SCREEN_RESULT_COLUMNS = [
    "基金代码",
    "基金名称",
    "类型",
    "近1年收益",
    "近3年收益",
    "最大回撤",
    "夏普",
    "同类排名",
    "信号",
]

DETAIL_FIELDS = pd.DataFrame(
    [
        {"维度": "收益", "计划字段": "阶段收益、年化收益、超额收益", "用途": "判断中长期胜率"},
        {"维度": "风险", "计划字段": "最大回撤、波动率、下行波动、夏普", "用途": "约束回撤和持有体验"},
        {"维度": "持仓", "计划字段": "重仓股票、行业暴露、债券久期", "用途": "避免组合隐性集中"},
        {"维度": "交易", "计划字段": "申购费、赎回费、确认日、限购", "用途": "模拟舱真实扣费"},
    ]
)

ALLOCATION_TEMPLATE = pd.DataFrame(
    [
        {"基金代码": "", "基金名称": "", "目标权重%": 0, "角色": "核心", "再平衡频率": "月度"},
        {"基金代码": "", "基金名称": "", "目标权重%": 0, "角色": "卫星", "再平衡频率": "季度"},
    ]
)

PAPER_RULE_ROWS = pd.DataFrame(
    [
        {"基金类型": "场内 ETF/LOF", "价格口径": "实时/收盘价", "确认规则": "成交即持仓", "成本": "佣金、滑点", "模拟动作": "买入/卖出"},
        {"基金类型": "场外开放式", "价格口径": "申购/赎回净值", "确认规则": "T+1/T+2", "成本": "申购费、赎回费", "模拟动作": "申购/赎回"},
    ]
)


def _inject_fund_css() -> None:
    st.markdown(
        """
        <style>
        .fund-hero {
            border: 1px solid #262626;
            border-radius: 8px;
            padding: 1rem 1.1rem;
            margin: 0 0 0.85rem;
            background:
                linear-gradient(135deg, rgba(30, 34, 31, 0.96), rgba(12, 12, 12, 0.98)),
                radial-gradient(circle at top right, rgba(214, 168, 90, 0.16), transparent 36%);
        }
        .fund-hero-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.8fr);
            gap: 0.9rem;
            align-items: end;
        }
        .fund-kicker {
            color: #d6a85a;
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.06em;
        }
        .fund-title {
            margin: 0.16rem 0 0.2rem;
            color: #f5f1eb;
            font-size: 1.55rem;
            font-weight: 800;
            line-height: 1.2;
        }
        .fund-copy {
            color: #a7a7a7;
            font-size: 0.88rem;
            line-height: 1.6;
        }
        .fund-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            justify-content: flex-end;
        }
        .fund-pill {
            border: 1px solid #3a3327;
            border-radius: 999px;
            padding: 0.26rem 0.6rem;
            background: rgba(214, 168, 90, 0.08);
            color: #dbc28d;
            font-size: 0.78rem;
            white-space: nowrap;
        }
        .fund-status {
            border: 1px solid #242424;
            border-radius: 8px;
            padding: 0.72rem 0.85rem;
            min-height: 6rem;
            background: #141414;
        }
        .fund-status-label {
            color: #8d8d8d;
            font-size: 0.72rem;
            margin-bottom: 0.3rem;
        }
        .fund-status-value {
            color: #f5f1eb;
            font-size: 1.06rem;
            font-weight: 750;
            line-height: 1.35;
        }
        .fund-status-note {
            color: #858585;
            font-size: 0.76rem;
            margin-top: 0.35rem;
            line-height: 1.45;
        }
        .fund-section-note {
            border-left: 3px solid #d6a85a;
            padding: 0.5rem 0.72rem;
            margin: 0.5rem 0 0.9rem;
            background: rgba(214, 168, 90, 0.06);
            color: #c7c7c7;
            font-size: 0.84rem;
            line-height: 1.55;
        }
        .fund-empty {
            border: 1px dashed #343434;
            border-radius: 8px;
            padding: 1rem;
            background: #111;
            color: #a8a8a8;
            min-height: 10rem;
        }
        .fund-empty-title {
            color: #f5f1eb;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }
        .fund-empty-list {
            margin: 0.55rem 0 0;
            padding-left: 1rem;
        }
        .fund-empty-list li {
            margin: 0.22rem 0;
        }
        .fund-rule {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.8rem;
            margin: 0.7rem 0 0.35rem;
        }
        .fund-rule-item {
            border: 1px solid #242424;
            border-radius: 8px;
            padding: 0.8rem;
            background: #141414;
        }
        .fund-rule-title {
            color: #f5f1eb;
            font-weight: 750;
            margin-bottom: 0.35rem;
        }
        .fund-rule-copy {
            color: #949494;
            font-size: 0.82rem;
            line-height: 1.55;
        }
        @media (max-width: 860px) {
            .fund-hero-grid,
            .fund-rule {
                grid-template-columns: 1fr;
            }
            .fund-pill-row {
                justify-content: flex-start;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _status_tile(label: str, value: str, note: str) -> None:
    st.markdown(
        f"""
        <div class="fund-status">
            <div class="fund-status-label">{label}</div>
            <div class="fund-status-value">{value}</div>
            <div class="fund-status-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _empty_state(title: str, body: str, items: list[str]) -> None:
    item_html = "".join(f"<li>{item}</li>" for item in items)
    st.markdown(
        f"""
        <div class="fund-empty">
            <div class="fund-empty-title">{title}</div>
            <div>{body}</div>
            <ul class="fund-empty-list">{item_html}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


_inject_fund_css()

st.markdown(
    """
    <section class="fund-hero">
        <div class="fund-hero-grid">
            <div>
                <div class="fund-kicker">FUND RESEARCH CONSOLE</div>
                <div class="fund-title">💼 基金中心</div>
                <div class="fund-copy">
                    独立基金系统 · 净值分析 · 定投回测 · 基金模拟舱。基金模块与股票 AI 荐股、股票监控、
                    股票模拟盘分开建设，后续基金数据、组合和交易规则只在本页闭环。
                </div>
            </div>
            <div class="fund-pill-row">
                <span class="fund-pill">场内 ETF/LOF</span>
                <span class="fund-pill">场外开放式</span>
                <span class="fund-pill">定投计划</span>
                <span class="fund-pill">组合再平衡</span>
            </div>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

status_cols = st.columns(4)
with status_cols[0]:
    _status_tile("基金入口", "独立页面", "与股票工具区分导航、独立数据域。")
with status_cols[1]:
    _status_tile("数据源规划", "天天基金 / 东方财富", "优先净值、费率、规模、持仓和同类排名。")
with status_cols[2]:
    _status_tile("模拟规则", "场内 / 场外分离", "ETF/LOF 按成交价，场外按净值确认日。")
with status_cols[3]:
    _status_tile("当前状态", "前端工作台就绪", "真实基金数据接入后即可填充结果。")

st.dataframe(STAGE_ROWS, width="stretch", hide_index=True, height=180)

tab_screen, tab_detail, tab_portfolio, tab_paper = st.tabs(
    ["基金筛选", "基金详情", "基金组合", "基金模拟舱"]
)

with tab_screen:
    st.markdown("### 基金筛选")
    st.markdown(
        '<div class="fund-section-note">筛选区保留傻瓜式入口：用户只需要输入基金代码或名称，再选择类型、周期和风险偏好。数据接入后，这里会输出可加入基金模拟舱的候选清单。</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns([1.45, 1, 1, 1])
    query = c1.text_input("基金代码/名称", placeholder="例: 110011 或 易方达蓝筹精选")
    fund_type = c2.selectbox("基金类型", FUND_TYPES)
    horizon = c3.selectbox("评价周期", HORIZONS, index=3)
    risk = c4.selectbox("风险偏好", RISK_LEVELS, index=1)

    b1, b2 = st.columns([1, 3])
    if b1.button("一键筛选基金", type="primary", width="stretch"):
        st.info("基金数据接口尚未接入；该入口已预留给基金筛选结果。")
    b2.caption(f"当前筛选条件：{query or '未输入'} · {fund_type} · {horizon} · {risk}")

    st.dataframe(
        pd.DataFrame(columns=SCREEN_RESULT_COLUMNS),
        width="stretch",
        hide_index=True,
        height=240,
    )

with tab_detail:
    st.markdown("### 基金详情")
    st.markdown(
        '<div class="fund-section-note">详情页面会承接筛选结果，专门展示单只基金画像，不和股票深度分析页面混在一起。</div>',
        unsafe_allow_html=True,
    )
    d1, d2, d3 = st.columns([1.2, 1, 1])
    fund_code = d1.text_input("基金代码", placeholder="例: 110011", key="fund_detail_code")
    d2.selectbox("净值周期", ["日净值", "周净值", "月净值"], index=0)
    d3.selectbox("对比基准", BENCHMARKS)

    metrics = st.columns(5)
    for col, label in zip(metrics, ["单位净值", "累计净值", "近1年收益", "最大回撤", "夏普"]):
        col.metric(label, "—")

    left, right = st.columns([1.05, 1])
    with left:
        if fund_code:
            _empty_state(
                "等待基金数据",
                "下一步会在这里展示净值曲线、阶段收益、回撤、基金经理、规模费率和重仓持股。",
                ["净值曲线和回撤曲线", "基金经理任期和规模变化", "重仓资产与行业暴露"],
            )
        else:
            _empty_state(
                "输入基金代码后生成画像",
                "详情页不会复用股票报告，它会围绕基金净值、风险和交易成本组织信息。",
                ["基金净值表现", "风险收益指标", "费用和确认规则"],
            )
    with right:
        st.dataframe(DETAIL_FIELDS, width="stretch", hide_index=True, height=260)

with tab_portfolio:
    st.markdown("### 基金组合")
    st.markdown(
        '<div class="fund-section-note">基金组合独立于股票组合：用于目标权重、核心/卫星/防守角色、定投计划和组合风险暴露。</div>',
        unsafe_allow_html=True,
    )
    allocation = st.data_editor(
        ALLOCATION_TEMPLATE,
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
    )
    target_weight = allocation["目标权重%"].sum() if "目标权重%" in allocation else 0
    filled_funds = int((allocation["基金代码"].astype(str).str.strip() != "").sum()) if "基金代码" in allocation else 0

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("组合数量", str(filled_funds))
    p2.metric("目标仓位", f"{target_weight:.0f}%")
    p3.metric("定投计划", "未设置")
    p4.metric("再平衡", "待启用")
    if target_weight > 100:
        st.warning("目标权重超过 100%，后续接入组合保存时会阻止提交。")

with tab_paper:
    st.markdown("### 基金模拟舱")
    st.markdown(
        '<div class="fund-section-note">基金模拟舱会和股票模拟盘分开：场内 ETF/LOF 按交易价格，场外基金按净值申购/赎回和确认日建模。</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="fund-rule">
            <div class="fund-rule-item">
                <div class="fund-rule-title">场内交易</div>
                <div class="fund-rule-copy">适合 ETF/LOF，交易动作接近股票，但会在基金模块内单独记录持仓、费用和信号来源。</div>
            </div>
            <div class="fund-rule-item">
                <div class="fund-rule-title">场外申赎</div>
                <div class="fund-rule-copy">适合开放式基金，模拟净值确认、申购费、赎回费和 T+1/T+2 确认带来的资金占用。</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(PAPER_RULE_ROWS, width="stretch", hide_index=True)
    st.button("加入基金模拟舱", disabled=True, width="stretch")
