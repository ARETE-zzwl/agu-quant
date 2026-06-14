"""模拟盘 — A股真实规则 · T+1 · 涨跌停 · 实时行情."""

from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from web.components.common import inject_css
from tradingagents.ranking.scoring_engine import ScoringEngine
from tradingagents.ranking.signal_engine import evaluate_code_signal
from tradingagents.paper_trade import get_account, is_trading_time

st.set_page_config(page_title="模拟盘", page_icon="💰", layout="wide", initial_sidebar_state="expanded")
inject_css()


def _market_status() -> tuple[str, str]:
    if is_trading_time():
        return "交易中", "success"
    now = datetime.now()
    if now.weekday() >= 5:
        return "周末休市", "warning"
    if now.time().hour < 9:
        return "等待开盘 09:30", "info"
    if now.time().hour == 9 and now.time().minute < 30:
        return "集合竞价", "info"
    if now.time().hour == 12:
        return "午间休市", "info"
    return "已收盘", "warning"


@st.cache_data(ttl=180, show_spinner=False)
def load_position_signal(code, end_date, strategy_key, price, avg_cost, shares, sellable):
    return evaluate_code_signal(
        code,
        end_date,
        strategy_key=strategy_key,
        quote={"code": code, "price": price},
        position={"avg_cost": avg_cost, "shares": shares, "sellable": sellable},
    )


def _render_quote_panel(code: str):
    if not code:
        st.info("输入股票代码后显示行情和K线")
        return
    try:
        from tradingagents.dataflows.a_stock import _load_ohlcv_astock, _tencent_quote
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        norm_code = code.strip()
        quotes = _tencent_quote([norm_code])
        q = quotes.get(norm_code, {})
        df = _load_ohlcv_astock(norm_code, datetime.now().strftime("%Y-%m-%d"))
        if df.empty:
            st.warning("暂时无法获取K线数据")
            return

        df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
        df = df.set_index("Date").sort_index().tail(90)
        name = q.get("name", norm_code)

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.72, 0.28],
        )
        fig.add_trace(
            go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name=name,
                increasing_line_color="#ef4444", decreasing_line_color="#22c55e",
            ),
            row=1, col=1,
        )
        ma20 = df["Close"].rolling(20).mean()
        ma60 = df["Close"].rolling(60).mean()
        fig.add_trace(go.Scatter(x=df.index, y=ma20, name="MA20",
                                  line=dict(color="#fbbf24", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=ma60, name="MA60",
                                  line=dict(color="#60a5fa", width=1)), row=1, col=1)
        colors = ["#ef4444" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "#22c55e"
                  for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=colors,
                              showlegend=False), row=2, col=1)
        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#0c0c0c", plot_bgcolor="#0c0c0c",
            height=380, margin=dict(l=0, r=0, t=20, b=0), xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.02, x=0),
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=False)

        q1, q2, q3, q4 = st.columns(4)
        q1.metric(name, f"{q.get('price', df['Close'].iloc[-1]):.2f}",
                  delta=f"{q.get('change_pct', 0):+.2f}%")
        q2.metric("PE(TTM)", f"{q.get('pe_ttm', 0):.1f}" if q else "—")
        q3.metric("PB", f"{q.get('pb', 0):.2f}" if q else "—")
        q4.metric("市值(亿)", f"{q.get('mcap_yi', 0):.0f}" if q else "—")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    except Exception as exc:
        st.warning(f"行情加载失败: {exc}")


def _order_rows(orders):
    rows = []
    for o in reversed(orders):
        icon = {"filled": "✅", "rejected": "❌", "pending_t1": "⏳"}.get(o.status, "❓")
        action = "买入" if o.action == "BUY" else "卖出"
        rows.append({
            "时间": o.time,
            "操作": action,
            "代码": o.code,
            "价格": f"{o.price:.2f}",
            "数量": o.shares,
            "金额": f"{o.amount:,.0f}",
            "费用": f"{o.fee:.2f}",
            "状态": f"{icon} {o.status}",
            "说明": o.reason[:60],
        })
    return rows


