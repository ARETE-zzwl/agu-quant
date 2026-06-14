"""缠论AI Agent — 分型 · 笔 · 中枢 · 买卖点 · 回测."""

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from web.components.common import inject_css
from tradingagents.chan import analyze_chan, run_chan_backtest

st.set_page_config(page_title="缠论Agent", page_icon="🧩", layout="wide", initial_sidebar_state="expanded")
inject_css()

st.markdown(
    '<div style="margin-bottom:0.5rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">🧩 缠论AI Agent</span>'
    '<span style="color:#666;font-size:0.85rem;margin-left:0.8rem;">'
    '分型 · 笔 · 中枢 · 背驰 · 买卖点 · 策略回测</span></div>',
    unsafe_allow_html=True,
)

st.caption("本页采用可回测的简化缠论规则。信号用于研究和模拟盘，不构成投资建议。")


@st.cache_data(ttl=60, show_spinner=False)
def load_chan_data(code: str, end_date: str):
    from tradingagents.dataflows.a_stock import _load_ohlcv_astock, _tencent_quote

    df = _load_ohlcv_astock(code, end_date)
    quote = {}
    try:
        quote = _tencent_quote([code]).get(code, {})
    except Exception:
        quote = {}
    if df.empty:
        return df, quote

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    price = float(quote.get("price", 0) or 0)
    today = pd.Timestamp(datetime.now().date())
    if price > 0:
        if df["Date"].iloc[-1] == today:
            i = df.index[-1]
            df.loc[i, "Close"] = price
            df.loc[i, "High"] = max(float(df.loc[i, "High"]), price)
            df.loc[i, "Low"] = min(float(df.loc[i, "Low"]), price)
        elif df["Date"].iloc[-1] < today:
            last_close = float(df["Close"].iloc[-1])
            df = pd.concat(
                [
                    df,
                    pd.DataFrame(
                        [{
                            "Date": today,
                            "Open": float(quote.get("open", last_close) or last_close),
                            "High": max(float(quote.get("high", price) or price), price),
                            "Low": min(float(quote.get("low", price) or price), price),
                            "Close": price,
                            "Volume": float(df["Volume"].tail(20).mean()),
                        }]
                    ),
                ],
                ignore_index=True,
            )
    return df, quote


def resample_ohlcv(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if period == "D":
        return df
    data = df.copy()
    data = data.set_index(pd.to_datetime(data["Date"]).dt.normalize()).sort_index()
    rule = "W-FRI" if period == "W" else "M"
    out = pd.DataFrame(
        {
            "Open": data["Open"].resample(rule).first(),
            "High": data["High"].resample(rule).max(),
            "Low": data["Low"].resample(rule).min(),
            "Close": data["Close"].resample(rule).last(),
            "Volume": data["Volume"].resample(rule).sum(),
        }
    ).dropna()
    out["Date"] = out.index
    return out.reset_index(drop=True)


def plot_chan(df: pd.DataFrame, analysis: dict):
    data = analysis.get("df")
    if data is None or data.empty:
        data = df.copy()
        data["Date"] = pd.to_datetime(data["Date"]).dt.normalize()
        data = data.set_index("Date").sort_index()

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="K线",
            increasing_line_color="#ef4444",
            decreasing_line_color="#22c55e",
        )
    )

    for center in analysis.get("centers", [])[-5:]:
        x0 = data.index[min(center["start_idx"], len(data) - 1)]
        x1 = data.index[min(center["end_idx"], len(data) - 1)]
        fig.add_shape(
            type="rect", x0=x0, x1=x1, y0=center["low"], y1=center["high"],
            fillcolor="rgba(249,115,22,0.12)", line=dict(color="rgba(249,115,22,0.55)", width=1),
            layer="below",
        )

    for stroke in analysis.get("strokes", []):
        color = "#ef4444" if stroke["direction"] == "up" else "#22c55e"
        fig.add_trace(
            go.Scatter(
                x=[stroke["start_date"], stroke["end_date"]],
                y=[stroke["start_price"], stroke["end_price"]],
                mode="lines",
                line=dict(color=color, width=2),
                name="笔",
                showlegend=False,
            )
        )

    top_x, top_y, bot_x, bot_y = [], [], [], []
    for f in analysis.get("fractals", [])[-80:]:
        if f["kind"] == "top":
            top_x.append(f["date"]); top_y.append(f["price"])
        else:
            bot_x.append(f["date"]); bot_y.append(f["price"])
    fig.add_trace(go.Scatter(x=top_x, y=top_y, mode="markers", name="顶分型",
                             marker=dict(symbol="triangle-down", size=8, color="#f97316")))
    fig.add_trace(go.Scatter(x=bot_x, y=bot_y, mode="markers", name="底分型",
                             marker=dict(symbol="triangle-up", size=8, color="#38bdf8")))

    latest = analysis.get("summary", {})
    if latest.get("action") in {"BUY", "WATCH_BUY"}:
        fig.add_trace(go.Scatter(
            x=[data.index[-1]], y=[float(data["Low"].iloc[-1]) * 0.98],
            mode="markers+text", text=[latest.get("action_cn", "")],
            textposition="bottom center", marker=dict(symbol="triangle-up", size=16, color="#22c55e"),
            name="Agent买点",
        ))
    elif latest.get("action") in {"SELL", "WATCH_SELL"}:
        fig.add_trace(go.Scatter(
            x=[data.index[-1]], y=[float(data["High"].iloc[-1]) * 1.02],
            mode="markers+text", text=[latest.get("action_cn", "")],
            textposition="top center", marker=dict(symbol="triangle-down", size=16, color="#ef4444"),
            name="Agent卖点",
        ))

    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0c0c0c", plot_bgcolor="#0c0c0c",
        height=560, margin=dict(l=0, r=0, t=24, b=0), xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02, x=0),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)
    return fig


