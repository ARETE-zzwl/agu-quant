"""一键选股."""

from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from web.components.common import inject_css
from web.components.screener_widgets import render_filter_panel, render_results_table

st.set_page_config(page_title="一键选股", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")
inject_css()

st.markdown(
    '<div style="margin-bottom:1rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">🔍 一键选股</span>'
    '<span style="color:#666;font-size:0.85rem;margin-left:0.8rem;">多条件筛选 · 实时排序</span></div>',
    unsafe_allow_html=True,
)

for key in ["screener_results", "screener_total"]:
    if key not in st.session_state:
        st.session_state[key] = (None if key == "screener_results" else 0)

filters = render_filter_panel()

if filters is not None:
    with st.spinner("正在筛选..."):
        from tradingagents.dataflows.a_stock import screen_stocks
        stocks, total = screen_stocks(
            market=filters["market"], pe_max=filters.get("pe_max"),
            pb_max=filters.get("pb_max"), roe_min=filters.get("roe_min"),
            mcap_min=filters.get("mcap_min"), change_min=filters.get("change_min"),
            turnover_min=filters.get("turnover_min"),
            sort_by=filters.get("sort_by", "f3"),
            sort_desc=filters.get("sort_desc", True),
            page_size=filters.get("page_size", 50),
        )
        st.session_state["screener_results"] = stocks
        st.session_state["screener_total"] = total
        if not stocks:
            st.warning("行情源暂时没有返回可用股票数据，请稍后重试或缩小筛选范围。")

stocks_data = st.session_state.get("screener_results")
total_count = st.session_state.get("screener_total", 0)

if stocks_data:
    st.markdown("---")
    render_results_table(stocks_data, total_count)

st.markdown("---")
st.caption(f"数据: 东方财富 push2 | {datetime.now().strftime('%H:%M:%S')}")
