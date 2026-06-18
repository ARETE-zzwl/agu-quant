"""因子引擎 — 80因子 · 8大类 · 回测 · IC分析 · AI优化 · 自动监控."""

from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from web.components.common import inject_css, require_premium_page
from tradingagents.factors import (
    ALL_FACTORS, FACTOR_CATEGORIES,
    compute_ic, factor_correlation, factor_report,
    run_factor_backtest,
    AIWeightOptimizer, AISynergyAnalyzer,
)
from tradingagents.ranking.scoring_engine import ScoringEngine
from tradingagents.ranking.strategy_optimizer import (
    WEIGHT_LABELS,
    optimize_strategy_weights,
    save_optimized_strategy,
)

st.set_page_config(page_title="因子引擎", page_icon="⚙️", layout="wide", initial_sidebar_state="collapsed")
inject_css()
require_premium_page("因子引擎")

st.markdown(
    '<div style="margin-bottom:0.5rem;">'
    f'<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">⚙️ 因子引擎</span>'
    f'<span style="color:#666;font-size:0.85rem;margin-left:0.8rem;">'
    f'{len(ALL_FACTORS)}因子 · {len(FACTOR_CATEGORIES)}大类 · 基于学术研究与实证</span></div>',
    unsafe_allow_html=True,
)

CODES = ["600519", "000858", "300750", "002594", "600036", "601318", "000001",
         "600276", "603259", "600900", "601857", "600030", "000725", "000333", "600585"]
end_date = datetime.now().strftime("%Y-%m-%d")
start_date = (datetime.now() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["📊 因子分析", "📈 回测", "🤖 AI优化", "🔗 联动分析", "🔔 自动监控", "⚖️ 策略调权"]
)

# ── TAB 1: Factor Analysis ──────────────────────────────────────────────────────

