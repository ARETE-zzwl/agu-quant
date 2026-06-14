"""股票监控 — 多周期K线 · 策略评分 · 多时间尺度因子."""

from datetime import datetime
from collections import Counter

import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from web.components.common import inject_css
from tradingagents.ranking.scoring_engine import ScoringEngine
from tradingagents.ranking.signal_engine import evaluate_stock_signal
from tradingagents.factors import ALL_FACTORS

st.set_page_config(page_title="股票监控", page_icon="📡", layout="wide", initial_sidebar_state="expanded")
inject_css()

st.markdown(
    '<div style="margin-bottom:0.5rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">📡 股票监控</span>'
    '<span style="color:#666;font-size:0.85rem;margin-left:0.8rem;">多周期K线 · 多时间尺度因子 · 买卖点</span></div>',
    unsafe_allow_html=True,
)

_KLINE_PERIODS = {"日K": "D", "周K": "W", "月K": "M"}
_FACTOR_WINDOWS = {"1周": 5, "2周": 10, "1月": 20, "3月": 60}

# ── Controls ─────────────────────────────────────────────────────────────────────

c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
ticker_input = c1.text_input("股票代码", "600519", placeholder="多个用逗号分隔")
codes = [c.strip() for c in ticker_input.split(",") if c.strip()]
kline_period = c2.selectbox("K线周期", list(_KLINE_PERIODS.keys()), index=0)
lookback = c3.selectbox("显示K线数", [60, 120, 250], index=1)
fw = c4.selectbox("因子时间尺度", list(_FACTOR_WINDOWS.keys()), index=2)

presets = ScoringEngine.get_presets()
strategy_labels = {p["key"]: p["label"] for p in presets}
strategy_keys = list(strategy_labels.keys())
strategy_idx = c5.selectbox("评估策略", range(len(strategy_keys)),
                            format_func=lambda i: strategy_labels[strategy_keys[i]],
                            index=list(strategy_keys).index("reversal_boll_mom")
                            if "reversal_boll_mom" in strategy_keys else 0)
selected_strategy = strategy_keys[strategy_idx]

end_date = datetime.now().strftime("%Y-%m-%d")
factor_days = _FACTOR_WINDOWS[fw]

# ── Data Loaders ─────────────────────────────────────────────────────────────────


@st.cache_data(ttl=120, show_spinner=False)
def load_ohlcv(code, end):
    from tradingagents.dataflows.a_stock import _load_ohlcv_astock
    df = _load_ohlcv_astock(code, end)
    if df.empty:
        return None
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    return df.set_index("Date").sort_index()


def resample_kline(df, period):
    """Resample OHLCV to weekly or monthly."""
    if period == "D":
        return df
    rule = {"W": "W-FRI", "M": "M"}[period]
    return pd.DataFrame({
        "Open": df["Open"].resample(rule).first(),
        "High": df["High"].resample(rule).max(),
        "Low": df["Low"].resample(rule).min(),
        "Close": df["Close"].resample(rule).last(),
        "Volume": df["Volume"].resample(rule).sum(),
    }).dropna()


