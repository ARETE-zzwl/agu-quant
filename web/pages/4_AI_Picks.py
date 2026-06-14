"""AI 荐股 — 12套策略 + 自定义权重."""

from datetime import datetime
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from web.components.common import inject_css
from tradingagents.ranking.scoring_engine import ScoringEngine
from tradingagents.ranking.signal_engine import evaluate_code_signal
from tradingagents.ranking.recommendation_engine import run_one_click_recommendation

st.set_page_config(page_title="AI 荐股", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")
inject_css()

st.markdown(
    '<div style="margin-bottom:1rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">🧠 AI 荐股</span>'
    '<span style="color:#666;font-size:0.85rem;margin-left:0.8rem;">12套策略 + 自定义权重 · 量化评分 + AI 点评</span></div>',
    unsafe_allow_html=True,
)

# ── One-click Recommendation ────────────────────────────────────────────────────

with st.expander("🎯 一键推荐当下候选股", expanded=True):
    st.caption("自动选择高流动性股票池，回测筛选策略，再用当前行情和风控信号过滤。结果仅供研究和模拟盘参考。")
    oc1, oc2, oc3, oc4 = st.columns([1, 1, 1, 1])
    oc_universe = oc1.selectbox("股票池规模", [40, 60, 100], index=1)
    oc_period = oc2.selectbox("回测周期", [90, 180, 365], index=1, format_func=lambda d: f"近{d}天")
    oc_n = oc3.selectbox("推荐数量", [5, 10, 15], index=1)
    one_click = oc4.button("一键推荐", type="primary", use_container_width=True)

    if one_click:
        with st.status("一键推荐运行中...", expanded=True) as status:
            try:
                st.write("📡 获取高流动性股票池...")
                st.write("🧪 回测比较预设策略...")
                st.write("🧭 叠加当前信号和风险过滤...")
                result = run_one_click_recommendation(
                    universe_size=oc_universe,
                    recommend_n=oc_n,
                    lookback_days=oc_period,
                    top_pct=0.2,
                    rebalance_days=10,
                    max_positions=10,
                )
                st.session_state["one_click_picks"] = result
                status.update(label="✅ 一键推荐完成", state="complete")
            except Exception as exc:
                status.update(label="❌ 一键推荐失败", state="error")
                st.error(f"一键推荐失败: {exc}")

    oc_result = st.session_state.get("one_click_picks")
    if oc_result:
        best = oc_result["best_strategy"]
        mt = best["metrics"]
        for note in oc_result.get("notes", []):
            st.caption(f"说明: {note}")
        st.markdown("#### 当前回测胜出策略")
        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("策略", best["label"])
        b2.metric("目标分", f"{mt['objective_score']:.1f}")
        b3.metric("年化收益", f"{mt['annual_return']*100:.1f}%")
        b4.metric("夏普", f"{mt['sharpe_ratio']:.2f}")
        b5.metric("最大回撤", f"{mt['max_drawdown']*100:.1f}%")

        recs = oc_result.get("recommendations", [])
        if recs:
            st.markdown("#### 当下候选股")
            display_rows = []
            for i, r in enumerate(recs, start=1):
                display_rows.append({
                    "排名": i,
                    "代码": r["代码"],
                    "名称": r["名称"],
                    "操作": r["操作"],
                    "综合分": r["综合分"],
                    "信号分": r["信号分"],
                    "风险": r["风险"],
                    "现价": r["现价"],
                    "涨跌幅%": f"{r['涨跌幅%']:+.1f}%",
                    "PE": f"{r['PE']:.1f}" if r["PE"] > 0 else "—",
                    "止损": r["止损"],
                    "止盈": r["止盈"],
                    "理由": r["理由"],
                    "风险提示": r["风险提示"],
                })
            st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
            st.session_state["picks_data"] = [
                {
                    "code": r["代码"],
                    "name": r["名称"],
                    "_score": r["综合分"],
                    "change_pct": r["涨跌幅%"],
                    "_signal": {
                        "action_cn": r["操作"],
                        "score": r["信号分"],
                        "risk_level": r["风险"],
                        "levels": {"stop_loss": r["止损"], "take_profit": r["止盈"]},
                        "reasons": [r["理由"]],
                    },
                }
                for r in recs
            ]
            st.session_state["picks_strategy"] = best["key"]
        else:
            st.warning("当前没有通过严格过滤的候选股。可以扩大股票池或缩短回测周期，但不要为了凑数量放松风控。")

        with st.expander("查看策略回测排名", expanded=False):
            st.dataframe(pd.DataFrame(oc_result["strategy_rows"]), use_container_width=True, hide_index=True)

# ── Strategy Selection ───────────────────────────────────────────────────────────

MODE_PRESET = "预设策略"
MODE_CUSTOM = "自定义策略"

mode = st.radio("模式", [MODE_PRESET, MODE_CUSTOM], horizontal=True)

if mode == MODE_PRESET:
    presets = ScoringEngine.get_presets()
    strategy_catalog = ScoringEngine.get_strategies()
    labels = [f"**{p['label']}** — _{p['desc']}_" for p in presets]
    keys = [p["key"] for p in presets]

    c1, c2, c3 = st.columns([3, 1, 1])
    si = c1.selectbox("选择策略", range(len(labels)), format_func=lambda i: labels[i])
    selected_strategy = keys[si]
    top_n = c2.selectbox("推荐数量", [10, 15, 20, 30], index=1)
    go = c3.button("🚀 开始扫描", type="primary", use_container_width=True)

    strategy_weights = strategy_catalog[selected_strategy]["weights"]
    strategy_filters = strategy_catalog[selected_strategy].get("filters", {})
    strategy_key = selected_strategy

else:
    st.markdown("#### 五因子权重 (之和自动归一化)")
    wc = st.columns(5)
    w_vq = wc[0].slider("价值品质", 0, 100, 20, 5, key="w_vq",
                         help="PE/PB/ROE 综合 — 越低PE/越低PB/越高ROE分越高")
    w_mo = wc[1].slider("动量趋势", 0, 100, 20, 5, key="w_mo",
                         help="涨跌幅 + 换手率 + 振幅 — 短期强势")
    w_mf = wc[2].slider("资金流向", 0, 100, 20, 5, key="w_mf",
                         help="主力净流入 + 成交额 — 跟随大资金")
    w_se = wc[3].slider("市场情绪", 0, 100, 20, 5, key="w_se",
                         help="换手活跃度 + 涨幅关注度 — 热度指标")
    w_sz = wc[4].slider("市值规模", 0, 100, 20, 5, key="w_sz",
                         help="总市值 — 大盘股稳定性")

    total_w = w_vq + w_mo + w_mf + w_se + w_sz
    if total_w == 0:
        total_w = 1
    custom_weights = {
        "value_quality": w_vq / total_w,
        "momentum": w_mo / total_w,
        "money_flow": w_mf / total_w,
        "sentiment": w_se / total_w,
        "size": w_sz / total_w,
    }

    st.markdown("#### 筛选条件")
    fc = st.columns(4)
    c_pe_max = fc[0].number_input("PE上限", value=0, step=5, help="0=不限")
    c_pb_max = fc[1].number_input("PB上限", value=0.0, step=0.5, format="%.1f", help="0=不限")
    c_roe_min = fc[2].number_input("ROE下限(%)", value=0.0, step=1.0, format="%.1f", help="0=不限")
    c_to_min = fc[3].number_input("换手率下限(%)", value=0.0, step=1.0, format="%.1f", help="0=不限")

    custom_filters = {}
    if c_pe_max > 0:
        custom_filters["pe_max"] = c_pe_max
    if c_pb_max > 0:
        custom_filters["pb_max"] = c_pb_max
    if c_roe_min > 0:
        custom_filters["roe_min"] = c_roe_min
    if c_to_min > 0:
        custom_filters["turnover_min"] = c_to_min

    c1, c2 = st.columns([3, 1])
    top_n = c1.selectbox("推荐数量", [10, 15, 20, 30], index=1)
    go = c2.button("🚀 开始扫描", type="primary", use_container_width=True)

    strategy_weights = custom_weights
    strategy_filters = custom_filters
    strategy_key = "custom"

    # Preview normalized weights
    st.caption(
        f"归一化权重: 价值={custom_weights['value_quality']:.0%} | "
        f"动量={custom_weights['momentum']:.0%} | "
        f"资金={custom_weights['money_flow']:.0%} | "
        f"情绪={custom_weights['sentiment']:.0%} | "
        f"规模={custom_weights['size']:.0%}"
    )

# ── Run Scan ─────────────────────────────────────────────────────────────────────

if go:
    with st.status("全市场扫描中...", expanded=True) as status:
        st.write("📡 获取全市场 A 股数据...")
        from tradingagents.dataflows.a_stock import screen_stocks

        stocks, total = screen_stocks(
            market="all",
            pe_max=strategy_filters.get("pe_max"),
            pb_max=strategy_filters.get("pb_max"),
            roe_min=strategy_filters.get("roe_min"),
            change_min=strategy_filters.get("change_min"),
            turnover_min=strategy_filters.get("turnover_min"),
            sort_by="f3" if "change_min" in strategy_filters else "f20",
            sort_desc=True,
            page_size=300,
        )
        st.write(f"✅ 初筛 {len(stocks)} 只 (全市场 {total} 只)")

        st.write("📊 五因子百分位评分...")
        if strategy_key == "custom":
            engine = ScoringEngine(strategy="custom", custom_weights=strategy_weights,
                                   custom_filters=strategy_filters)
        else:
            engine = ScoringEngine(strategy=strategy_key)

        ranked = engine.score_all(stocks)
        st.write("🧭 叠加K线趋势、因子投票和风控信号...")
        candidates = ranked[:min(len(ranked), top_n * 2)]
        today = datetime.now().strftime("%Y-%m-%d")
        action_bonus = {"BUY": 8, "WATCH": 2, "NEUTRAL": 0, "AVOID": -12}
        for s in candidates:
            sig = evaluate_code_signal(
                s["code"],
                today,
                strategy_key=strategy_key if strategy_key != "custom" else "balanced",
                quote=s,
                cross_score=s.get("_score", 50),
            )
            s["_signal"] = sig
            s["_final_score"] = round(
                s.get("_score", 0) * 0.65
                + sig.get("score", 50) * 0.35
                + action_bonus.get(sig.get("action"), 0),
                1,
            )
        candidates.sort(key=lambda x: x.get("_final_score", x.get("_score", 0)), reverse=True)
        top = candidates[:top_n]
        st.write(f"🏆 综合评分完成，Top {top_n}")

        rows = []
        for i, s in enumerate(top):
            f = s.get("_factors", {})
            sig = s.get("_signal", {})
            pe_str = f"{s.get('pe', 0):.0f}" if s.get("pe", 0) > 0 else "—"
            rows.append({
                "排名": i + 1, "代码": s["code"], "名称": s["name"],
                "综合分": s.get("_final_score", s["_score"]), "选股分": s["_score"],
                "交易信号": sig.get("action_cn", "—"), "信号分": sig.get("score", 0),
                "风险": sig.get("risk_level", "—"),
                "价值": f.get("value_quality", 0),
                "动量": f.get("momentum", 0), "资金": f.get("money_flow", 0),
                "情绪": f.get("sentiment", 0), "规模": f.get("size", 0),
                "涨跌幅": f"{s.get('change_pct', 0):+.1f}%", "PE": pe_str,
                "止损": sig.get("levels", {}).get("stop_loss", "—"),
                "止盈": sig.get("levels", {}).get("take_profit", "—"),
                "入选理由": "；".join(sig.get("reasons", [])[:2]) or s.get("_reason", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=500)
        st.session_state["picks_data"] = top
        st.session_state["picks_strategy"] = strategy_key
        status.update(label="✅ 扫描完成", state="complete")

# ── Cached Results ───────────────────────────────────────────────────────────────

top_stocks = st.session_state.get("picks_data")
if top_stocks:
    st.markdown("---")
    st.markdown("### 🤖 AI 深度点评")

    if st.button("生成 AI 点评 (Top 5)", type="primary"):
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.ranking.batch_runner import run_batch_analysis

        cfg = DEFAULT_CONFIG.copy()
        cfg.update({
            "llm_provider": "deepseek", "deep_think_llm": "deepseek-chat",
            "quick_think_llm": "deepseek-chat", "backend_url": "https://api.deepseek.com",
            "output_language": "Chinese",
        })

        bar = st.progress(0)
        txt = st.empty()

        def cb(completed, total, code):
            bar.progress(completed / total)
            txt.text(f"AI 点评中... {completed}/{total}")

        results = run_batch_analysis(
            top_stocks=top_stocks[:5], config=cfg,
            max_workers=3, progress_callback=cb,
        )
        st.session_state["picks_ai"] = results
        bar.empty()
        txt.empty()
        st.rerun()

    ai = st.session_state.get("picks_ai")
    if ai:
        st.markdown("#### 🎯 点评结果")
        for r in ai:
            s = next((x for x in top_stocks if x["code"] == r["code"]), None)
            if s:
                cc1, cc2, cc3 = st.columns([1, 1, 4])
                cc1.metric(s["code"], s["name"])
                cc2.metric("评分", f'{r["score"]}/100',
                           delta=f"{s.get('change_pct', 0):+.1f}%")
                cc3.info(r.get("ai_comment", "—"))
                st.markdown("---")

st.markdown("---")
st.caption(f"AI推荐仅供参考，不构成投资建议 | {datetime.now().strftime('%H:%M:%S')}")
