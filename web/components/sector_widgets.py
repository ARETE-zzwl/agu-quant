"""Reusable widgets for the Sector Board page."""

from __future__ import annotations

import streamlit as st

from web.components.common import fmt_change_pct, color_change


def render_sector_table(sectors: list[dict], title: str = "行业板块") -> None:
    """Render a sortable sector ranking table."""
    if not sectors:
        st.info(f"暂无{title}数据")
        return

    st.markdown(f"#### {title}")

    rows = []
    for s in sectors:
        chg = s.get("change_pct", 0) or 0
        color = color_change(chg)
        rows.append({
            "排名": s.get("rank", "-"),
            "名称": s.get("name", ""),
            "涨跌幅": f'<span style="color:{color}">{fmt_change_pct(chg)}</span>',
            "上涨家数": s.get("up_count", ""),
            "下跌家数": s.get("down_count", ""),
            "领涨股": s.get("leader_stock", ""),
        })

    st.markdown(
        "| 排名 | 名称 | 涨跌幅 | 上涨 | 下跌 | 领涨股 |\n"
        "|------|------|--------|------|------|--------|\n"
        + "\n".join(
            f"| {r['排名']} | {r['名称']} | {r['涨跌幅']} | {r['上涨家数']} | {r['下跌家数']} | {r['领涨股']} |"
            for r in rows[:50]
        ),
        unsafe_allow_html=True,
    )


def render_concept_table(concepts: list[dict]) -> None:
    """Render concept sector ranking table."""
    if not concepts:
        st.info("暂无概念板块数据")
        return

    st.markdown("#### 概念板块 TOP20")

    header_cols = st.columns([1, 2, 1, 1, 1, 1])
    for c, label in zip(header_cols, ["排名", "概念名称", "涨跌幅", "上涨", "下跌", "领涨股"]):
        c.markdown(f"**{label}**")

    for i, c in enumerate(concepts[:20]):
        cols = st.columns([1, 2, 1, 1, 1, 1])
        chg = c.get("change_pct", 0) or 0
        color = color_change(chg)
        cols[0].markdown(str(i + 1))
        cols[1].markdown(c.get("name", ""))
        cols[2].markdown(f'<span style="color:{color}">{fmt_change_pct(chg)}</span>', unsafe_allow_html=True)
        cols[3].markdown(str(c.get("up_count", "")))
        cols[4].markdown(str(c.get("down_count", "")))
        cols[5].markdown(c.get("leader_stock", ""))