with tab1:
    # Category tabs
    cats = list(FACTOR_CATEGORIES.keys())
    cat_tabs = st.tabs(cats)
    selected = []

    for i, cat in enumerate(cats):
        names = FACTOR_CATEGORIES[cat]
        with cat_tabs[i]:
            st.caption(f"{len(names)} 个因子")
            # Show top by IC within category
            from tradingagents.factors.library import get_top_by_ic
            top_ic = get_top_by_ic(cat, 5)
            st.markdown("**高IC因子 (文献参考):**")
            for f in top_ic:
                st.caption(f"`{f.name}` IC≈{f.ic_value:.2f}")

            for n in names:
                if st.checkbox(n, key=f"fsel_{n}"):
                    selected.append(n)

    if st.button("分析选中因子", type="primary") and selected:
        dates_list = [d.strftime("%Y-%m-%d") for d in pd.date_range(start_date, end_date, freq="14D")[-12:]]
        with st.spinner(f"分析 {len(selected)} 个因子..."):
            results = []
            for fn in selected:
                try:
                    r = factor_report(fn, CODES, dates_list, top_pct=0.3, rebalance_days=5)
                    results.append(r)
                except Exception as e:
                    results.append({"factor": fn, "score": 0, "error": str(e)})
            st.session_state["fe_results"] = results

        rows = []
        for r in sorted(results, key=lambda x: x.get("score", 0), reverse=True):
            rows.append({
                "因子": r.get("factor", ""), "IC均值": r.get("ic_mean", 0),
                "IC_IR": r.get("ic_ir", 0), "年化%": round(r.get("annual_return", 0) * 100, 1),
                "夏普": r.get("sharpe_ratio", 0), "回撤%": round(r.get("max_drawdown", 0) * 100, 1),
                "胜率%": r.get("win_rate", 0), "综合分": r.get("score", 0),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if results:
            ic_data = {r["factor"]: r.get("ic_mean", 0) for r in results if r.get("ic_mean", 0) != 0}
            if ic_data:
                st.bar_chart(pd.DataFrame({"IC均值": ic_data}))

# ── TAB 2: Backtest ─────────────────────────────────────────────────────────────

with tab2:
    c1, c2, c3 = st.columns(3)
    bt_factor = c1.selectbox("因子", list(ALL_FACTORS.keys()), key="bt_f")
    bt_pct = c2.slider("做多比例", 0.05, 0.5, 0.2, 0.05)
    bt_reb = c3.selectbox("调仓(天)", [1, 5, 10, 20], index=1)
    bt_start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    if st.button("开始回测", type="primary"):
        with st.spinner(f"回测 {bt_factor}..."):
            r = run_factor_backtest(bt_factor, CODES, bt_start, end_date,
                                    top_pct=bt_pct, rebalance_days=bt_reb)
            st.session_state["fe_bt"] = r

    r = st.session_state.get("fe_bt")
    if r and not r.error:
        cols = st.columns(6)
        cols[0].metric("年化收益", f"{r.annual_return*100:.1f}%")
        cols[1].metric("夏普", f"{r.sharpe_ratio:.2f}")
        cols[2].metric("最大回撤", f"{r.max_drawdown*100:.1f}%")
        cols[3].metric("胜率", f"{r.win_rate*100:.1f}%")
        cols[4].metric("总收益", f"{r.total_return*100:.1f}%")
        cols[5].metric("交易", r.total_trades)
        if r.equity_curve is not None:
            st.line_chart(pd.DataFrame({"净值": r.equity_curve.values}))
    elif r and r.error:
        st.error(f"回测失败: {r.error}")

# ── TAB 3: AI Optimize ──────────────────────────────────────────────────────────

with tab3:
    results = st.session_state.get("fe_results")
    if not results:
        st.info("先在「因子分析」中选择因子并运行分析")
    else:
        cw = {r["factor"]: 1.0 / max(len(results), 1) for r in results}
        st.json(cw)
        if st.button("AI 优化权重", type="primary"):
            from tradingagents.default_config import DEFAULT_CONFIG
            llm_cfg = DEFAULT_CONFIG.copy()
            llm_cfg.update({"llm_provider": "deepseek", "deep_think_llm": "deepseek-chat",
                           "quick_think_llm": "deepseek-chat", "backend_url": "https://api.deepseek.com"})
            with st.spinner("AI 分析..."):
                opt = AIWeightOptimizer()
                aw = opt.optimize(results, cw, llm_cfg)
                st.session_state["fe_ai_w"] = aw

        aw = st.session_state.get("fe_ai_w")
        if aw:
            c1, c2 = st.columns([1, 2])
            c1.json(aw["weights"])
            c2.info(aw.get("reasoning", ""))

# ── TAB 4: Synergy ──────────────────────────────────────────────────────────────

with tab4:
    sf = st.multiselect("选择因子", list(ALL_FACTORS.keys()),
                         default=["pe_rank", "mom_1m", "idio_vol", "earnings_yield", "value_mom"])
    if len(sf) >= 2:
        corr = factor_correlation(sf, CODES, end_date)
        st.dataframe(corr.round(3), use_container_width=True)
        comp = [(sf[i], sf[j], corr.iloc[i, j]) for i in range(len(sf))
                for j in range(i + 1, len(sf)) if abs(corr.iloc[i, j]) < 0.3]
        if comp:
            st.success(f"**{len(comp)} 对互补因子 (低相关<0.3):**")
            for a, b, c in comp:
                st.write(f"- {a} + {b}: ρ={c:.2f}")
        red = [(sf[i], sf[j], corr.iloc[i, j]) for i in range(len(sf))
               for j in range(i + 1, len(sf)) if abs(corr.iloc[i, j]) > 0.7]
        if red:
            st.warning(f"**{len(red)} 对冗余因子 (高相关>0.7):**")
            for a, b, c in red:
                st.write(f"- {a} + {b}: ρ={c:.2f}")

# ── TAB 5: Auto Monitor ─────────────────────────────────────────────────────────

with tab5:
    st.markdown("### 🔔 因子机会自动扫描")
    st.caption("对指定股票运行全因子扫描，发现触发买入/卖出信号的因子")

    monitor_ticker = st.text_input("股票代码", "600519", key="mon_ticker",
                                   placeholder="输入6位代码")

    if st.button("🔍 扫描因子信号", type="primary"):
        with st.spinner(f"扫描 {monitor_ticker} 全部 {len(ALL_FACTORS)} 因子..."):
            from tradingagents.dataflows.a_stock import _load_ohlcv_astock
            df = _load_ohlcv_astock(monitor_ticker, end_date)
            if df.empty:
                st.error("无法获取数据")
                st.stop()
            df = df.set_index("Date")

            buy_signals = []
            sell_signals = []
            for name, factor in ALL_FACTORS.items():
                try:
                    sig = factor.signal(df)
                    if sig == "BUY":
                        buy_signals.append((name, factor.category, factor.ic_value))
                    elif sig == "SELL":
                        sell_signals.append((name, factor.category, factor.ic_value))
                except Exception:
                    pass

            buy_signals.sort(key=lambda x: x[2], reverse=True)
            sell_signals.sort(key=lambda x: x[2], reverse=True)

            total_buy = len(buy_signals)
            total_sell = len(sell_signals)
            score = total_buy - total_sell

            st.metric("综合因子评分", f"{score:+d}",
                      delta=f"🟢{total_buy}买入 / 🔴{total_sell}卖出")

            if buy_signals:
                st.success(f"**买入信号 ({total_buy}):**")
                buy_df = pd.DataFrame(buy_signals, columns=["因子", "类别", "IC参考"])
                st.dataframe(buy_df, use_container_width=True, hide_index=True)

            if sell_signals:
                st.error(f"**卖出信号 ({total_sell}):**")
                sell_df = pd.DataFrame(sell_signals, columns=["因子", "类别", "IC参考"])
                st.dataframe(sell_df, use_container_width=True, hide_index=True)

    # Batch monitoring
    st.markdown("---")
    st.markdown("### 🔍 批量机会扫描 (Top因子)")
    batch_codes = st.text_area("股票代码列表(换行分隔)", "600519\n000858\n300750", height=100)

    if st.button("🔍 批量扫描", type="primary") and batch_codes:
        codes = [c.strip() for c in batch_codes.split("\n") if c.strip()]
        # Use top IC factors only for speed
        from tradingagents.factors.library import get_top_by_ic
        top_factors = get_top_by_ic(top_n=20)

        results = []
        for code in codes:
            try:
                from tradingagents.dataflows.a_stock import _load_ohlcv_astock
                df = _load_ohlcv_astock(code, end_date)
                if df.empty:
                    results.append({"code": code, "score": 0, "buy": 0, "sell": 0, "error": "no data"})
                    continue
                df = df.set_index("Date")
                buy = sell = 0
                for f in top_factors:
                    try:
                        sig = f.signal(df)
                        if sig == "BUY":
                            buy += 1
                        elif sig == "SELL":
                            sell += 1
                    except Exception:
                        pass
                results.append({
                    "code": code, "score": buy - sell, "buy": buy, "sell": sell, "error": None,
                })
            except Exception as e:
                results.append({"code": code, "score": 0, "buy": 0, "sell": 0, "error": str(e)})

        results.sort(key=lambda x: x["score"], reverse=True)
        rows = []
        for r in results:
            rows.append({
                "代码": r["code"], "综合评分": f"{r['score']:+d}",
                "买入信号": r["buy"], "卖出信号": r["sell"],
                "状态": "🟢 看多" if r["score"] > 3 else ("🔴 看空" if r["score"] < -3 else "⚪ 中性"),
                "备注": r.get("error") or "",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── TAB 6: Strategy Weight Optimization ─────────────────────────────────────────

with tab6:
    st.markdown("### ⚖️ 策略回测评分自动调权")
    st.caption("用历史回测评价五因子权重，自动生成可复用的优化策略；结果会进入 AI荐股/股票监控 的策略下拉。")

    presets = ScoringEngine.get_presets()
    preset_keys = [p["key"] for p in presets]
    preset_map = {p["key"]: p for p in presets}

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    base_idx = c1.selectbox(
        "基准策略",
        range(len(preset_keys)),
        format_func=lambda i: preset_map[preset_keys[i]]["label"],
        key="opt_base_strategy",
    )
    period = c2.selectbox("回测周期", ["近6个月", "近1年", "近2年"], index=1)
    opt_reb = c3.selectbox("调仓频率", [5, 10, 20], index=1, format_func=lambda x: f"{x}天")
    opt_top = c4.selectbox("持仓比例", [0.1, 0.2, 0.3], index=1, format_func=lambda x: f"{int(x*100)}%")

    c5, c6 = st.columns([1, 3])
    opt_max_pos = c5.number_input("最大持仓数", min_value=3, max_value=50, value=10, step=1)
    universe_text = c6.text_area(
        "股票池",
        "\n".join(CODES),
        height=120,
        help="一行一个股票代码。股票池越大越慢，但结果更稳定。",
    )

    days = {"近6个月": 183, "近1年": 365, "近2年": 730}[period]
    opt_start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    opt_codes = [c.strip() for c in universe_text.splitlines() if c.strip()]
    base_key = preset_keys[base_idx]
    base_cfg = preset_map[base_key]

    if st.button("开始回测调权", type="primary", use_container_width=True):
        with st.spinner("正在准备历史K线、计算分类因子排名并测试候选权重..."):
            try:
                result = optimize_strategy_weights(
                    opt_codes,
                    opt_start,
                    end_date,
                    base_weights=base_cfg["weights"],
                    top_pct=opt_top,
                    rebalance_days=opt_reb,
                    max_positions=int(opt_max_pos),
                )
                st.session_state["strategy_opt_result"] = result
                st.session_state["strategy_opt_meta"] = {
                    "base_key": base_key,
                    "base_label": base_cfg["label"],
                    "base_filters": base_cfg.get("filters", {}),
                    "start_date": opt_start,
                    "end_date": end_date,
                    "codes": opt_codes,
                }
            except Exception as exc:
                st.error(f"调权失败: {exc}")

    opt_result = st.session_state.get("strategy_opt_result")
    opt_meta = st.session_state.get("strategy_opt_meta", {})
    if opt_result:
        best = opt_result["best"]
        best_metrics = best["metrics"]

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("目标评分", f"{best_metrics['objective_score']:.1f}")
        m2.metric("年化收益", f"{best_metrics['annual_return']*100:.1f}%")
        m3.metric("夏普", f"{best_metrics['sharpe_ratio']:.2f}")
        m4.metric("最大回撤", f"{best_metrics['max_drawdown']*100:.1f}%")
        m5.metric("胜率", f"{best_metrics['win_rate']*100:.1f}%")

        st.markdown("#### 推荐权重")
        weight_rows = []
        base_weights = preset_map.get(opt_meta.get("base_key", base_key), base_cfg)["weights"]
        for k, label in WEIGHT_LABELS.items():
            weight_rows.append({
                "因子维度": label,
                "原权重": f"{base_weights.get(k, 0):.0%}",
                "优化后": f"{best['weights'].get(k, 0):.0%}",
                "变化": f"{(best['weights'].get(k, 0) - base_weights.get(k, 0)):+.0%}",
            })
        st.dataframe(pd.DataFrame(weight_rows), use_container_width=True, hide_index=True)

        if best.get("equity_curve") is not None:
            st.line_chart(pd.DataFrame({"优化策略净值": best["equity_curve"].values}))

        st.markdown("#### 候选组合排名")
        cand_rows = []
        for i, cand in enumerate(opt_result["candidates"][:12], start=1):
            mt = cand["metrics"]
            cand_rows.append({
                "排名": i,
                "目标分": mt["objective_score"],
                "年化%": round(mt["annual_return"] * 100, 1),
                "夏普": round(mt["sharpe_ratio"], 2),
                "回撤%": round(mt["max_drawdown"] * 100, 1),
                "胜率%": round(mt["win_rate"] * 100, 1),
                "平均换手": f"{mt['avg_turnover']:.0%}",
                "权重": " / ".join(f"{WEIGHT_LABELS[k]}{cand['weights'][k]:.0%}" for k in WEIGHT_LABELS),
            })
        st.dataframe(pd.DataFrame(cand_rows), use_container_width=True, hide_index=True)

        if st.button("保存为可选策略", type="primary"):
            saved_key = save_optimized_strategy(
                opt_meta.get("base_key", base_key),
                opt_meta.get("base_label", base_cfg["label"]),
                best["weights"],
                best_metrics,
                start_date=opt_meta.get("start_date", opt_start),
                end_date=opt_meta.get("end_date", end_date),
                codes=opt_meta.get("codes", opt_codes),
                filters=opt_meta.get("base_filters", {}),
            )
            st.success(f"已保存: {saved_key}。刷新 AI荐股或股票监控后可在策略下拉中选择。")

st.markdown("---")
st.caption(f"{len(ALL_FACTORS)} 因子 · 基于 Fama-French, Factor Zoo, 中信FactorZoo II, 方正高频因子 等研究 | {datetime.now().strftime('%H:%M:%S')}")
