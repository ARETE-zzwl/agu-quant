"""Reusable widgets for the Stock Screener page."""

from __future__ import annotations

from datetime import datetime

import streamlit as st
import pandas as pd

from web.components.common import fmt_change_pct, fmt_amount, fmt_number, color_change

_MARKET_OPTIONS = {
    "全部A股": "all",
    "沪市主板": "sh",
    "深市主板": "sz",
    "创业板": "cyb",
    "科创板": "kcb",
}


def render_filter_panel() -> dict:
    """Render multi-condition screener filter panel.

    Returns filter dict or None if not submitted.
    """
    with st.form("screener_filters"):
        c1, c2, c3, c4 = st.columns(4)

        market = c1.selectbox("市场", list(_MARKET_OPTIONS.keys()), index=0)
        pe_min = c2.number_input("PE 最低", value=None, step=1.0, format="%.1f")
        pe_max = c3.number_input("PE 最高", value=None, step=1.0, format="%.1f")
        pb_max = c4.number_input("PB 最高", value=None, step=0.5, format="%.2f")

        c5, c6, c7, c8 = st.columns(4)
        roe_min = c5.number_input("ROE 最低(%)", value=None, step=1.0, format="%.1f")
        mcap_min = c6.number_input("最低市值(亿)", value=None, step=10.0, format="%.0f")
        turnover_min = c7.number_input("最低换手率(%)", value=None, step=1.0, format="%.1f")
        change_min = c8.number_input("最低涨跌(%)", value=None, step=1.0, format="%.1f")

        c9, c10 = st.columns([1, 3])
        sort_options = {
            "涨跌幅降序": ("f3", True),
            "涨跌幅升序": ("f3", False),
            "市值降序": ("f20", True),
            "ROE降序": ("f37", True),
            "成交额降序": ("f6", True),
            "换手率降序": ("f8", True),
        }
        sort_choice = c9.selectbox("排序", list(sort_options.keys()), index=0)
        sort_by, sort_desc = sort_options[sort_choice]

        page_size = c10.selectbox("每页显示", [20, 50, 100], index=1)

        submitted = st.form_submit_button("🔍 开始筛选", type="primary", use_container_width=True)

    if not submitted:
        return None

    filters = {
        "market": _MARKET_OPTIONS[market],
        "pe_max": pe_max if pe_max and pe_max > 0 else None,
        "pb_max": pb_max if pb_max and pb_max > 0 else None,
        "roe_min": roe_min if roe_min and roe_min > 0 else None,
        "mcap_min": mcap_min if mcap_min and mcap_min > 0 else None,
        "change_min": change_min if change_min and change_min != 0 else None,
        "turnover_min": turnover_min if turnover_min and turnover_min > 0 else None,
        "sort_by": sort_by,
        "sort_desc": sort_desc,
        "page_size": page_size,
    }
    return filters


def render_results_table(stocks: list[dict], total: int, page: int = 1) -> bool:
    """Render screener results table with action buttons.

    Returns True if a "深度分析" button was clicked.
    """
    if not stocks:
        st.info("未找到匹配股票，请放宽筛选条件")
        return False

    st.success(f"找到 {total} 只股票")

    df = pd.DataFrame(stocks)
    display_cols = ["code", "name", "price", "change_pct", "pe", "pb", "roe", "market_cap", "turnover"]
    display_labels = ["代码", "名称", "最新价", "涨跌幅%", "PE", "PB", "ROE%", "总市值(亿)", "换手率%"]

    available_cols = [c for c in display_cols if c in df.columns]
    available_labels = [display_labels[i] for i, c in enumerate(display_cols) if c in df.columns]

    df_display = df[available_cols].copy()
    df_display.columns = available_labels

    # Format
    if "涨跌幅%" in df_display.columns:
        df_display["涨跌幅%"] = df_display["涨跌幅%"].apply(lambda x: f"{x:+.2f}%")
    if "PE" in df_display.columns:
        df_display["PE"] = df_display["PE"].apply(lambda x: f"{x:.1f}" if x > 0 else "—")
    if "PB" in df_display.columns:
        df_display["PB"] = df_display["PB"].apply(lambda x: f"{x:.2f}" if x > 0 else "—")
    if "ROE%" in df_display.columns:
        df_display["ROE%"] = df_display["ROE%"].apply(lambda x: f"{x:.1f}" if x > 0 else "—")
    if "换手率%" in df_display.columns:
        df_display["换手率%"] = df_display["换手率%"].apply(lambda x: f"{x:.2f}")

    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Deep-analysis button for each row
    clicked_code = None
    with st.expander("🔬 一键深度分析", expanded=False):
        cols = st.columns([3, 1])
        selected_code = cols[0].selectbox(
            "选择股票进行7-Agent深度分析",
            [f"{row['code']} {row['name']}" for row in stocks],
        )
        if cols[1].button("开始分析", type="primary", use_container_width=True):
            clicked_code = selected_code.split()[0]

    if clicked_code:
        st.session_state["start_analysis"] = {
            "ticker": clicked_code,
            "trade_date": datetime.now().strftime("%Y-%m-%d"),
        }
        st.session_state["viewing_history"] = None
        st.success(f"跳转到 {clicked_code} 深度分析页面...")
        return True

    return False
