"""基金中心：筛选、详情、组合与模拟申赎。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from tradingagents.fund_center import fetch_fund_profile, screen_funds
from tradingagents.fund_paper_trade import evaluate_allocation, get_fund_account
from web.components.common import inject_css, require_premium_page

load_dotenv()

st.set_page_config(page_title="基金中心", page_icon="F", layout="wide", initial_sidebar_state="expanded")
inject_css()
require_premium_page("基金中心")

FUND_TYPES = ["全部", "场外开放式", "场内 ETF/LOF", "股票型", "混合型", "债券型", "指数型", "QDII", "货币型"]
HORIZONS = ["近1月", "近3月", "近6月", "近1年", "今年来", "日内"]
RISK_LEVELS = ["稳健", "均衡", "进取"]

DEFAULT_ALLOCATION = [
    {"代码": "510300", "名称": "沪深300ETF", "类型": "场内 ETF/LOF", "定位": "核心", "目标权重%": 35},
    {"代码": "110011", "名称": "易方达优质精选混合", "类型": "混合型", "定位": "进攻", "目标权重%": 25},
    {"代码": "000083", "名称": "汇添富消费行业混合", "类型": "混合型", "定位": "卫星", "目标权重%": 20},
    {"代码": "003834", "名称": "华夏能源革新股票A", "类型": "股票型", "定位": "卫星", "目标权重%": 15},
]


st.markdown(
    """
<style>
.fund-hero {
    border: 1px solid #28343b;
    border-radius: 8px;
    padding: 1.05rem 1.15rem;
    margin-bottom: 1rem;
    background:
        linear-gradient(135deg, rgba(45, 212, 191, 0.10), rgba(249, 115, 22, 0.08)),
        #101518;
}
.fund-eyebrow {
    color: #2dd4bf;
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0;
}
.fund-hero h1 {
    color: #f4efe6;
    font-size: 1.65rem;
    line-height: 1.2;
    margin: 0.2rem 0 0.35rem 0;
}
.fund-hero p {
    color: #a7b2ba;
    margin: 0;
    font-size: 0.92rem;
}
.fund-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 0.85rem;
}
.fund-badges span {
    border: 1px solid #334149;
    background: #121b20;
    color: #d7e1e7;
    border-radius: 999px;
    padding: 0.22rem 0.58rem;
    font-size: 0.78rem;
}
.fund-status {
    border-left: 3px solid #2dd4bf;
    background: #10181c;
    padding: 0.75rem 0.85rem;
    color: #dce7ed;
    border-radius: 6px;
    margin-bottom: 0.85rem;
}
.fund-rule {
    border: 1px solid #28343b;
    border-radius: 8px;
    padding: 0.85rem;
    background: #101518;
    min-height: 112px;
}
.fund-rule strong {
    color: #f4efe6;
    display: block;
    margin-bottom: 0.35rem;
}
.fund-rule span {
    color: #a7b2ba;
    font-size: 0.85rem;
    line-height: 1.55;
}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300, show_spinner=False)
def _load_screen(query: str, fund_type: str, horizon: str, risk_level: str, limit: int):
    return screen_funds(query=query, fund_type=fund_type, horizon=horizon, risk_level=risk_level, limit=limit)


@st.cache_data(ttl=300, show_spinner=False)
def _load_profile(code: str):
    return fetch_fund_profile(code)


def _fmt_pct(value) -> str:
    if value is None or value == "":
        return "-"
    try:
        sign = "+" if float(value) > 0 else ""
        return f"{sign}{float(value):.2f}%"
    except (TypeError, ValueError):
        return "-"


def _fmt_rate(value) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "-"


def _screen_rows(candidates: list[dict], horizon: str) -> pd.DataFrame:
    rows = []
    for item in candidates:
        metrics = item.get("metrics") or {}
        returns = item.get("returns") or {}
        rows.append(
            {
                "代码": item.get("code", ""),
                "名称": item.get("name", ""),
                "类型": item.get("fund_type", ""),
                "净值/价格": item.get("latest_nav"),
                "日期": item.get("nav_date", ""),
                horizon: _fmt_pct(returns.get(horizon)),
                "近1年": _fmt_pct(returns.get("近1年")),
                "回撤": _fmt_pct(metrics.get("max_drawdown")),
                "波动": _fmt_pct(metrics.get("annualized_volatility")),
                "费率": _fmt_rate(item.get("purchase_fee_rate")),
                "评分": item.get("score", 0),
                "数据源": item.get("data_source", ""),
            }
        )
    return pd.DataFrame(rows)