@st.cache_data(ttl=120, show_spinner=False)
def compute_factors_multi_window(code, end, strategy_key, factor_window_days):
    """Compute factors across active dates within lookback window."""
    from tradingagents.dataflows.a_stock import _load_ohlcv_astock  # noqa: F811
    from tradingagents.factors import ALL_FACTORS

    df = _load_ohlcv_astock(code, end)
    if df.empty:
        return (None,) * 11
    df = df.set_index(pd.to_datetime(df["Date"]).dt.normalize()).sort_index()

    strategy_catalog = ScoringEngine.get_strategies()
    cfg = strategy_catalog.get(strategy_key, strategy_catalog["balanced"])
    weights = cfg["weights"]
    label = cfg["label"]

    cat_weight = {
        "价值估值": weights.get("value_quality", 0.2),
        "动量趋势": weights.get("momentum", 0.2),
        "质量成长": weights.get("value_quality", 0.2),
        "资金流动": weights.get("money_flow", 0.2),
        "波动风险": weights.get("sentiment", 0.2),
        "情绪行为": weights.get("sentiment", 0.2),
        "技术形态": weights.get("momentum", 0.2),
        "复合联动": weights.get("value_quality", 0.2),
    }

    # Cutoff: only consider data within factor_window_days of the end date
    cutoff = df.index[-1] - pd.Timedelta(days=factor_window_days)
    active_df = df[df.index >= cutoff]
    recent_df = df.tail(factor_window_days)

    # Compute factor on active date range AND on sub-periods for trend
    def score_on_df(sub_df):
        signals = {}
        w_score, buy, sell = 0.0, 0, 0
        for name, f in ALL_FACTORS.items():
            try:
                s = f.compute_series(sub_df)
                sig = f.signal(sub_df)
                val = float(s.dropna().iloc[-1]) if len(s.dropna()) > 0 else 0
                w = cat_weight.get(f.category, 0.2)
                signals[name] = {"signal": sig, "value": round(val, 4),
                                 "category": f.category, "weight": round(w, 2),
                                 "contribution": round(val * w, 2)}
                if sig == "BUY":
                    w_score += w
                    buy += 1
                elif sig == "SELL":
                    w_score -= w
                    sell += 1
            except:
                signals[name] = {"signal": "ERR", "value": 0, "category": f.category,
                                 "weight": 0.2, "contribution": 0}
        return signals, w_score, buy, sell

    signals, w_score, buy_cnt, sell_cnt = score_on_df(recent_df)

    # Multi-window trend: split recent_df into halves for momentum
    mid = len(recent_df) // 2
    if mid >= 5:
        _, ws_early, b_early, s_early = score_on_df(recent_df.iloc[:mid])
        _, ws_late, b_late, s_late = score_on_df(recent_df.iloc[mid:])
        score_trend = ws_late - ws_early
        buy_trend = b_late - b_early
        sell_trend = s_late - s_early
    else:
        score_trend = buy_trend = sell_trend = 0

    unified_signal = evaluate_stock_signal(
        df,
        strategy_key=strategy_key,
        factor_window_days=factor_window_days,
    )

    return (
        df, signals, w_score, buy_cnt, sell_cnt, label, weights,
        score_trend, buy_trend, sell_trend, unified_signal,
    )


# ── Render ───────────────────────────────────────────────────────────────────────

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Resolve names
try:
    from tradingagents.dataflows.a_stock import _tencent_quote
    quotes = _tencent_quote(codes)
except:
    quotes = {}

