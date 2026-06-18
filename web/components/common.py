"""Shared CSS, navigation, and page utilities for the multi-page Streamlit app."""

from __future__ import annotations

import streamlit as st

# ── CSS Injection ───────────────────────────────────────────────────────────────

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;600;700;800&display=swap');

:root {
    --ta-bg: #0b0f12;
    --ta-surface: #12171a;
    --ta-surface-2: #171d21;
    --ta-border: #263036;
    --ta-border-strong: #3b4850;
    --ta-text: #f4efe6;
    --ta-muted: #9aa4ad;
    --ta-subtle: #68737d;
    --ta-accent: #f97316;
    --ta-accent-2: #2dd4bf;
    --ta-blue: #60a5fa;
    --ta-green: #22c55e;
    --ta-red: #ef4444;
}

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
    background: var(--ta-surface-2) !important;
    border: 1px solid var(--ta-border) !important;
    border-radius: 6px !important;
    width: 32px !important;
    height: 32px !important;
}

html, body, [class*="css"] {
    font-family: 'Noto Sans SC', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    letter-spacing: 0 !important;
}

.stApp {
    background: linear-gradient(180deg, #0b0f12 0%, #0d1113 100%);
    color: var(--ta-text);
}

section[data-testid="stSidebar"] {
    background: #0f1417;
    border-right: 1px solid #202930;
}

.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 2rem !important;
}

/* Page primitives */
.ta-page-header {
    border-bottom: 1px solid var(--ta-border);
    margin: 0 0 1rem 0;
    padding: 0.25rem 0 1rem 0;
    position: relative;
    overflow: hidden;
}
.ta-page-header::after {
    content: "";
    position: absolute;
    top: 0.25rem;
    right: 0;
    width: min(26rem, 42%);
    height: 100%;
    opacity: 0.18;
    pointer-events: none;
    background:
        linear-gradient(90deg, transparent, var(--ta-bg) 92%),
        repeating-linear-gradient(0deg, transparent 0 9px, rgba(45, 212, 191, 0.3) 9px 10px),
        repeating-linear-gradient(90deg, rgba(249, 115, 22, 0.35) 0 1px, transparent 1px 18px);
}
.ta-eyebrow {
    color: var(--ta-accent-2);
    font-size: 0.78rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
}
.ta-page-title {
    color: var(--ta-text);
    font-size: 1.55rem;
    font-weight: 800;
    line-height: 1.25;
    margin: 0;
}
.ta-page-subtitle {
    color: var(--ta-muted);
    font-size: 0.92rem;
    line-height: 1.6;
    margin-top: 0.35rem;
}
.ta-panel {
    background: var(--ta-surface);
    border: 1px solid var(--ta-border);
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1rem;
}
.ta-panel-title {
    color: var(--ta-text);
    font-weight: 700;
    font-size: 1rem;
    margin-bottom: 0.35rem;
}
.ta-muted {
    color: var(--ta-muted);
    font-size: 0.86rem;
    line-height: 1.55;
}
.ta-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.75rem;
}
.ta-badge {
    border: 1px solid var(--ta-border);
    border-radius: 999px;
    color: #d7dee4;
    background: #10171b;
    font-size: 0.78rem;
    padding: 0.2rem 0.55rem;
}
.ta-plan-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
    margin: 0.25rem 0 1rem 0;
}
.ta-plan-card {
    background: #11181c;
    border: 1px solid var(--ta-border);
    border-radius: 8px;
    padding: 0.9rem;
}
.ta-plan-card strong {
    color: var(--ta-text);
    font-size: 1rem;
}
.ta-plan-price {
    color: var(--ta-accent);
    font-size: 1.35rem;
    font-weight: 800;
    margin: 0.25rem 0;
}
.ta-status-good { color: var(--ta-green); }
.ta-status-warn { color: var(--ta-accent); }
.ta-status-bad { color: var(--ta-red); }
.ta-warning-strip {
    background: #172018;
    border: 1px solid #344829;
    border-radius: 8px;
    color: #edf5e7;
    font-weight: 700;
    padding: 0.85rem 1rem;
    margin-bottom: 1rem;
}

@media (max-width: 760px) {
    .ta-plan-grid { grid-template-columns: 1fr; }
    .ta-page-header::after { display: none; }
    .ta-page-title { font-size: 1.28rem; }
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
}

/* Metrics */
.stMetric label {
    color: var(--ta-muted) !important;
    font-size: 0.75rem !important;
    letter-spacing: 0 !important;
}
.stMetric [data-testid="stMetricValue"] {
    color: var(--ta-text) !important;
    font-weight: 700 !important;
    font-size: 1.28rem !important;
}

