"""AI 荐股与多策略回测研究台."""

from datetime import datetime
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from web.components.common import inject_css, require_premium_page
from tradingagents.ranking.scoring_engine import ScoringEngine
from tradingagents.ranking.signal_engine import evaluate_code_signal
from tradingagents.ranking.recommendation_engine import (
    recommend_strategy_candidates,
    run_one_click_recommendation,
)


def _build_paper_import(stocks: list[dict], strategy_key: str) -> dict:
    """Convert screened rows into the paper-trade candidate contract."""
    recommendations = []
    for stock in stocks:
        signal = stock.get("_signal", {})
        action = signal.get("action", "")
        if action not in {"BUY", "WATCH"} or signal.get("risk_level") == "高":
            continue
        levels = signal.get("levels", {})
        recommendations.append({
            "代码": stock["code"],
            "名称": stock.get("name", ""),
            "操作": signal.get("action_cn", "观察"),
            "动作Key": action,
            "综合分": stock.get("_final_score", stock.get("_score", 0)),
            "选股分": stock.get("_score", 0),
            "信号分": signal.get("score", 0),
            "置信度": signal.get("confidence", 0),
            "风险": signal.get("risk_level", "未知"),
            "现价": stock.get("price", 0),
            "涨跌幅%": stock.get("change_pct", 0),
            "换手%": stock.get("turnover", 0),
            "PE": stock.get("pe", 0),
            "PB": stock.get("pb", 0),
            "止损": levels.get("stop_loss", ""),
            "止盈": levels.get("take_profit", ""),
            "补仓观察": levels.get("add_price", ""),
            "理由": "；".join(signal.get("reasons", [])[:3]),
            "风险提示": "；".join(signal.get("risk_notes", [])[:2]),
        })
    return {
        "strategy_key": strategy_key,
        "strategy_label": ScoringEngine.get_strategies().get(strategy_key, {}).get("label", strategy_key),
        "strategy_desc": "由AI荐股页筛选并导入，仍需在交易时段确认模拟买入。",
        "universe_size": len(stocks),
        "entry_actions": ["BUY", "WATCH"],
        "min_entry_score": 0,
        "recommendations": recommendations,
    }


def _candidate_rows_to_stocks(rows: list[dict]) -> list[dict]:
    """Convert strategy-workbench rows into the shared pick/session contract."""
    return [
        {
            "code": row["代码"],
            "name": row["名称"],
            "_score": row["选股分"],
            "_final_score": row["综合分"],
            "price": row["现价"],
            "change_pct": row["涨跌幅%"],
            "turnover": row.get("换手%", 0),
            "pe": row.get("PE", 0),
            "pb": row.get("PB", 0),
            "_signal": {
                "action": row["动作Key"],
                "action_cn": row["操作"],
                "score": row["信号分"],
                "confidence": row.get("置信度", 0),
                "risk_level": row["风险"],
                "levels": {
                    "stop_loss": row["止损"],
                    "take_profit": row["止盈"],
                    "add_price": row.get("补仓观察", ""),
                },
                "reasons": [row["理由"]] if row["理由"] else [],
                "risk_notes": [row["风险提示"]] if row["风险提示"] else [],
            },
        }
        for row in rows
    ]


def _display_candidate_table(rows: list[dict], *, show_status: bool = True) -> None:
    display_rows = []
    for i, row in enumerate(rows, start=1):
        item = {
            "排名": i,
            "代码": row["代码"],
            "名称": row["名称"],
            "操作": row["操作"],
            "综合分": row["综合分"],
            "选股分": row["选股分"],
            "信号分": row["信号分"],
            "风险": row["风险"],
            "现价": row["现价"],
            "涨跌幅": f"{row['涨跌幅%']:+.1f}%",
            "止损": row["止损"],
            "止盈": row["止盈"],
            "理由": row["理由"],
            "风险提示": row["风险提示"],
        }
        if show_status:
            item = {
                "排名": i,
                "入选状态": row.get("入选状态", "—"),
                **{key: value for key, value in item.items() if key != "排名"},
            }
        display_rows.append(item)
    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True, height=430)