def metric_pct(v: float) -> str:
    return f"{v * 100:.1f}%"


@st.cache_data(ttl=300, show_spinner=False)
def generate_ai_chan_comment(
    code: str,
    period_label: str,
    summary: dict,
    signals: list[dict],
    backtest: dict,
    llm_provider: str,
    quick_model: str,
    deep_model: str,
) -> str:
    from langchain_core.messages import HumanMessage
    from tradingagents.llm_clients import create_llm_client

    signal_text = "\n".join(
        f"- {s['type']} {('买点' if s['side'] == 'buy' else '卖点')} 强度{s['strength']}: {s['reason']}"
        for s in signals[:5]
    ) or "- 当前没有明确买卖点"
    reasons = "\n".join(f"- {r}" for r in summary.get("reasons", [])[:5])
    prompt = f"""
你是A股交易辅助Agent，只能基于给定数据做风控型解读，不能承诺收益。

股票: {code}
分析级别: {period_label}
规则动作: {summary.get('action_cn')}，评分: {summary.get('score')}/100
现价: {summary.get('price')}，止损: {summary.get('stop_loss')}，止盈: {summary.get('take_profit')}
结构理由:
{reasons}
缠论信号:
{signal_text}
回测结果:
- 总收益: {backtest.get('total_return', 0) * 100:.1f}%
- 年化: {backtest.get('annual_return', 0) * 100:.1f}%
- 最大回撤: {backtest.get('max_drawdown', 0) * 100:.1f}%
- 胜率: {backtest.get('win_rate', 0) * 100:.1f}%
- 完成交易: {backtest.get('total_trades', 0)}

请输出不超过220字的中文交易建议，必须包含：
1. 当前更适合观察、试买、持有、减仓还是平仓；
2. 关键触发条件；
3. 最大风险点。
不要使用“必涨”“稳赚”等表述。
""".strip()
    client = create_llm_client(
        provider=llm_provider or "deepseek",
        model=quick_model or deep_model or "deepseek-chat",
        base_url="https://api.deepseek.com" if (llm_provider or "deepseek") == "deepseek" else None,
    )
    llm = client.get_llm()
    return llm.invoke([HumanMessage(content=prompt)]).content.strip()


c1, c2, c3, c4, c5 = st.columns([1.4, 1, 1, 1, 1])
code = c1.text_input("股票代码", "600519")
period_label = c2.selectbox("分析级别", ["日线", "周线", "月线"], index=0)
period = {"日线": "D", "周线": "W", "月线": "M"}[period_label]
lookback = c3.selectbox("显示K线", [120, 250, 500], index=1)
min_stroke = c4.selectbox("成笔间隔", [3, 5, 7], index=1)
strategy = c5.selectbox(
    "回测策略",
    ["combined", "t1_divergence", "t2_confirm", "t3_breakout"],
    format_func=lambda x: {
        "combined": "综合买卖点",
        "t1_divergence": "一买/一卖 背驰",
        "t2_confirm": "二买/二卖 确认",
        "t3_breakout": "三买/三卖 突破",
    }[x],
)