def _equity_chart(acc):
    snapshots = acc.get_snapshots()
    if len(snapshots) < 2:
        st.caption("资产快照不足，后续交易日会自动形成资产曲线")
        return
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[s[0] for s in snapshots],
            y=[s[1] for s in snapshots],
            mode="lines+markers",
            name="总资产",
            line=dict(color="#f97316", width=2),
            fill="tozeroy",
            fillcolor="rgba(249,115,22,0.10)",
        )
    )
    fig.add_hline(y=acc.initial_cash, line=dict(color="#666", width=1, dash="dash"),
                  annotation_text="初始资金")
    fig.update_layout(template="plotly_dark", paper_bgcolor="#0c0c0c", plot_bgcolor="#0c0c0c",
                      height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


prefill = st.session_state.pop("paper_trade_prefill", None)
if prefill:
    st.session_state["trd_code"] = prefill.get("code", "")
    st.session_state["trd_action"] = prefill.get("action", "买入")
    st.session_state["trd_qty"] = prefill.get("qty", 100)

st.markdown(
    '<div style="margin-bottom:0.5rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">💰 模拟盘</span>'
    '<span style="color:#666;font-size:0.85rem;margin-left:0.8rem;">'
    'A股真实规则 · T+1 · 持仓信号 · 资产延续</span></div>',
    unsafe_allow_html=True,
)

acc = get_account("default")
acc.refresh_prices()
summary = acc.summary()
market_label, market_kind = _market_status()
market_open = market_kind == "success"

top = st.columns([1.2, 1, 1, 1, 1, 0.9])
top[0].metric("市场状态", market_label)
top[1].metric("总资产", f"{summary['total_equity']:,.0f}", delta=f"{summary['total_return']:+.1f}%")
top[2].metric("现金", f"{summary['cash']:,.0f}")
top[3].metric("持仓市值", f"{summary['market_value']:,.0f}")
top[4].metric("累计盈亏", f"{summary['total_pnl']:+,.0f}")
if top[5].button("刷新", width="stretch"):
    acc.refresh_prices()
    st.rerun()

if market_kind == "success":
    st.success("交易时段内，模拟下单将按实时行情和A股规则校验")
elif market_kind == "info":
    st.info("当前不在连续竞价时段，下单会按规则被拒绝")
else:
    st.warning("当前休市或已收盘，下单会按规则被拒绝")

tab_pos, tab_trade, tab_orders, tab_rules = st.tabs(["持仓信号", "下单交易", "资产委托", "规则管理"])

with tab_pos:
    st.markdown("### 持仓与系统信号")
    signal_presets = ScoringEngine.get_presets()
    signal_keys = [p["key"] for p in signal_presets]
    signal_labels = {p["key"]: p["label"] for p in signal_presets}
    default_signal_idx = signal_keys.index("balanced") if "balanced" in signal_keys else 0
    signal_strategy_idx = st.selectbox(
        "持仓信号策略",
        range(len(signal_keys)),
        format_func=lambda i: signal_labels[signal_keys[i]],
        index=default_signal_idx,
    )
    signal_strategy = signal_keys[signal_strategy_idx]

    if summary["positions"]:
        rows = []
        action_counts = {}
        end_date = datetime.now().strftime("%Y-%m-%d")
        for p in summary["positions"]:
            locked = p["shares"] - p["sellable"]
            sig = load_position_signal(
                p["code"], end_date, signal_strategy, p["price"], p["avg_cost"],
                p["shares"], p["sellable"],
            )
            action = sig.get("action_cn", "—")
            action_counts[action] = action_counts.get(action, 0) + 1
            levels = sig.get("levels", {})
            rows.append({
                "代码": p["code"],
                "名称": p["name"],
                "持有": f"{p['shares']}股",
                "可卖": f"{p['sellable']}股" + (f" 🔒{locked}" if locked > 0 else ""),
                "成本": p["avg_cost"],
                "现价": p["price"],
                "市值": f"{p['value']:,.0f}",
                "盈亏": f"{p['pnl']:+,.0f}",
                "盈亏%": f"{p['pnl_pct']:+.1f}%",
                "系统信号": action,
                "信号分": sig.get("score", "—"),
                "风险": sig.get("risk_level", "—"),
                "止损": levels.get("stop_loss", "—"),
                "止盈": levels.get("take_profit", "—"),
                "信号依据": "；".join(sig.get("reasons", [])[:2]),
            })

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("持仓数", len(rows))
        s2.metric("可卖市值", f"{sum(p['price'] * p['sellable'] for p in summary['positions']):,.0f}")
        s3.metric("需处理信号", action_counts.get("减仓", 0) + action_counts.get("止盈", 0)
                  + action_counts.get("止损/平仓", 0) + action_counts.get("平仓", 0))
        s4.metric("补仓信号", action_counts.get("补仓/加仓", 0))

        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=380)
        st.caption("🔒 表示T+1锁定；系统信号仅用于模拟盘管理和研究参考")

        p_codes = [f"{p['code']} {p['name']}" for p in summary["positions"]]
        pick = st.selectbox("选择持仓操作", p_codes)
        selected_pos = summary["positions"][p_codes.index(pick)]
        b1, b2, b3 = st.columns(3)
        if b1.button("填入卖出", width="stretch"):
            st.session_state["paper_trade_prefill"] = {
                "code": selected_pos["code"], "action": "卖出",
                "qty": max(100, int(selected_pos["sellable"] or selected_pos["shares"])),
            }
            st.rerun()
        if b2.button("填入加仓", width="stretch"):
            st.session_state["paper_trade_prefill"] = {
                "code": selected_pos["code"], "action": "买入", "qty": 100,
            }
            st.rerun()
        if b3.button("刷新持仓信号", width="stretch"):
            load_position_signal.clear()
            st.rerun()
    else:
        st.info("暂无持仓")

