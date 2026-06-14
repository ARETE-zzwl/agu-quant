"""Shared CSS, navigation, and page utilities for the multi-page Streamlit app."""

from __future__ import annotations

import streamlit as st

# ── CSS Injection ───────────────────────────────────────────────────────────────

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

#MainMenu, header[data-testid="stHeader"],
footer, div[data-testid="stDecoration"],
div[data-testid="stToolbar"] { display: none !important; }
button[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: fixed !important;
    top: 0.5rem !important;
    left: 0.5rem !important;
    z-index: 999999 !important;
    background: #1a1a1a !important;
    border: 1px solid #333 !important;
    border-radius: 6px !important;
    width: 32px !important;
    height: 32px !important;
}

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
.stApp { background: #0c0c0c; }
section[data-testid="stSidebar"] { background: #111; border-right: 1px solid #1e1e1e; }

/* -- Metrics -- */
.stMetric label { color: #888 !important; font-size: 0.75rem !important; letter-spacing: 0.02em; }
.stMetric [data-testid="stMetricValue"] { color: #f5f1eb !important; font-weight: 600 !important; font-size: 1.4rem !important; }

/* -- Progress -- */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #f97316, #fb923c) !important;
    border-radius: 2px !important;
}

/* -- Primary Button -- */
button[kind="primary"] {
    background: linear-gradient(135deg, #f97316, #ea580c) !important; border: none !important;
    font-weight: 600 !important; font-size: 0.85rem !important;
    border-radius: 6px !important; transition: all 0.15s ease !important;
}
button[kind="primary"]:hover { background: linear-gradient(135deg, #fb923c, #f97316) !important; }

/* -- Secondary Button -- */
button[kind="secondary"] {
    background: #1a1a1a !important; border: 1px solid #333 !important;
    color: #aaa !important; border-radius: 6px !important;
    transition: all 0.15s ease !important;
}
button[kind="secondary"]:hover { border-color: #555 !important; color: #f5f1eb !important; }

/* -- Expander -- */
.stExpander { border: 1px solid #222 !important; border-radius: 6px !important; }

/* -- Tabs -- */
.stTabs [data-baseweb="tab"] { color: #666 !important; font-size: 0.85rem !important; }
.stTabs [aria-selected="true"] { color: #f97316 !important; border-bottom-color: #f97316 !important; }

/* -- Inputs -- */
input[data-testid="stTextInputRootElement"] input, .stTextInput input {
    background: #1a1a1a !important; border: 1px solid #2a2a2a !important;
    color: #e5e5e5 !important; border-radius: 6px !important;
}
.stTextInput input:focus { border-color: #f97316 !important; box-shadow: none !important; }
.stDateInput input { background: #1a1a1a !important; border-color: #2a2a2a !important; color: #e5e5e5 !important; }
.stSelectbox [data-baseweb="select"] { background: #1a1a1a !important; border-radius: 6px !important; }
.stRadio [data-baseweb="radiogroup"] label { color: #999 !important; }

/* -- Dataframe -- */
.stDataFrame { font-size: 0.82rem !important; }
.stDataFrame th { background: #161616 !important; color: #777 !important; font-weight: 600 !important; border-bottom: 1px solid #222 !important; }
.stDataFrame td { color: #ddd !important; }

/* -- Metric cards -- */
div[data-testid="stMetric"] {
    background: #141414; border: 1px solid #1e1e1e;
    border-radius: 8px; padding: 0.75rem 1rem;
}
div[data-testid="stMetric"]:hover { border-color: #2a2a2a; }

/* -- Section divider -- */
hr { border-color: #1a1a1a !important; margin: 1rem 0 !important; }
"""


def inject_css():
    """Inject shared dark-theme CSS. Call once at the top of every page."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


# ── Data Helpers ────────────────────────────────────────────────────────────────

def fmt_change_pct(v: float) -> str:
    """Format a change percentage with +/- and % sign."""
    if v is None or v == 0:
        return "0.00%"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"


def fmt_amount(yi: float) -> str:
    """Format an amount in 亿元."""
    if yi is None:
        return "—"
    if abs(yi) >= 10000:
        return f"{yi/10000:.2f} 万亿"
    return f"{yi:.2f} 亿"


def fmt_number(v: float, decimals: int = 2) -> str:
    """Format a number, handling None."""
    if v is None:
        return "—"
    return f"{v:.{decimals}f}"


def fmt_volume(shou: int) -> str:
    """Format volume in 手."""
    if shou is None:
        return "—"
    if abs(shou) >= 10000:
        return f"{shou/10000:.1f} 万手"
    return f"{shou} 手"


def color_change(v: float) -> str:
    """Return CSS color for a price change."""
    if v is None or v == 0:
        return "#888"
    return "#ff4444" if v > 0 else "#44bb44"