def _profile_metrics(profile: dict) -> None:
    returns = profile.get("returns") or {}
    metrics = profile.get("metrics") or {}
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("净值/价格", profile.get("latest_nav") or "-", profile.get("nav_date") or "")
    c2.metric("近1月", _fmt_pct(returns.get("近1月")))
    c3.metric("近1年", _fmt_pct(returns.get("近1年")))
    c4.metric("最大回撤", _fmt_pct(metrics.get("max_drawdown")))
    c5.metric("年化波动", _fmt_pct(metrics.get("annualized_volatility")))


def _orders_frame(orders) -> pd.DataFrame:
    action_map = {"SUBSCRIBE": "申购/买入", "REDEEM": "赎回/卖出"}
    rows = []
    for order in reversed(orders[-50:]):
        rows.append(
            {
                "时间": order.time,
                "方向": action_map.get(order.action, order.action),
                "代码": order.code,
                "名称": order.name,
                "净值": order.nav,
                "份额": order.units,
                "金额": order.amount,
                "费用": order.fee,
                "状态": order.status,
                "说明": order.reason,
            }
        )
    return pd.DataFrame(rows)


if "fund_screen_results" not in st.session_state:
    st.session_state["fund_screen_results"] = []
if "fund_selected_code" not in st.session_state:
    st.session_state["fund_selected_code"] = "110011"
if "fund_allocation_rows" not in st.session_state:
    st.session_state["fund_allocation_rows"] = DEFAULT_ALLOCATION

st.markdown(
    """
<section class="fund-hero">
  <div class="fund-eyebrow">FUND RESEARCH CONSOLE</div>
  <h1>基金中心</h1>
  <p>场外开放式基金、场内 ETF/LOF、组合权重与基金模拟盘统一管理。</p>
  <div class="fund-badges">
    <span>天天基金净值</span>
    <span>东方财富 push2</span>
    <span>基金数据接口</span>
    <span>股票模拟盘隔离</span>
  </div>
</section>
""",
    unsafe_allow_html=True,
)

tab_screen, tab_detail, tab_portfolio, tab_trade = st.tabs(["基金筛选", "基金详情", "基金组合", "基金模拟舱"])