if st.button("运行缠论Agent", type="primary", width="stretch"):
    load_chan_data.clear()

end_date = datetime.now().strftime("%Y-%m-%d")
raw_df, quote = load_chan_data(code.strip(), end_date)
if raw_df.empty:
    st.error("无法获取K线数据")
    st.stop()

df = resample_ohlcv(raw_df, period).tail(lookback)
analysis = analyze_chan(df, min_stroke_bars=min_stroke)
summary = analysis["summary"]

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric(quote.get("name", code), f"{summary.get('price', 0):.2f}",
          delta=f"{quote.get('change_pct', 0):+.2f}%" if quote else None)
m2.metric("Agent动作", summary.get("action_cn", "等待"), delta=f"{summary.get('score', 0)}/100", delta_color="off")
m3.metric("分型", len(analysis.get("fractals", [])))
m4.metric("笔", len(analysis.get("strokes", [])))
m5.metric("中枢", len(analysis.get("centers", [])))
m6.metric("止损/止盈", f"{summary.get('stop_loss', 0):.2f} / {summary.get('take_profit', 0):.2f}")

st.plotly_chart(plot_chan(df, analysis), width="stretch", config={"displayModeBar": False})

left, right = st.columns([1.1, 1])
with left:
    st.markdown("### Agent分析")
    for reason in summary.get("reasons", []):
        st.write(f"- {reason}")
    for note in summary.get("risk_notes", []):
        st.caption(f"风险提示: {note}")

    if analysis.get("signals"):
        sig_rows = []
        for s in analysis["signals"]:
            sig_rows.append({
                "类型": s["type"],
                "方向": "买点" if s["side"] == "buy" else "卖点",
                "强度": s["strength"],
                "解释": s["reason"],
            })
        st.dataframe(pd.DataFrame(sig_rows), width="stretch", hide_index=True)
    else:
        st.info("当前没有明确缠论买卖点，等待分型/笔/中枢进一步确认")

with right:
    st.markdown("### 策略回测")
    bt = run_chan_backtest(df, strategy=strategy, min_stroke_bars=min_stroke)
    b1, b2, b3, b4, b5 = st.columns(5)
    b1.metric("总收益", metric_pct(bt["total_return"]))
    b2.metric("年化", metric_pct(bt["annual_return"]))
    b3.metric("夏普", f"{bt['sharpe_ratio']:.2f}")
    b4.metric("最大回撤", metric_pct(bt["max_drawdown"]))
    b5.metric("胜率", metric_pct(bt["win_rate"]))

    eq = bt.get("equity_curve")
    if eq is not None and len(eq) > 1:
        st.line_chart(pd.DataFrame({"策略净值": eq.values}, index=eq.index))
    trades = bt.get("trades", [])[-12:]
    if trades:
        st.dataframe(pd.DataFrame(trades), width="stretch", hide_index=True, height=280)
    else:
        st.caption("该策略在当前区间内没有完成交易")

st.markdown("### AI交易解读")
if st.button("生成AI交易建议", type="secondary"):
    with st.spinner("AI Agent 正在结合缠论结构和回测结果生成建议..."):
        try:
            st.session_state["chan_ai_comment"] = generate_ai_chan_comment(
                code.strip(),
                period_label,
                summary,
                analysis.get("signals", []),
                {
                    "total_return": bt.get("total_return", 0),
                    "annual_return": bt.get("annual_return", 0),
                    "max_drawdown": bt.get("max_drawdown", 0),
                    "win_rate": bt.get("win_rate", 0),
                    "total_trades": bt.get("total_trades", 0),
                },
                st.session_state.get("llm_provider", "deepseek"),
                st.session_state.get("quick_think_llm", "deepseek-chat"),
                st.session_state.get("deep_think_llm", "deepseek-chat"),
            )
        except Exception as e:
            st.session_state["chan_ai_comment"] = f"AI解读失败，已保留规则Agent建议。原因: {e}"

if st.session_state.get("chan_ai_comment"):
    st.info(st.session_state["chan_ai_comment"])

st.markdown("---")
st.caption("缠论Agent采用可回测的简化规则：三K分型、交替成笔、三笔重叠中枢、MACD力度背驰近似。")