for code in codes:
    stock_name = quotes.get(code, {}).get("name", "") if quotes else ""
    result = compute_factors_multi_window(code, end_date, selected_strategy, factor_days)
    if result is None or result[0] is None:
        st.error(f"{code}: 无法获取数据")
        continue

    orig_df, signals, w_score, buy_cnt, sell_cnt, strat_label, strat_weights, \
        score_trend, buy_trend, sell_trend, unified_signal = result

    # Resample K-line
    df_kline = resample_kline(orig_df, _KLINE_PERIODS[kline_period]).tail(lookback)
    total_f = len(signals)
    score_norm = unified_signal.get("score", round(w_score / max(total_f * 0.2, 0.01) * 100))

    # ── K-line Chart ──────────────────────────────────────────────────────────

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.7, 0.3])

    fig.add_trace(go.Candlestick(
        x=df_kline.index, open=df_kline["Open"], high=df_kline["High"],
        low=df_kline["Low"], close=df_kline["Close"], name=code,
        increasing_line_color="#ef4444", decreasing_line_color="#22c55e",
    ), row=1, col=1)

    # MAs
    ma20 = df_kline["Close"].rolling(20).mean()
    ma60 = df_kline["Close"].rolling(60).mean()
    if len(df_kline) >= 20:
        fig.add_trace(go.Scatter(x=df_kline.index, y=ma20, name="MA20",
                                  line=dict(color="#fbbf24", width=1)), row=1, col=1)
    if len(df_kline) >= 60:
        fig.add_trace(go.Scatter(x=df_kline.index, y=ma60, name="MA60",
                                  line=dict(color="#3b82f6", width=1)), row=1, col=1)
    # Bollinger
    if len(df_kline) >= 20:
        std20 = df_kline["Close"].rolling(20).std()
        bb_up = ma20 + 2 * std20
        bb_lo = ma20 - 2 * std20
        fig.add_trace(go.Scatter(x=df_kline.index, y=bb_up, line=dict(color="#555", width=0.5),
                                  showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_kline.index, y=bb_lo, line=dict(color="#555", width=0.5),
                                  fill="tonexty", fillcolor="rgba(128,128,128,0.05)",
                                  showlegend=False), row=1, col=1)

    # Volume
    vol_colors = ["#ef4444" if df_kline["Close"].iloc[i] >= df_kline["Open"].iloc[i]
                  else "#22c55e" for i in range(len(df_kline))]
    fig.add_trace(go.Bar(x=df_kline.index, y=df_kline["Volume"], marker_color=vol_colors,
                          showlegend=False), row=2, col=1)

    # Strategy signal marker
    recent = df_kline.tail(30)
    action = unified_signal.get("action", "NEUTRAL")
    if action in {"BUY", "ADD"} and len(recent) > 0:
        fig.add_trace(go.Scatter(
            x=[recent["Low"].idxmin()], y=[float(recent["Low"].min()) * 0.97],
            mode="markers+text", text=["<b>买</b>"], textposition="bottom center",
            marker=dict(symbol="triangle-up", size=16, color="#00ff88"),
            textfont=dict(color="#00ff88", size=12), name=f"{strat_label}:买入",
        ), row=1, col=1)
    elif action in {"REDUCE", "TAKE_PROFIT", "STOP_LOSS", "EXIT", "AVOID"} and len(recent) > 0:
        fig.add_trace(go.Scatter(
            x=[recent["High"].idxmax()], y=[float(recent["High"].max()) * 1.03],
            mode="markers+text", text=["<b>卖</b>"], textposition="top center",
            marker=dict(symbol="triangle-down", size=16, color="#ff4444"),
            textfont=dict(color="#ff4444", size=12), name=f"{strat_label}:卖出",
        ), row=1, col=1)

    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0c0c0c", plot_bgcolor="#0c0c0c",
        height=520, margin=dict(l=0, r=0, t=25, b=0),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)

    # ── Metrics Row ───────────────────────────────────────────────────────────

    latest = df_kline.iloc[-1]
    chg = (latest["Close"] / df_kline["Close"].iloc[-2] - 1) * 100 if len(df_kline) >= 2 else 0

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    display_name = f"{stock_name or code} ({kline_period})"
    m1.metric(display_name, f"{latest['Close']:.2f}", delta=f"{chg:+.1f}%")
    m2.metric("策略评分", f"{score_norm}/100", delta=strat_label, delta_color="off")
    trend_icon = "↗" if score_trend > 0.5 else ("↘" if score_trend < -0.5 else "→")
    m3.metric("因子趋势", trend_icon, delta=f"{score_trend:+.1f}" if score_trend != 0 else "平稳", delta_color="off")
    signal_text = unified_signal.get("action_cn", "中性")
    m4.metric("策略信号", signal_text)
    m5.metric("买入因子", buy_cnt, delta=f"{buy_trend:+d}" if buy_trend else None)
    m6.metric("卖出因子", sell_cnt, delta=f"{sell_trend:+d}" if sell_trend else None)

    # Strategy weights
    st.markdown("#### 策略权重")
    wc = st.columns(5)
    for i, (k, v) in enumerate(strat_weights.items()):
        names = {"value_quality": "价值品质", "momentum": "动量趋势",
                 "money_flow": "资金流向", "sentiment": "市场情绪", "size": "市值规模"}
        wc[i].metric(names.get(k, k), f"{v:.0%}")
        wc[i].progress(v)

    st.plotly_chart(fig, use_container_width=True)

    # ── Unified Trading Signal ───────────────────────────────────────────────

    levels = unified_signal.get("levels", {})
    technical = unified_signal.get("technical", {})
    a1, a2, a3, a4, a5 = st.columns(5)
    a1.metric("操作建议", unified_signal.get("action_cn", "中性"),
              delta=f"置信度 {unified_signal.get('confidence', 0)}", delta_color="off")
    a2.metric("风险等级", unified_signal.get("risk_level", "—"))
    a3.metric("参考止损", levels.get("stop_loss", "—"))
    a4.metric("参考止盈", levels.get("take_profit", "—"))
    a5.metric("补仓观察价", levels.get("add_price", "—"))
    reason_text = "；".join(unified_signal.get("reasons", [])[:3])
    risk_text = "；".join(unified_signal.get("risk_notes", [])[:3])
    if reason_text:
        st.caption(f"信号依据: {reason_text}")
    if risk_text:
        st.warning(f"风控提示: {risk_text}")
    st.caption(
        f"技术状态: RSI {technical.get('rsi', '—')} · ATR {technical.get('atr_pct', '—')}% · "
        f"20日收益 {technical.get('ret20', '—')}% · 量比 {technical.get('volume_ratio', '—')}"
    )

    # ── Multi-timeframe Factor Detail ─────────────────────────────────────────

    with st.expander(f"📊 因子详情 ({strat_label}, {fw}尺度): 🟢{buy_cnt} / 🔴{sell_cnt} / {total_f-buy_cnt-sell_cnt}中性",
                     expanded=False):
        # Category breakdown
        cat_buy = Counter(s["category"] for s in signals.values() if s["signal"] == "BUY")
        cat_sell = Counter(s["category"] for s in signals.values() if s["signal"] == "SELL")

        st.markdown("#### 分类信号分布")
        ccols = st.columns(8)
        for i, (cat, cnt) in enumerate(sorted(cat_buy.items(), key=lambda x: -x[1])[:8]):
            ccols[i].metric(f"🟢{cat[:4]}", cnt)

        # Factor trend note
        if score_trend != 0:
            direction = "改善" if score_trend > 0 else "恶化"
            st.caption(f"📈 因子趋势: 近半段相比前半段 {direction} {abs(score_trend):.1f} 分")

        # Top weighted signals
        st.markdown("#### 策略高权重因子")
        weighted = sorted(signals.items(), key=lambda x: abs(x[1]["contribution"]), reverse=True)
        top_rows = []
        for n, s in weighted[:20]:
            icon = "🟢" if s["signal"] == "BUY" else ("🔴" if s["signal"] == "SELL" else "⚪")
            factor_obj = ALL_FACTORS.get(n)
            cn_name = factor_obj.name_cn if factor_obj and factor_obj.name_cn else n
            cn_desc = factor_obj.desc_cn if factor_obj and factor_obj.desc_cn else ""
            top_rows.append({
                "因子": cn_name, "英文名": n, "类别": s["category"],
                "权重": f'{s["weight"]:.0%}', "贡献": s["contribution"], "信号": icon,
                "解释": cn_desc[:40],
            })
        st.dataframe(pd.DataFrame(top_rows), use_container_width=True, hide_index=True)

        # Buy vs Sell side-by-side
        ca, cb = st.columns(2)
        with ca:
            st.markdown("**最强买入**")
            bu = [(n, s) for n, s in signals.items() if s["signal"] == "BUY"]
            bu.sort(key=lambda x: abs(x[1]["contribution"]), reverse=True)
            if bu:
                st.dataframe(pd.DataFrame([{"因子": n, "权重": f'{s["weight"]:.0%}',
                                             "贡献": s["contribution"]}
                                           for n, s in bu[:10]]),
                             use_container_width=True, hide_index=True)
            else:
                st.caption("无")
        with cb:
            st.markdown("**最强卖出**")
            se = [(n, s) for n, s in signals.items() if s["signal"] == "SELL"]
            se.sort(key=lambda x: abs(x[1]["contribution"]), reverse=True)
            if se:
                st.dataframe(pd.DataFrame([{"因子": n, "权重": f'{s["weight"]:.0%}',
                                             "贡献": s["contribution"]}
                                           for n, s in se[:10]]),
                             use_container_width=True, hide_index=True)
            else:
                st.caption("无")

    st.markdown("---")

st.caption(f"15套策略 · 80因子 · 多时间尺度 | {datetime.now().strftime('%H:%M:%S')}")