with tab_screen:
    st.markdown('<div class="fund-status">基金筛选会按收益周期、风险偏好和基金类型给出可落地候选。</div>', unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = st.columns([1.35, 1, 1, 1, 0.8])
    query = f1.text_input("代码或名称", value="", placeholder="110011 / 沪深300 / 易方达")
    fund_type = f2.selectbox("基金类型", FUND_TYPES, index=0)
    horizon = f3.selectbox("收益周期", HORIZONS, index=3)
    risk_level = f4.selectbox("风险偏好", RISK_LEVELS, index=1)
    limit = f5.number_input("数量", min_value=5, max_value=50, value=20, step=5)

    if st.button("一键筛选基金", type="primary", use_container_width=True):
        with st.spinner("正在拉取基金列表与行情..."):
            st.session_state["fund_screen_results"] = _load_screen(query, fund_type, horizon, risk_level, int(limit))

    candidates = st.session_state.get("fund_screen_results", [])
    if candidates:
        df = _screen_rows(candidates, horizon)
        st.dataframe(df, hide_index=True, use_container_width=True, height=360)
        labels = [f"{row.get('code')} {row.get('name')} | {row.get('fund_type')} | {row.get('score', 0)}分" for row in candidates]
        selected = st.selectbox("选入详情/模拟", labels)
        selected_row = candidates[labels.index(selected)]
        b1, b2 = st.columns(2)
        if b1.button("查看详情", use_container_width=True):
            st.session_state["fund_selected_code"] = selected_row["code"]
            st.rerun()
        if b2.button("加入组合", use_container_width=True):
            rows = list(st.session_state["fund_allocation_rows"])
            rows.append(
                {
                    "代码": selected_row["code"],
                    "名称": selected_row["name"],
                    "类型": selected_row["fund_type"],
                    "定位": "卫星",
                    "目标权重%": 5,
                }
            )
            st.session_state["fund_allocation_rows"] = rows
            st.success("已加入基金组合")
    else:
        st.info("输入条件后点击一键筛选基金。空条件会加载开放式基金排行榜和场内 ETF/LOF。")

with tab_detail:
    c1, c2 = st.columns([1, 0.22])
    detail_code = c1.text_input("基金代码", value=st.session_state.get("fund_selected_code", "110011"), key="fund_detail_code")
    refresh_detail = c2.button("刷新", use_container_width=True)
    if refresh_detail:
        _load_profile.clear()

    if detail_code:
        try:
            profile = _load_profile(detail_code.strip())
            st.session_state["fund_selected_code"] = profile["code"]
            st.markdown(f"### {profile['code']} {profile['name']}")
            st.caption(f"{profile.get('fund_type', '-')} | {profile.get('data_source', '-')}")
            _profile_metrics(profile)

            hist = pd.DataFrame(profile.get("nav_history") or [])
            left, right = st.columns([1.4, 1])
            with left:
                if not hist.empty:
                    hist["date"] = pd.to_datetime(hist["date"])
                    st.line_chart(hist.set_index("date")["nav"], height=320)
                else:
                    st.info("该基金暂无可绘制的历史净值序列，场内基金会显示实时价格。")
            with right:
                fee_rows = pd.DataFrame(
                    [
                        {"项目": "申购/买入费率", "值": _fmt_rate(profile.get("purchase_fee_rate"))},
                        {"项目": "原始申购费率", "值": _fmt_rate(profile.get("source_fee_rate"))},
                        {"项目": "最低申购", "值": profile.get("min_purchase", "-")},
                    ]
                )
                st.dataframe(fee_rows, hide_index=True, use_container_width=True)

                holdings = profile.get("holdings") or []
                if holdings:
                    st.markdown("#### 重仓持股")
                    st.dataframe(pd.DataFrame({"股票代码": holdings[:20]}), hide_index=True, use_container_width=True, height=220)
        except Exception as exc:
            st.error(f"基金详情加载失败: {exc}")
    else:
        st.info("输入基金代码查看详情。")

with tab_portfolio:
    st.markdown('<div class="fund-status">基金组合用于管理目标权重，不影响基金模拟舱持仓。</div>', unsafe_allow_html=True)
    allocation_df = pd.DataFrame(st.session_state["fund_allocation_rows"])
    edited = st.data_editor(
        allocation_df,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "目标权重%": st.column_config.NumberColumn("目标权重%", min_value=0, max_value=100, step=1),
            "定位": st.column_config.SelectboxColumn("定位", options=["核心", "卫星", "进攻", "防守", "现金替代"]),
            "类型": st.column_config.SelectboxColumn("类型", options=FUND_TYPES[1:] + ["其他"]),
        },
    )
    st.session_state["fund_allocation_rows"] = edited.to_dict("records")
    report = evaluate_allocation(st.session_state["fund_allocation_rows"])
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("目标权重", f"{report['total_weight']:.1f}%")
    p2.metric("基金数量", len(report["rows"]))
    p3.metric("核心权重", f"{report['role_weights'].get('核心', 0):.1f}%")
    p4.metric("场内权重", f"{report['type_weights'].get('场内 ETF/LOF', 0):.1f}%")
    if report["warnings"]:
        for warning in report["warnings"]:
            st.warning(warning)
    else:
        st.success("组合权重处于可执行区间。")

    col_role, col_type = st.columns(2)
    with col_role:
        if report["role_weights"]:
            st.bar_chart(pd.Series(report["role_weights"]), height=260)
    with col_type:
        if report["type_weights"]:
            st.bar_chart(pd.Series(report["type_weights"]), height=260)

