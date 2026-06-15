"""Sidebar: navigation, stock input, LLM config, history."""

from __future__ import annotations

from datetime import date

import streamlit as st

from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS
from web.history import get_history

_PROVIDERS: list[tuple[str, str]] = [
    ("DeepSeek", "deepseek"),
    ("通义千问 Qwen", "qwen"),
    ("智谱 GLM", "glm"),
    ("MiniMax", "minimax"),
    ("OpenAI", "openai"),
    ("Anthropic", "anthropic"),
    ("Google Gemini", "google"),
    ("xAI Grok", "xai"),
    ("Ollama", "ollama"),
]

_PROVIDER_DISPLAY = [n for n, _ in _PROVIDERS]
_PROVIDER_KEYS = [k for _, k in _PROVIDERS]

def _resolve_user_input(raw: str) -> tuple:
    from tradingagents.dataflows.a_stock import resolve_ticker
    try:
        return resolve_ticker(raw), None
    except ValueError as e:
        return "", str(e)


def _render_llm_config():
    idx = st.selectbox("LLM 供应商", range(len(_PROVIDERS)),
                       format_func=lambda i: _PROVIDER_DISPLAY[i], key="llm_provider_idx")
    provider = _PROVIDER_KEYS[idx]
    st.session_state["llm_provider"] = provider

    if provider in MODEL_OPTIONS:
        qo = MODEL_OPTIONS[provider]["quick"]
        do = MODEL_OPTIONS[provider]["deep"]
        qi = st.selectbox("快速模型", range(len(qo)),
                          format_func=lambda i: qo[i][0], key="quick_model_idx")
        di = st.selectbox("深度模型", range(len(do)),
                          format_func=lambda i: do[i][0], key="deep_model_idx")
        st.session_state["quick_think_llm"] = qo[qi][1]
        st.session_state["deep_think_llm"] = do[di][1]
    else:
        st.session_state["quick_think_llm"] = st.text_input("快速模型ID", key="cq")
        st.session_state["deep_think_llm"] = st.text_input("深度模型ID", key="cd")


def render_sidebar():
    from tradingagents.auth import get_license_status, is_premium

    license_status = get_license_status()
    premium = license_status.get("valid", False)

    st.markdown(
        '<div style="text-align:center;margin-bottom:0.5rem;">'
        '<span style="font-size:1.1rem;font-weight:800;color:#f5f1eb;">'
        'A股量化系统</span></div>',
        unsafe_allow_html=True,
    )

    status_color = "#22c55e" if premium else "#f97316"
    st.markdown(
        f'<div style="text-align:center;margin-bottom:0.3rem;font-size:0.8rem;color:{status_color}">'
        f'{license_status.get("display", "🔒 免费版")}</div>',
        unsafe_allow_html=True,
    )
    if not premium:
        st.page_link("pages/activate.py", label="🔑 赞赏激活", use_container_width=True)
    else:
        st.page_link("pages/admin.py", label="🛡️ 管理员", use_container_width=True)

    st.markdown("---")
    st.caption("📋 功能导航")
    premium_pages = {"深度分析", "AI 荐股", "因子引擎", "股票监控", "模拟盘"}
    nav_items = [
        ("📈 深度分析", "app.py", "深度分析"),
        ("🏠 大盘看盘", "pages/1_Market_Dashboard.py", "大盘看盘"),
        ("📊 板块分析", "pages/2_Sector_Board.py", "板块分析"),
        ("🔍 一键选股", "pages/3_Stock_Screener.py", "一键选股"),
        ("🧠 AI 荐股", "pages/4_AI_Picks.py", "AI 荐股"),
        ("📚 策略库", "pages/10_Strategy_Guide.py", "策略库"),
        ("⚙️ 因子引擎", "pages/5_Factor_Engine.py", "因子引擎"),
        ("📡 股票监控", "pages/6_Stock_Monitor.py", "股票监控"),
        ("💰 模拟盘", "pages/7_Paper_Trade.py", "模拟盘"),
        ("🧩 缠论Agent", "pages/8_Chan_Agent.py", "缠论Agent"),
        ("📚 知识库", "pages/9_Knowledge_Base.py", "知识库"),
    ]
    for label, target, page_name in nav_items:
        lock = " 🔒" if (not premium and page_name in premium_pages) else ""
        if st.button(label + lock, key=f"nav_{target}", use_container_width=True):
            st.switch_page(target)

    st.markdown("---")
    st.markdown("#### 新建分析")

    ticker = st.text_input("股票代码", placeholder="例: 300750 或 宁德时代", key="input_ticker")
    trade_date = st.date_input("分析日期", value=date.today(), key="input_date")

    with st.expander("模型配置", expanded=False):
        _render_llm_config()

    tracker = st.session_state.get("tracker")
    busy = tracker is not None and tracker.is_running

    if st.button(
        "开始分析" if not busy else "分析中...",
        use_container_width=True, disabled=busy or not ticker, type="primary",
    ):
        code, err = _resolve_user_input(ticker)
        if err:
            st.error(f"❌ {err}")
        else:
            if code != ticker.strip():
                st.success(f"✅ {ticker.strip()} -> {code}")
            st.session_state["start_analysis"] = {"ticker": code, "trade_date": trade_date.strftime("%Y-%m-%d")}
            st.session_state["viewing_history"] = None

    st.markdown("---")
    st.markdown("#### 历史记录")

    history = get_history()
    if not history:
        st.caption("暂无历史记录")
        return

    for entry in history[:20]:
        t, d = entry["ticker"], entry["date"]
        if st.button(f"{t}  ·  {d}", key=f"hist_{t}_{d}", use_container_width=True):
            st.session_state["viewing_history"] = entry["path"]
            st.session_state["start_analysis"] = None
