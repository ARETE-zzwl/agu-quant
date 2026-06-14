"""板块分析 — 行业/概念排名 + Treemap热力图."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from web.components.common import inject_css
from web.components.sector_widgets import render_sector_table, render_concept_table

st.set_page_config(page_title="板块分析", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
inject_css()

st.markdown(
    '<div style="margin-bottom:1rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">📊 板块分析</span>'
    '<span style="color:#666;font-size:0.85rem;margin-left:0.8rem;">行业/概念排名 · 板块轮动热力图</span></div>',
    unsafe_allow_html=True,
)


@st.cache_data(ttl=120, show_spinner=False)
def _load_industry():
    import re
    from tradingagents.dataflows.a_stock import get_industry_comparison
    text = get_industry_comparison("000001", "")
    results = []
    for line in text.split("\n"):
        m = re.match(r"\s*(\d+)\.\s*(\S+)\s*\|\s*([\-\d.]+)%\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\S+)", line)
        if m:
            results.append({"rank": int(m.group(1)), "name": m.group(2), "change_pct": float(m.group(3)),
                           "up_count": int(m.group(4)), "down_count": int(m.group(5)), "leader_stock": m.group(6)})
    return results


@st.cache_data(ttl=120, show_spinner=False)
def _load_concepts():
    import requests as _req
    _UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {"pn": "1", "pz": "50", "po": "1", "np": "1", "fltt": "2", "invt": "2",
              "fs": "m:90+t:1", "fields": "f2,f3,f4,f12,f14,f104,f105,f128"}
    r = _req.get(url, params=params, headers={"User-Agent": _UA}, timeout=15)
    items = r.json().get("data", {}).get("diff", [])
    return [{"code": i.get("f12", ""), "name": i.get("f14", ""), "change_pct": float(i.get("f3", 0) or 0),
             "price": float(i.get("f2", 0) or 0), "up_count": i.get("f104", 0) or 0,
             "down_count": i.get("f105", 0) or 0, "leader_stock": i.get("f128", "")}
            for i in items]


tab1, tab2, tab3 = st.tabs(["行业板块", "概念板块", "📈 涨跌热力图"])

with tab1:
    with st.spinner("加载行业板块..."):
        industry = _load_industry()
    render_sector_table(industry, "申万行业板块")

with tab2:
    with st.spinner("加载概念板块..."):
        concepts = _load_concepts()
    render_concept_table(concepts)

with tab3:
    c1, c2 = st.columns([3, 1])
    sector_type = c1.radio("板块类型", ["行业板块", "概念板块"], horizontal=True,
                           key="heat_type", label_visibility="collapsed")
    if c2.button("🔄 刷新", key="heat_refresh", use_container_width=True):
        st.cache_data.clear()

    with st.spinner("加载..."):
        if sector_type == "行业板块":
            data = _load_industry()
        else:
            data = _load_concepts()

    if not data:
        st.stop()

    rows = []
    for s in data:
        chg = round(s["change_pct"], 1)
        rows.append({"name": s["name"], "chg": chg, "abs": abs(chg),
                     "up": s.get("up_count", 0), "dn": s.get("down_count", 0),
                     "ld": s.get("leader_stock", ""),
                     "size": max(abs(chg), 0.15) ** 0.85})
    df_all = pd.DataFrame(rows)
    up_df = df_all[df_all["chg"] > 0].sort_values("abs", ascending=False)
    dn_df = df_all[df_all["chg"] < 0].sort_values("abs", ascending=False)

    import plotly.express as px

    def build_treemap(df_side, color_scale):
        if df_side.empty:
            return None
        # Use abs(chg) as color driver so both sides: bigger = brighter
        plot_df = df_side.copy()
        plot_df["intensity"] = plot_df["abs"]
        fig = px.treemap(
            plot_df, path=["name"], values="size", color="intensity",
            color_continuous_scale=color_scale,
            hover_data={"chg": ":.1f", "up": True, "dn": True, "ld": True, "size": False, "intensity": False},
        )
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[0]:+.1f}%",
            textfont=dict(size=15, color="#f5f1eb"),
            textposition="middle center",
            marker=dict(line=dict(width=1.5, color="#0c0c0c")),
            hovertemplate="<b>%{label}</b><br>%{customdata[0]:+.1f}%<br>"
            "涨%{customdata[1]}家 跌%{customdata[2]}家<br>领涨: %{customdata[3]}<extra></extra>",
        )
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0c0c0c",
                          margin=dict(l=0, r=0, t=25, b=0), height=500,
                          coloraxis_showscale=False)
        return fig

    red_scale = [(0, "#3b1a1a"), (0.3, "#7f1d1d"), (0.6, "#b91c1c"), (0.85, "#dc2626"), (1, "#f87171")]
    green_scale = [(0, "#1a2e1a"), (0.3, "#14532d"), (0.6, "#15803d"), (0.85, "#22c55e"), (1, "#4ade80")]

    left, right = st.columns(2)
    with left:
        st.markdown(f"##### 🔥 领涨 ({len(up_df)})")
        fig_u = build_treemap(up_df, red_scale)
        if fig_u:
            st.plotly_chart(fig_u, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("无上涨板块")
    with right:
        st.markdown(f"##### ❄️ 领跌 ({len(dn_df)})")
        fig_d = build_treemap(dn_df, green_scale)
        if fig_d:
            st.plotly_chart(fig_d, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("无下跌板块")

st.markdown("---")
st.caption(f"数据: 东方财富 push2 | {datetime.now().strftime('%H:%M:%S')}")