with tab_trade:
    acc = get_fund_account("default")
    summary = acc.summary()
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("总资产", f"{summary['total_equity']:,.0f}", delta=_fmt_pct(summary["total_return"]))
    s2.metric("现金", f"{summary['cash']:,.0f}")
    s3.metric("持仓市值", f"{summary['market_value']:,.0f}")
    s4.metric("累计盈亏", f"{summary['total_pnl']:+,.0f}")
    s5.metric("持仓数", len(summary["positions"]))

    left, right = st.columns([0.95, 1.45])
    with left:
        st.markdown("### 申购 / 赎回")
        with st.form("fund_trade_form"):
            trade_code = st.text_input("基金代码", value=st.session_state.get("fund_selected_code", "110011"))
            direction = st.radio("方向", ["申购/买入", "赎回/卖出"], horizontal=True)
            amount = st.number_input("申购金额", min_value=100, value=5000, step=500)
            units = st.number_input("赎回份额", min_value=0.0, value=0.0, step=100.0)
            submitted = st.form_submit_button("确认委托", type="primary", use_container_width=True)

        if submitted:
            try:
                profile = _load_profile(trade_code.strip())
                nav = float(profile.get("latest_nav") or 0)
                fee_rate = float(profile.get("purchase_fee_rate") or 0.0015)
                if direction == "申购/买入":
                    if profile.get("fund_type") == "场内 ETF/LOF":
                        order = acc.buy_exchange(profile["code"], profile["name"], amount=amount, price=nav)
                    else:
                        order = acc.subscribe(
                            profile["code"],
                            profile["name"],
                            amount=amount,
                            nav=nav,
                            fund_type=profile.get("fund_type", "场外开放式"),
                            fee_rate=fee_rate,
                        )
                else:
                    redeem_units = units
                    if redeem_units <= 0 and profile["code"] in acc.positions:
                        redeem_units = acc.positions[profile["code"]].units
                    sell_fee = 0.00015 if profile.get("fund_type") == "场内 ETF/LOF" else 0.005
                    order = acc.redeem(profile["code"], units=redeem_units, nav=nav, fee_rate=sell_fee)

                if order.status == "filled":
                    st.success(f"{order.reason}: {order.code} {order.units:.2f}份，费用{order.fee:.2f}")
                else:
                    st.error(order.reason)
                st.rerun()
            except Exception as exc:
                st.error(f"委托失败: {exc}")

        if st.button("按最新净值刷新持仓", use_container_width=True):
            refreshed = 0
            for pos in list(acc.positions.values()):
                try:
                    profile = _load_profile(pos.code)
                    nav = float(profile.get("latest_nav") or 0)
                    if nav > 0:
                        acc.mark_to_nav(pos.code, nav)
                        refreshed += 1
                except Exception:
                    continue
            st.success(f"已刷新 {refreshed} 只基金")
            st.rerun()

    with right:
        st.markdown("### 持仓")
        if summary["positions"]:
            st.dataframe(pd.DataFrame(summary["positions"]), hide_index=True, use_container_width=True, height=260)
        else:
            st.info("暂无基金持仓。")

        st.markdown("### 委托记录")
        if summary["orders"]:
            st.dataframe(_orders_frame(summary["orders"]), hide_index=True, use_container_width=True, height=280)
        else:
            st.caption("暂无委托记录。")

    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.markdown('<div class="fund-rule"><strong>场外开放式</strong><span>按净值估算份额，申购费在金额内扣除。</span></div>', unsafe_allow_html=True)
    with r2:
        st.markdown('<div class="fund-rule"><strong>场内 ETF/LOF</strong><span>按实时价格估算成交，费用使用低佣金规则。</span></div>', unsafe_allow_html=True)
    with r3:
        st.markdown('<div class="fund-rule"><strong>赎回规则</strong><span>按当前净值估算到账，场外默认计入短持有期赎回费。</span></div>', unsafe_allow_html=True)
    with r4:
        st.markdown('<div class="fund-rule"><strong>股票模拟盘</strong><span>基金账户独立持久化，不与股票模拟盘资金混用。</span></div>', unsafe_allow_html=True)

st.caption(f"基金中心数据会缓存 5 分钟 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
