"""A股量化 — 深度分析主页."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env")

from tradingagents.default_config import DEFAULT_CONFIG
from web.components.common import inject_css, require_premium_page
from web.components.progress_panel import render_progress
from web.components.report_viewer import render_report
from web.components.sidebar import render_sidebar
from web.history import extract_signal, load_analysis
from web.progress import ProgressTracker
from web.runner import run_analysis_in_thread

st.set_page_config(page_title="深度分析", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
inject_css()


def _build_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = st.session_state.get("llm_provider", "deepseek")
    config["deep_think_llm"] = st.session_state.get("deep_think_llm", "deepseek-chat")
    config["quick_think_llm"] = st.session_state.get("quick_think_llm", "deepseek-chat")
    config["data_vendors"] = {
        "core_stock_apis": "a_stock", "technical_indicators": "a_stock",
        "fundamental_data": "a_stock", "news_data": "a_stock", "signal_data": "a_stock",
    }
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["output_language"] = "Chinese"
    return config


with st.sidebar:
    render_sidebar()

require_premium_page("深度分析")

start_req = st.session_state.pop("start_analysis", None)
if start_req:
    tracker = ProgressTracker(ticker=start_req["ticker"], trade_date=start_req["trade_date"])
    st.session_state["tracker"] = tracker
    run_analysis_in_thread(
        ticker=start_req["ticker"], trade_date=start_req["trade_date"],
        config=_build_config(), tracker=tracker,
    )

tracker = st.session_state.get("tracker")
viewing_history = st.session_state.get("viewing_history")

if viewing_history:
    try:
        state = load_analysis(viewing_history)
        signal = extract_signal(state)
        ticker = Path(viewing_history).parent.parent.name
        trade_date = Path(viewing_history).stem.replace("full_states_log_", "")
        render_report(state, ticker, trade_date, signal)
    except Exception as exc:
        st.error(f"加载失败: {exc}")
elif tracker and tracker.is_running:
    render_progress(tracker)
    time.sleep(2)
    st.rerun()
elif tracker and tracker.is_complete:
    render_report(tracker.final_state, tracker.ticker, tracker.trade_date, tracker.signal, elapsed=tracker.elapsed)
elif tracker and tracker.error:
    st.error(f"分析失败: {tracker.error}")
    if st.button("重试"):
        st.session_state.pop("tracker", None)
        st.rerun()
else:
    st.markdown(
        '<div style="display:flex;flex-direction:column;align-items:center;'
        'justify-content:center;min-height:40vh;text-align:center;">'
        '<div style="font-size:3rem;margin-bottom:1rem;">📈</div>'
        '<div style="font-size:1.6rem;font-weight:800;color:#f5f1eb;margin-bottom:0.5rem;">'
        '深度分析</div>'
        '<div style="color:#888;font-size:0.95rem;line-height:1.6;">'
        '7位AI分析师协作，逐层辩论，产出投资决策报告</div>'
        '<div style="margin-top:2rem;padding:0.6rem 1.2rem;border:1px solid #333;'
        'border-radius:6px;color:#666;font-size:0.85rem;">'
        '在左侧输入股票代码，开始分析</div></div>',
        unsafe_allow_html=True,
    )