/* Progress */
.stProgress > div > div > div {
    background: var(--ta-accent) !important;
    border-radius: 2px !important;
}

/* Buttons */
button[kind="primary"] {
    background: var(--ta-accent) !important;
    border: 1px solid #fb923c !important;
    color: #140b04 !important;
    font-weight: 700 !important;
    font-size: 0.86rem !important;
    border-radius: 6px !important;
    transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease !important;
}
button[kind="primary"]:hover {
    background: #fb923c !important;
    border-color: #fed7aa !important;
    transform: translateY(-1px);
}
button[kind="secondary"] {
    background: var(--ta-surface-2) !important;
    border: 1px solid var(--ta-border) !important;
    color: #d5dde3 !important;
    border-radius: 6px !important;
    transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease !important;
}
button[kind="secondary"]:hover {
    background: #1c2429 !important;
    border-color: var(--ta-border-strong) !important;
    color: var(--ta-text) !important;
}
button:disabled {
    opacity: 0.45 !important;
}
button:focus-visible,
.stTextInput input:focus-visible,
.stNumberInput input:focus-visible,
.stDateInput input:focus-visible {
    outline: 2px solid var(--ta-accent-2) !important;
    outline-offset: 2px !important;
}

/* Expander and tabs */
.stExpander {
    border: 1px solid var(--ta-border) !important;
    border-radius: 8px !important;
    background: #101518 !important;
}
.stTabs [data-baseweb="tab"] {
    color: var(--ta-muted) !important;
    font-size: 0.86rem !important;
}
.stTabs [aria-selected="true"] {
    color: var(--ta-accent) !important;
    border-bottom-color: var(--ta-accent) !important;
}

/* Inputs */
.stTextInput input,
.stNumberInput input,
.stDateInput input {
    background: #101518 !important;
    border: 1px solid var(--ta-border) !important;
    color: #e8edf0 !important;
    border-radius: 6px !important;
}
.stTextInput input:focus,
.stNumberInput input:focus,
.stDateInput input:focus {
    border-color: var(--ta-accent) !important;
    box-shadow: 0 0 0 1px rgba(249, 115, 22, 0.25) !important;
}
.stSelectbox [data-baseweb="select"] {
    background: #101518 !important;
    border-color: var(--ta-border) !important;
    border-radius: 6px !important;
}
.stRadio [data-baseweb="radiogroup"] label {
    color: var(--ta-muted) !important;
}

/* Alerts */
div[data-testid="stAlert"] {
    background: #11181c !important;
    border: 1px solid var(--ta-border) !important;
    border-radius: 8px !important;
    color: #e6edf2 !important;
}
div[data-testid="stAlert"] p {
    color: #e6edf2 !important;
}

/* Dataframe */
.stDataFrame {
    border: 1px solid var(--ta-border);
    border-radius: 8px;
    overflow: hidden;
    font-size: 0.82rem !important;
}
.stDataFrame th {
    background: #151b1f !important;
    color: #b6c0c8 !important;
    font-weight: 700 !important;
    border-bottom: 1px solid var(--ta-border) !important;
}
.stDataFrame td {
    color: #dde5eb !important;
}

/* Metric cards */
div[data-testid="stMetric"] {
    background: var(--ta-surface);
    border: 1px solid var(--ta-border);
    border-radius: 8px;
    padding: 0.75rem 1rem;
}
div[data-testid="stMetric"]:hover {
    border-color: var(--ta-border-strong);
}

hr {
    border-color: var(--ta-border) !important;
    margin: 1rem 0 !important;
}
"""


def inject_css():
    """Inject shared dark-theme CSS. Call once at the top of every page."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def has_premium_access(required_plan: str = "supporter") -> bool:
    from tradingagents.auth import get_license_status
    from tradingagents.auth.plans import plan_allows
    from web.auth_session import is_admin

    if is_admin():
        return True
    status = get_license_status()
    return bool(status.get("valid")) and plan_allows(
        status.get("plan", "pro"),
        required_plan,
    )


def require_premium_page(page_name: str, required_plan: str = "supporter") -> None:
    """Stop rendering a paid page unless the current session is allowed."""
    if has_premium_access(required_plan):
        return

    from tradingagents.auth.plans import plan_label

    st.warning(f"{page_name} 需要{plan_label(required_plan)}或更高套餐。")
    st.page_link("pages/activate.py", label="前往登录 / 激活", use_container_width=True)
    st.stop()


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
