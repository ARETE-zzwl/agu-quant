"""Knowledge base browser for strategy, Chan theory, and A-share rules."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from web.components.common import inject_css

load_dotenv()

st.set_page_config(page_title="知识库", page_icon="📚", layout="wide", initial_sidebar_state="expanded")
inject_css()

ROOT = Path(__file__).resolve().parents[2]
KB_ROOT = ROOT / "docs" / "knowledge_base"
CATALOG_PATH = KB_ROOT / "catalog.json"


@st.cache_data(show_spinner=False)
def load_catalog() -> dict:
    if not CATALOG_PATH.exists():
        return {"documents": []}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_doc(rel_path: str) -> str:
    path = (KB_ROOT / rel_path).resolve()
    if KB_ROOT not in path.parents and path != KB_ROOT:
        return "文档路径非法。"
    if not path.exists():
        return "文档不存在。"
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip()
    return text


def category_name(doc_id: str) -> str:
    if doc_id.startswith("chan."):
        return "缠论"
    if doc_id.startswith("market."):
        return "A股规则"
    if doc_id.startswith("quant."):
        return "量化与回测"
    if doc_id.startswith("agent."):
        return "Agent规范"
    return "其他"


st.markdown(
    '<div style="margin-bottom:0.5rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">📚 知识库</span>'
    '<span style="color:#777;font-size:0.85rem;margin-left:0.8rem;">'
    '缠论 · A股规则 · 因子 · 技术指标 · 回测风控 · Agent规范</span></div>',
    unsafe_allow_html=True,
)
st.caption("知识库用于统一系统口径和AI解释边界，不构成投资建议。")

catalog = load_catalog()
docs = sorted(catalog.get("documents", []), key=lambda d: (d.get("priority", 9), d.get("id", "")))

query = st.text_input("搜索知识点", placeholder="例：三买、背驰、T+1、低波、回测")
if query:
    q = query.lower()
    docs = [
        d for d in docs
        if q in d.get("title", "").lower()
        or q in d.get("id", "").lower()
        or any(q in tag.lower() for tag in d.get("tags", []))
        or q in load_doc(d.get("path", "")).lower()
    ]

if not docs:
    st.info("没有匹配的知识文档。")
    st.stop()

left, right = st.columns([0.9, 2.2])
with left:
    st.markdown("### 目录")
    selected_id = st.radio(
        "选择文档",
        [d["id"] for d in docs],
        format_func=lambda doc_id: next((d["title"] for d in docs if d["id"] == doc_id), doc_id),
        label_visibility="collapsed",
    )

    selected = next(d for d in docs if d["id"] == selected_id)
    st.markdown("### 元信息")
    st.write(f"分类：{category_name(selected_id)}")
    st.write(f"优先级：{selected.get('priority', '-')}")
    st.write("标签：" + "、".join(selected.get("tags", [])))

with right:
    selected = next(d for d in docs if d["id"] == selected_id)
    st.markdown(load_doc(selected["path"]))
