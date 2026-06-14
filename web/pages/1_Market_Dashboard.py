"""大盘看盘."""

from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from web.components.common import inject_css
from web.components.market_widgets import (
    render_indices_row, render_breadth_panel, render_northbound_panel,
    render_hot_sectors_table, render_hot_stocks_table, render_northbound_history_panel,
)

st.set_page_config(page_title="大盘看盘", page_icon="🏠", layout="wide", initial_sidebar_state="expanded")
inject_css()

now = datetime.now()
trading_note = "" if now.weekday() < 5 and 9 <= now.hour < 15 else " (非交易时段)"

st.markdown(
    f'<div style="margin-bottom:1rem;">'
    f'<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">🏠 大盘看盘</span>'
    f'<span style="color:#666;font-size:0.85rem;margin-left:0.8rem;">'
    f'{now.strftime("%Y-%m-%d %H:%M")}{trading_note}</span></div>',
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60, show_spinner=False)
def _load_indices():
    from tradingagents.dataflows.a_stock import get_market_indices
    return get_market_indices()


@st.cache_data(ttl=120, show_spinner=False)
def _load_breadth():
    from tradingagents.dataflows.a_stock import get_market_breadth
    return get_market_breadth()


@st.cache_data(ttl=60, show_spinner=False)
def _load_northbound():
    import re
    from tradingagents.dataflows.a_stock import get_northbound_flow
    text = get_northbound_flow("", include_history=True)
    result = {"hgt": 0.0, "sgt": 0.0, "total": 0.0, "history": []}
    m = re.search(r"HGT.*?=([\-\d.]+)亿.*?SGT.*?=([\-\d.]+)亿.*?Total=([\-\d.]+)亿", text)
    if m:
        result["hgt"] = float(m.group(1))
        result["sgt"] = float(m.group(2))
        result["total"] = float(m.group(3))
    for line in text.split("\n"):
        hm = re.match(r"\s*(\d{4}-\d{2}-\d{2}):\s*HGT=([\-\d.]+)\s*SGT=([\-\d.]+)", line)
        if hm:
            result["history"].append((hm.group(1), float(hm.group(2)), float(hm.group(3))))
    return result


@st.cache_data(ttl=120, show_spinner=False)
def _load_sectors():
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
def _load_hot_stocks():
    import re
    from tradingagents.dataflows.a_stock import get_hot_stocks
    text = get_hot_stocks(datetime.now().strftime("%Y-%m-%d"))
    results = []
    for line in text.split("\n"):
        m = re.match(r"(\d{6})\s+(\S+):\s+\+?([\d.]+)%\s+换手([\d.]+)%\s+成交额([\d.]+)\s+大单净量([\d\-.]+)\s*\|\s*(.+)", line)
        if m:
            results.append({"code": m.group(1), "name": m.group(2), "change_pct": float(m.group(3)),
                           "turnover": float(m.group(4)), "amount": float(m.group(5)),
                           "dde": float(m.group(6)), "reason": m.group(7).strip()})
    return results


# Indices
with st.spinner("加载指数..."):
    indices = _load_indices()
render_indices_row(indices)

# Breadth + Northbound
st.markdown("---")
ca, cb = st.columns(2)
with ca:
    st.markdown("#### 涨跌家数")
    with st.spinner("加载..."):
        breadth = _load_breadth()
    render_breadth_panel(breadth)
with cb:
    st.markdown("#### 北向资金")
    with st.spinner("加载..."):
        nb = _load_northbound()
    render_northbound_panel(nb["hgt"], nb["sgt"], nb["total"])

# Hot Sectors
st.markdown("---")
with st.spinner("加载行业板块..."):
    sectors = _load_sectors()
render_hot_sectors_table(sectors)

# Hot Stocks
st.markdown("---")
with st.spinner("加载热门个股..."):
    hot = _load_hot_stocks()
render_hot_stocks_table(hot)

# Northbound History
if nb.get("history"):
    st.markdown("---")
    render_northbound_history_panel(nb["history"])

st.markdown("---")
st.caption(f"数据: 东方财富 · 腾讯 · 同花顺 | {datetime.now().strftime('%H:%M:%S')}")
