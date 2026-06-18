"""Strategy catalog and implementation notes."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from tradingagents.ranking.scoring_engine import WEIGHT_LABELS, ScoringEngine
from web.components.common import inject_css


st.set_page_config(page_title="策略库", page_icon="📚", layout="wide", initial_sidebar_state="expanded")
inject_css()

details = ScoringEngine.get_strategy_details()
detail_by_key = {d["key"]: d for d in details}
keys = list(detail_by_key)

query_strategy = st.query_params.get("strategy", "balanced")
if isinstance(query_strategy, list):
    query_strategy = query_strategy[0] if query_strategy else "balanced"
if query_strategy not in detail_by_key:
    query_strategy = "balanced"

st.markdown(
    '<div style="margin-bottom:0.5rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">📚 策略库</span>'
    '<span style="color:#888;font-size:0.85rem;margin-left:0.8rem;">预设策略 · 权重结构 · 适用场景 · 实现说明</span>'
    '</div>',
    unsafe_allow_html=True,
)

families = Counter(d["family"] for d in details)
summary_cols = st.columns(4)
summary_cols[0].metric("可选策略", len(details))
summary_cols[1].metric("策略族", len(families))
summary_cols[2].metric("回测优选", families.get("回测优选", 0))
summary_cols[3].metric("经典研究", families.get("经典研究", 0))

select_col, family_col, risk_col = st.columns([3, 1, 1])
selected_index = keys.index(query_strategy)
selected_key = select_col.selectbox(
    "策略",
    keys,
    index=selected_index,
    format_func=lambda key: f"{detail_by_key[key]['label']} · {detail_by_key[key]['family']}",
)
selected = detail_by_key[selected_key]
st.query_params["strategy"] = selected_key

family_col.metric("类型", selected["family"])
risk_col.metric("风险", selected["risk_level"])

st.markdown("### 策略说明")
st.write(selected["desc"])

m1, m2, m3 = st.columns([1, 1, 2])
m1.metric("持有周期", selected["holding_period"])
m2.metric("策略代码", selected["key"])
m3.info(selected["best_for"])

st.markdown("### 权重结构")
weight_rows = []
for key, weight in selected["weights"].items():
    weight_rows.append(
        {
            "维度": WEIGHT_LABELS.get(key, key),
            "权重": f"{weight:.1%}",
            "key": key,
        }
    )
weight_df = pd.DataFrame(weight_rows)
chart_df = pd.DataFrame(
    {"权重": {WEIGHT_LABELS.get(k, k): v for k, v in selected["weights"].items()}}
)
left, right = st.columns([1, 2])
left.dataframe(weight_df, use_container_width=True, hide_index=True)
right.bar_chart(chart_df)

st.markdown("### 筛选与实现")
filter_rows = [{"条件": k, "阈值": v} for k, v in selected["filters"].items()]
if filter_rows:
    st.dataframe(pd.DataFrame(filter_rows), use_container_width=True, hide_index=True)
else:
    st.caption("无硬性预筛选条件")
st.write(selected["implementation"])
if selected.get("research_sources"):
    st.markdown("**研究来源**")
    for source in selected["research_sources"]:
        st.markdown(f"- [{source['title']}]({source['url']})")
st.caption(selected["backtest_note"])

st.markdown("---")
st.markdown("### 全策略总览")
rows = []
for item in details:
    top_weights = sorted(item["weights"].items(), key=lambda pair: pair[1], reverse=True)[:2]
    rows.append(
        {
            "策略": item["label"],
            "key": item["key"],
            "类型": item["family"],
            "风险": item["risk_level"],
            "持有周期": item["holding_period"],
            "主权重": " / ".join(f"{WEIGHT_LABELS[k]} {v:.0%}" for k, v in top_weights),
            "说明": item["desc"],
        }
    )
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=520)

st.markdown("---")
st.caption("策略库用于研究和模拟盘配置；历史回测不构成未来收益承诺。")