with tab_trade:
    st.markdown("### 下单交易")
    left, right = st.columns([1, 1.35])
    with left:
        with st.form("paper_trade_order"):
            trade_code = st.text_input("股票代码", key="trd_code", placeholder="例: 600519")
            trade_action = st.radio("方向", ["买入", "卖出"], horizontal=True, key="trd_action")
            c_qty, c_amt = st.columns(2)
            trade_shares = c_qty.number_input("数量(股)", value=100, step=100, min_value=100,
                                              key="trd_qty")
            trade_amount = c_amt.number_input("买入金额(元)", value=0, step=1000, min_value=0,
                                              key="trd_amt")
            submitted = st.form_submit_button("确认下单", type="primary", width="stretch")

        if submitted:
            if not market_open:
                st.error("当前非交易时间，无法下单")
            elif not trade_code:
                st.error("请输入股票代码")
            else:
                try:
                    amount = trade_amount if trade_action == "买入" and trade_amount > 0 else None
                    qty = None if amount else trade_shares
                    order = acc.buy(trade_code, shares=qty, amount=amount) if trade_action == "买入" \
                        else acc.sell(trade_code, shares=trade_shares)

                    if order.status == "filled":
                        st.success(f"{order.action} {order.code} {order.shares}股 @{order.price:.2f} "
                                   f"金额{order.amount:,.0f} 费用{order.fee:.2f}")
                        if order.reason:
                            st.caption(order.reason)
                    else:
                        st.error(f"委托失败: {order.reason}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"下单异常: {exc}")

    with right:
        _render_quote_panel(st.session_state.get("trd_code", ""))

with tab_orders:
    st.markdown("### 资产曲线")
    _equity_chart(acc)

    st.markdown("### 委托记录")
    recent = acc.orders[-40:]
    if recent:
        st.dataframe(pd.DataFrame(_order_rows(recent)), width="stretch", hide_index=True, height=360)
    else:
        st.caption("暂无委托记录")

with tab_rules:
    st.markdown("### 交易规则")
    r1, r2, r3, r4 = st.columns(4)
    r1.markdown("**T+1交割**\n\n当日买入，次交易日可卖")
    r2.markdown("**涨跌停**\n\n主板±10%，科创/创业±20%，ST±5%")
    r3.markdown("**交易时间**\n\n9:30-11:30，13:00-15:00")
    r4.markdown("**费用**\n\n印花税卖出收取，佣金最低5元")

    st.markdown("### 账户管理")
    st.caption(f"数据文件: {acc._file}")
    m1, m2 = st.columns(2)
    if m1.button("刷新行情并解锁T+1", width="stretch"):
        acc.refresh_prices()
        st.success("已刷新")
        st.rerun()
    if m2.button("重置账户", type="secondary", width="stretch"):
        acc.reset()
        st.rerun()

st.caption(
    "初始资金100万 · 关闭后持仓/资金/订单自动保存 · 重启自动恢复 "
    f"| {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