st.set_page_config(page_title="AI 荐股", page_icon="🧠", layout="wide", initial_sidebar_state="collapsed")
inject_css()
require_premium_page("AI 荐股")

st.markdown(
    '<div style="margin-bottom:1rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">🧠 AI 荐股</span>'
    f'<span style="color:#8f8a82;font-size:0.85rem;margin-left:0.8rem;">{len(ScoringEngine.get_presets())}套策略 · 回测研究台 · 模拟仓联动</span></div>',
    unsafe_allow_html=True,
)

# ── One-click Recommendation ────────────────────────────────────────────────────

with st.expander("🎯 多策略回测与当下选股", expanded=True):
    st.caption("同一股票池、同一时间窗比较全部策略；冠军和其他策略都可以继续查看当前具体选股。")
    oc1, oc2, oc3, oc4 = st.columns([1, 1, 1, 1.15])
    oc_universe = oc1.selectbox("股票池规模", [40, 60, 100], index=1)
    oc_period = oc2.selectbox("回测周期", [90, 180, 365], index=1, format_func=lambda days: f"近{days}天")
    oc_n = oc3.selectbox("每套查看", [5, 10, 15], index=1, format_func=lambda count: f"Top {count}")
    one_click = oc4.button("开始多策略回测", type="primary", use_container_width=True)

    if one_click:
        with st.status("正在建立策略研究台...", expanded=True) as status:
            try:
                st.write("📡 获取同一组高流动性股票池")
                st.write("🧪 用统一成本和调仓规则比较全部策略")
                st.write("🧭 为冠军策略叠加当前信号与风险过滤")
                result = run_one_click_recommendation(
                    universe_size=oc_universe,
                    recommend_n=oc_n,
                    lookback_days=oc_period,
                    top_pct=0.2,
                    rebalance_days=10,
                    max_positions=10,
                )
                st.session_state["one_click_picks"] = result
                st.session_state["one_click_strategy_results"] = {}
                status.update(label="✅ 策略研究台已更新", state="complete")
            except Exception as exc:
                status.update(label="❌ 多策略回测失败", state="error")
                st.error(f"多策略回测失败: {exc}")

    oc_result = st.session_state.get("one_click_picks")
    if oc_result:
        best = oc_result["best_strategy"]
        result_view = st.radio(
            "结果视图",
            ["🏆 冠军结果", "🧭 策略研究台", "📐 口径说明"],
            horizontal=True,
            key="one_click_result_view",
            label_visibility="collapsed",
        )

        if result_view == "🏆 冠军结果":
            metrics = best["metrics"]
            b1, b2, b3, b4, b5 = st.columns(5)
            b1.metric("冠军策略", best["label"])
            b2.metric("目标分", f"{metrics['objective_score']:.1f}")
            b3.metric("年化收益", f"{metrics['annual_return'] * 100:.1f}%")
            b4.metric("夏普", f"{metrics['sharpe_ratio']:.2f}")
            b5.metric("最大回撤", f"{metrics['max_drawdown'] * 100:.1f}%")
            st.caption(best.get("desc", ""))

            champion_rows = oc_result.get("strategy_candidates", oc_result.get("recommendations", []))
            if champion_rows:
                _display_candidate_table(champion_rows)
                if st.button("采用冠军选股", type="primary", key="use_champion_picks"):
                    st.session_state["picks_data"] = _candidate_rows_to_stocks(champion_rows)
                    st.session_state["picks_strategy"] = best["key"]
                    st.success("冠军选股已设为当前候选，可在页面下方加入模拟仓或生成 AI 点评。")
            else:
                st.warning("冠军策略当前没有通过数据完整性检查的候选股。")

        elif result_view == "🧭 策略研究台":
            strategy_rows = oc_result.get("strategy_rows", [])
            st.markdown(f"**本轮已比较 {len(strategy_rows)} 套策略。** 排名不是黑箱终点，选择任意一套继续看它今天选了谁。")
            st.dataframe(pd.DataFrame(strategy_rows), use_container_width=True, hide_index=True, height=360)

            if strategy_rows:
                default_index = 1 if len(strategy_rows) > 1 else 0
                selected_index = st.selectbox(
                    "查看哪套策略的具体选股",
                    range(len(strategy_rows)),
                    index=default_index,
                    format_func=lambda index: (
                        f"#{strategy_rows[index]['排名']}  {strategy_rows[index]['策略']}"
                        f"  · 目标分 {strategy_rows[index]['目标分']:.1f}"
                    ),
                )
                selected_row = strategy_rows[selected_index]
                selected_key = selected_row["策略Key"]
                detail = ScoringEngine.get_strategy_detail(selected_key)

                d1, d2, d3, d4 = st.columns(4)
                d1.metric("本轮排名", f"#{selected_row['排名']}")
                d2.metric("年化", f"{selected_row['年化%']:.1f}%")
                d3.metric("夏普", f"{selected_row['夏普']:.2f}")
                d4.metric("回撤", f"{selected_row['回撤%']:.1f}%")
                st.markdown(f"**{detail['label']}** · {detail['family']} · 风险 {detail['risk_level']} · 持有 {detail['holding_period']}")
                st.caption(detail["implementation"])

                weight_text = " · ".join(
                    f"{label} {detail['weights'][key]:.0%}"
                    for key, label in {
                        "value_quality": "价值质量",
                        "momentum": "动量",
                        "money_flow": "资金",
                        "sentiment": "情绪",
                        "size": "低波/规模",
                    }.items()
                )
                st.caption(f"权重：{weight_text}")
                if detail.get("research_sources"):
                    st.markdown("研究来源：" + " · ".join(
                        f"[{source['title']}]({source['url']})" for source in detail["research_sources"]
                    ))

                cache = st.session_state.setdefault("one_click_strategy_results", {})
                load_col, hint_col = st.columns([1, 2.4])
                if load_col.button("加载该策略选股", type="primary", use_container_width=True, key=f"load_{selected_key}"):
                    universe = oc_result.get("universe", [])
                    if not universe:
                        st.warning("这是旧版回测缓存，请重新点击“开始多策略回测”后再查看。")
                    else:
                        with st.spinner(f"正在计算 {detail['label']} 的当前信号..."):
                            cache[selected_key] = recommend_strategy_candidates(
                                universe,
                                strategy_key=selected_key,
                                recommend_n=oc_n,
                                end_date=oc_result.get("date"),
                            )
                hint_col.caption("候选会保留中性信号并标为“仅排名”，便于研究；加入模拟仓时仍只接受买入/观察且非高风险标的。")

                selected_result = cache.get(selected_key)
                if selected_result:
                    selected_candidates = selected_result["candidates"]
                    _display_candidate_table(selected_candidates)
                    if st.button("采用这套策略的选股", key=f"use_{selected_key}"):
                        st.session_state["picks_data"] = _candidate_rows_to_stocks(selected_candidates)
                        st.session_state["picks_strategy"] = selected_key
                        st.success(f"已采用 {detail['label']}，可在页面下方加入模拟仓或生成 AI 点评。")

        else:
            st.markdown(
                "回测先按当前成交额建立高流动性股票池，再在统一的时间区间、调仓频率、持仓上限和交易成本下比较策略。"
                "目标分同时考虑年化收益、夏普、胜率、最大回撤和换手率；它用于同轮相对比较，不等于未来收益预测。"
            )
            for note in oc_result.get("notes", []):
                st.caption(f"• {note}")

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
    st.link_button("查看策略说明", "/10_Strategy_Guide")

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
        if not stocks:
            status.update(label="行情源暂不可用", state="error")
            st.warning("东方财富 push2 暂时没有返回可用股票数据，请稍后重试或降低扫描数量。")
            st.stop()
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
    paper_import = _build_paper_import(
        top_stocks,
        st.session_state.get("picks_strategy", "balanced"),
    )
    import_col, import_hint = st.columns([1, 2])
    if import_col.button(
        f"加入模拟仓候选 ({len(paper_import['recommendations'])})",
        type="primary",
        use_container_width=True,
        disabled=not paper_import["recommendations"],
    ):
        st.session_state["paper_import_candidates"] = paper_import
        st.switch_page("pages/7_Paper_Trade.py")
    import_hint.caption("只导入买入/观察且非高风险的候选；实际成交仍由模拟仓按交易时间、资金、涨跌停和手数规则校验。")

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
