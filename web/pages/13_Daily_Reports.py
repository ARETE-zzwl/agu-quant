"""Configure, run, and browse automated daily research reports."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from tradingagents.reporting.daily import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    load_daily_config,
    normalize_watchlist,
    run_daily_reports,
    save_daily_config,
)
from web.components.common import inject_css, require_premium_page
from web.components.sidebar import render_sidebar


st.set_page_config(page_title="每日投研报告", page_icon="◫", layout="wide")
inject_css()

with st.sidebar:
    render_sidebar()

require_premium_page("每日投研报告", required_plan="pro")

st.markdown(
    """
    <div class="ta-page-header">
        <div class="ta-eyebrow">DAILY RESEARCH</div>
        <h1 class="ta-page-title">每日投研报告</h1>
        <div class="ta-page-subtitle">为自选股批量生成可归档的 Markdown 研究报告，并由 Windows 任务计划定时执行。</div>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    saved = load_daily_config(DEFAULT_CONFIG_PATH)
except (FileNotFoundError, ValueError, OSError):
    saved = {"tickers": ["600519"], "template": "brief"}

left, right = st.columns([1, 1.25], gap="large")
with left:
    st.subheader("任务配置")
    ticker_text = st.text_area(
        "自选股代码",
        value=", ".join(saved["tickers"]),
        help="使用逗号、空格或换行分隔，最多 20 只，仅接受 6 位代码。",
    )
    template_labels = {
        "brief": "简报：结论、技术、情绪和风险",
        "full": "完整：7 分析师、多空与风控",
        "risk": "风险：政策、游资、解禁与风控",
    }
    template_names = list(template_labels)
    selected_template = st.selectbox(
        "报告模板",
        template_names,
        index=template_names.index(saved["template"]),
        format_func=lambda value: template_labels[value],
    )
    trade_date = st.date_input("研究日期", value=date.today())

    save_col, run_col = st.columns(2)
    if save_col.button("保存定时配置", use_container_width=True):
        try:
            tickers = normalize_watchlist(ticker_text)
            config_path = save_daily_config(tickers, selected_template)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"已保存到 {config_path}")

    if run_col.button("立即生成", type="primary", use_container_width=True):
        try:
            tickers = normalize_watchlist(ticker_text)
        except ValueError as exc:
            st.error(str(exc))
        else:
            with st.spinner("正在逐只生成报告，这会产生模型调用费用..."):
                results = run_daily_reports(
                    tickers,
                    trade_date.isoformat(),
                    selected_template,
                )
            for result in results:
                if result.success:
                    st.success(f"{result.ticker} 已生成：{result.path}")
                else:
                    st.error(f"{result.ticker} 失败：{result.error}")

    st.caption("Windows 自动任务：以 PowerShell 运行 scripts/install_daily_task.ps1。")

with right:
    st.subheader("报告归档")
    report_root = Path(DEFAULT_OUTPUT_DIR)
    report_files = sorted(report_root.rglob("*.md"), reverse=True)[:30] if report_root.exists() else []
    if not report_files:
        st.info("还没有自动日报。保存配置后可先点击“立即生成”验证模型和数据源。")
    for report_file in report_files:
        with st.expander(f"{report_file.parent.name} · {report_file.stem}"):
            content = report_file.read_text(encoding="utf-8")
            st.markdown(content)
            st.download_button(
                "下载 Markdown",
                data=content,
                file_name=report_file.name,
                mime="text/markdown",
                key=f"download_{report_file}",
            )

st.caption("自动报告不构成证券投资咨询。请控制自选股数量并关注模型 Token 成本。")
