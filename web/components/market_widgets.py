"""Reusable widgets for the Market Dashboard page."""

from __future__ import annotations

import streamlit as st

from web.components.common import fmt_change_pct, fmt_amount, fmt_number, color_change


def render_index_card(
    name: str,
    price: float,
    change_pct: float,
    change_amt: float,
    subtitle: str = "",
) -> None:
    """Render a single index as a metric card."""
    delta_str = f"{fmt_change_pct(change_pct)}"
    delta_color = "off"  # Streamlit: normal=green for up, but we want red for up in CN
    st.metric(
        label=f"**{name}**" + (f"  _{subtitle}_" if subtitle else ""),
        value=f"{price:.2f}",
        delta=delta_str,
        delta_color=delta_color,
    )


def render_indices_row(indices: list[dict]) -> None:
    """Render a row of index cards."""
    if not indices:
        st.warning("暂无指数数据")
        return

    cols = st.columns(min(len(indices), 6))
    for i, idx in enumerate(indices[:6]):
        with cols[i]:
            render_index_card(
                name=idx.get("name", "—"),
                price=idx.get("price", 0),
                change_pct=idx.get("change_pct", 0),
                change_amt=idx.get("change_amt", 0),
            )


def render_breadth_panel(breadth: dict) -> None:
    """Render market breadth statistics."""
    if not breadth:
        st.warning("暂无涨跌统计")
        return

    total_up = breadth.get("total_up", 0)
    total_down = breadth.get("total_down", 0)
    total = total_up + total_down

    up_pct = (total_up / total * 100) if total > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("上涨家数", total_up)
    c2.metric("下跌家数", total_down)
    c3.metric("平盘家数", breadth.get("total_flat", 0))
    c4.metric("上涨占比", f"{up_pct:.1f}%")

    c5, c6 = st.columns(2)
    c5.metric("涨停家数", breadth.get("limit_up_count", 0))
    c6.metric("跌停家数", breadth.get("limit_down_count", 0))


def render_northbound_panel(hgt: float, sgt: float, total: float) -> None:
    """Render northbound capital flow panel."""
    direction = "流入" if total > 0 else "流出"
    signal_color = "#ff4444" if total > 0 else "#44bb44"

    c1, c2, c3 = st.columns(3)
    c1.metric("沪股通", f"{hgt:+.2f} 亿")
    c2.metric("深股通", f"{sgt:+.2f} 亿")
    c3.metric("北向合计", f"{total:+.2f} 亿")

    st.markdown(
        f'<span style="color:{signal_color}; font-weight:600;">'
        f"信号: 北向{'净流入 (看多)' if total > 0 else '净流出 (看空)'}"
        f"</span>",
        unsafe_allow_html=True,
    )


def render_hot_sectors_table(sectors: list[dict]) -> None:
    """Render top hot sectors table."""
    if not sectors:
        st.info("暂无板块数据")
        return

    rows = []
    for s in sectors[:10]:
        name = s.get("name", "")
        change_pct = s.get("change_pct", 0) or 0
        color = color_change(change_pct)
        rows.append({
            "板块": name,
            "涨跌幅": f'<span style="color:{color}">{fmt_change_pct(change_pct)}</span>',
            "领涨股": s.get("leader_stock", ""),
            "成交额": fmt_amount(s.get("amount", 0)),
        })

    st.markdown("#### 热门板块 TOP10")
    st.markdown(
        "| 板块 | 涨跌幅 | 领涨股 | 成交额 |\n"
        "|------|--------|--------|--------|\n"
        + "\n".join(
            f"| {r['板块']} | {r['涨跌幅']} | {r['领涨股']} | {r['成交额']} |"
            for r in rows
        ),
        unsafe_allow_html=True,
    )


def render_hot_stocks_table(stocks: list[dict]) -> None:
    """Render hot stocks with topic tags."""
    if not stocks:
        return

    st.markdown("#### 热门个股")

    header_cols = st.columns([1, 1, 1, 1, 2])
    header_labels = ["代码", "名称", "涨跌幅", "换手率", "题材标签"]
    for c, label in zip(header_cols, header_labels):
        c.markdown(f"**{label}**")

    for stock in stocks[:15]:
        cols = st.columns([1, 1, 1, 1, 2])
        code = stock.get("code", "")
        name = stock.get("name", "")
        chg = stock.get("change_pct", 0) or 0
        turnover = stock.get("turnover", 0) or 0
        reason = stock.get("reason", "")

        color = color_change(chg)
        cols[0].markdown(f"`{code}`")
        cols[1].markdown(name)
        cols[2].markdown(f'<span style="color:{color}">{fmt_change_pct(chg)}</span>', unsafe_allow_html=True)
        cols[3].markdown(f"{turnover:.1f}%")
        cols[4].markdown(f"<small>{reason}</small>" if reason else "", unsafe_allow_html=True)


def render_northbound_history_panel(history: list[tuple]) -> None:
    """Render northbound flow history table."""
    if not history:
        return

    st.markdown("#### 北向资金历史 (近20日)")
    total_sum = sum(h + s for _, h, s in history)
    avg_total = total_sum / len(history)

    rows = []
    for date_str, h, s in history:
        t = h + s
        style = "color:#ff4444" if t > 0 else "color:#44bb44"
        rows.append(
            f"| {date_str} | {h:+.1f} 亿 | {s:+.1f} 亿 | "
            f'<span style="{style}">{t:+.1f} 亿</span> |'
        )

    st.markdown(
        "| 日期 | 沪股通 | 深股通 | 净合计 |\n"
        "|------|--------|--------|--------|\n" + "\n".join(rows),
        unsafe_allow_html=True,
    )
    st.caption(f"20日平均净流量: {avg_total:+.1f} 亿")
