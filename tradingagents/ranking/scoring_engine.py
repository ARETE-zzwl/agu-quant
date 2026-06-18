"""Multi-factor scoring engine with research-backed strategies.

Strategies designed based on empirical A-share quantitative research:
- Value + Low-vol combo consistently generates alpha in A-shares
- Momentum works but needs volume confirmation in T+1 market
- Northbound + main force tracking captures institutional flows
- Small-cap reversal exploits retail investor overreaction
"""

from __future__ import annotations

import math

SCORE_KEYS = ["value_quality", "momentum", "money_flow", "sentiment", "size"]

WEIGHT_LABELS = {
    "value_quality": "价值质量",
    "momentum": "动量趋势",
    "money_flow": "资金流向",
    "sentiment": "情绪/反转",
    "size": "规模/低波",
}

# Strategy catalog — each has:
#   label, description, filters (pre-screen), weights (5-factor)

STRATEGIES = {
    # ── Value Family ──────────────────────────────────────────────────────────
    "deep_value": {
        "label": "低估修复",
        "desc": "PE<15 + PB<2 + 价格近1年低点 + 高ROE → 均值回归潜力大",
        "filters": {"pe_max": 20, "pb_max": 3},
        "weights": {"value_quality": 0.50, "momentum": 0.10, "money_flow": 0.15, "sentiment": 0.10, "size": 0.15},
    },
    "dividend_value": {
        "label": "红利价值",
        "desc": "低PE + 低PB + 大市值 → 类红利策略，熊市抗跌",
        "filters": {"pe_max": 25, "pb_max": 2.5},
        "weights": {"value_quality": 0.45, "momentum": 0.10, "money_flow": 0.10, "sentiment": 0.05, "size": 0.30},
    },
    "value_lowvol": {
        "label": "价值低波",
        "desc": "低PE + 低PB + 低换手 → Fama-French价值因子，A股长期有效",
        "filters": {"pe_max": 20, "pb_max": 3},
        "weights": {"value_quality": 0.40, "momentum": 0.05, "money_flow": 0.15, "sentiment": 0.10, "size": 0.30},
    },

    # ── Growth Family ─────────────────────────────────────────────────────────
    "garp": {
        "label": "优质成长(GARP)",
        "desc": "ROE>12% + PE<30 + PEG合理 → 合理价格买成长",
        "filters": {"pe_max": 35, "roe_min": 10},
        "weights": {"value_quality": 0.30, "momentum": 0.25, "money_flow": 0.20, "sentiment": 0.10, "size": 0.15},
    },
    "quality_growth": {
        "label": "质量成长",
        "desc": "高ROE + 盈利增长 + 合理PE → 寻找复利机器",
        "filters": {"roe_min": 12},
        "weights": {"value_quality": 0.35, "momentum": 0.25, "money_flow": 0.15, "sentiment": 0.15, "size": 0.10},
    },

    # ── Momentum Family ───────────────────────────────────────────────────────
    "trend_breakout": {
        "label": "强势突破",
        "desc": "涨幅>2% + 换手>5% + 放量 → 量价配合突破",
        "filters": {"change_min": 1, "turnover_min": 3},
        "weights": {"value_quality": 0.05, "momentum": 0.40, "money_flow": 0.25, "sentiment": 0.25, "size": 0.05},
    },
    "pullback_buy": {
        "label": "回调买入",
        "desc": "近期下跌 + 主力资金流入 → 洗盘后的反弹机会",
        "filters": {},
        "weights": {"value_quality": 0.20, "momentum": 0.05, "money_flow": 0.40, "sentiment": 0.15, "size": 0.20},
    },

    # ── Money Flow Family ─────────────────────────────────────────────────────
    "smart_money": {
        "label": "聪明钱跟踪",
        "desc": "主力连续流入 + 成交额大 + 换手适中 → 跟随机构动向",
        "filters": {"turnover_min": 1},
        "weights": {"value_quality": 0.15, "momentum": 0.20, "money_flow": 0.40, "sentiment": 0.15, "size": 0.10},
    },
    "northbound_fav": {
        "label": "外资偏好",
        "desc": "大市值 + 高成交额 + 低估值 → 北向资金最爱类型",
        "filters": {"pe_max": 40},
        "weights": {"value_quality": 0.30, "momentum": 0.10, "money_flow": 0.20, "sentiment": 0.10, "size": 0.30},
    },

    # ── Special Situations ────────────────────────────────────────────────────
    "smallcap_reversal": {
        "label": "小盘反转",
        "desc": "小市值 + 超跌(换手萎缩后放量) → 散户恐慌后的反弹",
        "filters": {},
        "weights": {"value_quality": 0.20, "momentum": 0.15, "money_flow": 0.30, "sentiment": 0.20, "size": 0.15},
    },
    "limitup_hunter": {
        "label": "涨停猎手",
        "desc": "涨幅>5% + 高换手 + 资金涌入 → 抓强势股的延续性",
        "filters": {"change_min": 3, "turnover_min": 5},
        "weights": {"value_quality": 0.05, "momentum": 0.35, "money_flow": 0.30, "sentiment": 0.25, "size": 0.05},
    },
    # ── Backtest-Proven Strategies (2025.01-2026.05 validation) ───────────────
    "reversal_boll_mom": {
        "label": "反转+布林+动量 [回测验证]",
        "desc": "日内反转 + 布林收窄 + 动量3月 → 组合Alpha+9.6%, 最大回撤仅1.3%",
        "filters": {},
        "weights": {"value_quality": 0.05, "momentum": 0.30, "money_flow": 0.25, "sentiment": 0.35, "size": 0.05},
    },
    "intraday_reversal": {
        "label": "日内反转 [回测Alpha+15%]",
        "desc": "捕捉开盘冲高回落后的反弹 → 散户过度反应后的均值回归",
        "filters": {},
        "weights": {"value_quality": 0.10, "momentum": 0.10, "money_flow": 0.20, "sentiment": 0.50, "size": 0.10},
    },
    "boll_mean_rev": {
        "label": "布林均值回归 [胜率20.6%]",
        "desc": "布林下轨买入 + 布林收窄突破 → 最高胜率策略",
        "filters": {},
        "weights": {"value_quality": 0.15, "momentum": 0.30, "money_flow": 0.15, "sentiment": 0.30, "size": 0.10},
    },
    "backtest_value_size_alpha": {
        "label": "价值低波Alpha [近一年优选]",
        "desc": "价值质量 + 规模低波双核心，降低情绪噪声；在2025-06-14~2026-06-14默认池回测总收益48.5%",
        "filters": {"pe_max": 35, "pb_max": 4},
        "weights": {"value_quality": 0.45, "momentum": 0.00, "money_flow": 0.10, "sentiment": 0.00, "size": 0.45},
        "family": "回测优选",
        "risk_level": "中",
        "holding_period": "10-20个交易日",
        "best_for": "震荡或结构性行情中寻找低波动、高性价比标的",
    },
    "paper_signal_opt": {
        "label": "模拟舱稳健增强 [默认]",
        "desc": "面向模拟舱的一键选股与持仓管理：价值低波为底，高分观察股允许入池；默认池3年模拟舱回测总收益33.8%",
        "filters": {"pe_max": 35, "pb_max": 4},
        "weights": {"value_quality": 0.45, "momentum": 0.00, "money_flow": 0.10, "sentiment": 0.00, "size": 0.45},
        "family": "模拟舱",
        "risk_level": "中",
        "holding_period": "5-20个交易日",
        "best_for": "想一键选股后放入模拟舱观察，并在持仓过程中按信号加减仓的用户",
        "paper_entry_actions": ["BUY", "WATCH"],
        "paper_min_entry_score": 65,
        "backtest_note": "2023-06-15~2026-06-14默认15股池，BUY/WATCH且信号分>=65入场，总收益33.79%，年化10.66%，最大回撤12.00%。",
        "implementation": "使用价值质量和规模低波作为主要选股分，少量资金流确认；空仓时允许高分观察股进入模拟舱，持仓后继续使用统一信号引擎执行加仓、止盈、止损和平仓提示。",
    },
    "flow_value_rotation": {
        "label": "资金价值轮动 [高收益]",
        "desc": "主攻资金流，辅以价值和规模过滤；在2025-06-14~2026-06-14默认池回测总收益53.3%",
        "filters": {"turnover_min": 1},
        "weights": {"value_quality": 0.15, "momentum": 0.05, "money_flow": 0.55, "sentiment": 0.00, "size": 0.25},
        "family": "资金流",
        "risk_level": "中高",
        "holding_period": "5-15个交易日",
        "best_for": "资金流持续改善、成交活跃但未明显过热的股票池",
    },
    "flow_trend_confirm": {
        "label": "资金趋势确认",
        "desc": "资金流和动量共同确认，减少单纯追涨；适合趋势延续阶段",
        "filters": {"turnover_min": 1, "change_min": 0},
        "weights": {"value_quality": 0.15, "momentum": 0.30, "money_flow": 0.35, "sentiment": 0.00, "size": 0.20},
        "family": "资金流",
        "risk_level": "中高",
        "holding_period": "5-10个交易日",
        "best_for": "量价同步向上、主力资金净流入的趋势股",
    },
    "defensive_value_size": {
        "label": "防守价值低波",
        "desc": "价值质量和规模低波为主，牺牲弹性换取回撤控制；默认池近一年最大回撤约6.7%",
        "filters": {"pe_max": 30, "pb_max": 3},
        "weights": {"value_quality": 0.45, "momentum": 0.00, "money_flow": 0.00, "sentiment": 0.05, "size": 0.50},
        "family": "防守",
        "risk_level": "低中",
        "holding_period": "20-60个交易日",
        "best_for": "市场波动加大、需要降低组合回撤时",
    },
    "capital_lowvol_barbell": {
        "label": "资金低波杠铃",
        "desc": "一端抓资金流，一端压低波动，减少纯题材策略的回撤风险",
        "filters": {"turnover_min": 1},
        "weights": {"value_quality": 0.15, "momentum": 0.05, "money_flow": 0.35, "sentiment": 0.00, "size": 0.45},
        "family": "资金流",
        "risk_level": "中",
        "holding_period": "10-20个交易日",
        "best_for": "资金偏强但市场整体风险偏高的阶段",
    },
    "volume_breakout_confirm": {
        "label": "放量突破确认",
        "desc": "动量和资金流双高，保留少量情绪确认；进攻性强，需配合止损",
        "filters": {"change_min": 1, "turnover_min": 3},
        "weights": {"value_quality": 0.05, "momentum": 0.35, "money_flow": 0.40, "sentiment": 0.10, "size": 0.10},
        "family": "动量",
        "risk_level": "高",
        "holding_period": "3-10个交易日",
        "best_for": "放量突破、热点扩散、短线风险预算充足时",
    },
    "quality_flow_compound": {
        "label": "质量资金复合",
        "desc": "价值质量与资金流均衡，保留一定动量，适合做中性增强基线",
        "filters": {"pe_max": 40, "turnover_min": 1},
        "weights": {"value_quality": 0.30, "momentum": 0.15, "money_flow": 0.40, "sentiment": 0.00, "size": 0.15},
        "family": "均衡增强",
        "risk_level": "中",
        "holding_period": "10-30个交易日",
        "best_for": "想在默认均衡策略上提高收益弹性，但不追极端动量时",
    },
    "lowvol_core_satellite": {
        "label": "低波核心卫星",
        "desc": "规模低波作为核心，少量资金流和动量做增强",
        "filters": {"pe_max": 45},
        "weights": {"value_quality": 0.20, "momentum": 0.05, "money_flow": 0.05, "sentiment": 0.05, "size": 0.65},
        "family": "防守",
        "risk_level": "低中",
        "holding_period": "20-60个交易日",
        "best_for": "偏稳健用户、组合底仓或弱市防守",
    },
    "oversold_flow_rebound": {
        "label": "超跌资金反弹",
        "desc": "资金流 + 情绪反转为主，用价值质量过滤纯弱股",
        "filters": {},
        "weights": {"value_quality": 0.15, "momentum": 0.05, "money_flow": 0.45, "sentiment": 0.25, "size": 0.10},
        "family": "反转",
        "risk_level": "高",
        "holding_period": "3-10个交易日",
        "best_for": "急跌后出现资金回流、但还没有形成拥挤追涨时",
    },
    "growth_flow_trend": {
        "label": "成长资金趋势",
        "desc": "动量、资金流、质量三者均衡，面向成长股趋势修复",
        "filters": {"roe_min": 8, "turnover_min": 1},
        "weights": {"value_quality": 0.20, "momentum": 0.30, "money_flow": 0.35, "sentiment": 0.05, "size": 0.10},
        "family": "成长",
        "risk_level": "中高",
        "holding_period": "5-20个交易日",
        "best_for": "成长板块回暖、成交放大且趋势开始修复时",
    },
    "balanced_plus": {
        "label": "综合均衡增强",
        "desc": "基于默认均衡的一年候选调权：提高价值质量和资金流，降低情绪噪声",
        "filters": {},
        "weights": {"value_quality": 0.304348, "momentum": 0.130435, "money_flow": 0.304348, "sentiment": 0.086957, "size": 0.173913},
        "family": "均衡增强",
        "risk_level": "中",
        "holding_period": "10-20个交易日",
        "best_for": "默认策略的增强替代，适合先做全市场筛选再人工确认",
    },
    "alpha191_balanced": {
        "label": "Alpha191 价量均衡",
        "desc": "参考GTJA Alpha191短周期价量思路，均衡配置动量、资金流、反转和低波维度",
        "filters": {"turnover_min": 1},
        "weights": {"value_quality": 0.10, "momentum": 0.30, "money_flow": 0.30, "sentiment": 0.20, "size": 0.10},
        "factor_map": "alpha191_style",
        "family": "Alpha191",
        "risk_level": "中高",
        "holding_period": "3-10个交易日",
        "best_for": "希望用短周期价量因子捕捉交易型机会的用户",
        "implementation": "使用GTJA Alpha191风格因子子集作为因子库补充，选股权重偏向动量、资金流和情绪反转；个股层面继续叠加K线趋势、量价、涨跌停和波动风控。",
    },
    "alpha191_momentum_reversal": {
        "label": "Alpha191 动量反转",
        "desc": "突出日内位置、五日反转、VWAP偏离和成交量冲击，适合短线均值回归",
        "filters": {"turnover_min": 2},
        "weights": {"value_quality": 0.05, "momentum": 0.35, "money_flow": 0.20, "sentiment": 0.35, "size": 0.05},
        "factor_map": "alpha191_style",
        "family": "Alpha191",
        "risk_level": "高",
        "holding_period": "1-5个交易日",
        "best_for": "高换手、短线反转、热点回落后的二次确认场景",
        "implementation": "偏重Alpha191风格的收盘位置变化、五日反转、VWAP偏离和量价冲击；适合观察，不建议脱离止损直接实盘执行。",
    },
    "alpha191_flow_volatility": {
        "label": "Alpha191 资金波动",
        "desc": "将Alpha191价量失衡与低波控制组合，强调资金流和波动收缩后的扩散",
        "filters": {"turnover_min": 1},
        "weights": {"value_quality": 0.10, "momentum": 0.20, "money_flow": 0.40, "sentiment": 0.10, "size": 0.20},
        "factor_map": "alpha191_style",
        "family": "Alpha191",
        "risk_level": "中高",
        "holding_period": "5-15个交易日",
        "best_for": "成交活跃、资金失衡明显，同时希望控制波动回撤的股票池",
        "implementation": "使用Alpha191风格的量价相关、资金流失衡、波动收缩因子作为信号来源；五维评分上提高资金流和低波/规模权重。",
    },
    "alpha191_momentum_core": {
        "label": "Alpha191 动量核心 [回测优选]",
        "desc": "Alpha191子集在默认池近一年表现较好的调权方案：动量80% + 低波20%",
        "filters": {"turnover_min": 1},
        "weights": {"value_quality": 0.00, "momentum": 0.80, "money_flow": 0.00, "sentiment": 0.00, "size": 0.20},
        "factor_map": "alpha191_style",
        "family": "Alpha191",
        "risk_level": "中高",
        "holding_period": "3-10个交易日",
        "best_for": "短周期价量趋势更清晰、市场有连续性时，用作Alpha191子集的优选版本",
        "implementation": "使用GTJA Alpha191风格因子映射，并把组合权重集中在动量类Alpha191因子，少量低波维度用于控制过度追涨。",
    },
    "alpha191_flow_lowvol_opt": {
        "label": "Alpha191 低波容量增强 [回测优选]",
        "desc": "Alpha191 190因子池权重搜索优选：价值20% + 资金流10% + 低波70%，默认池近一年总收益约34.3%",
        "filters": {"turnover_min": 1},
        "weights": {"value_quality": 0.20, "momentum": 0.00, "money_flow": 0.10, "sentiment": 0.00, "size": 0.70},
        "factor_map": "alpha191_style",
        "family": "Alpha191",
        "risk_level": "中",
        "holding_period": "10-30个交易日",
        "best_for": "Alpha191 190因子池里希望先控制回撤和因子稀释风险的用户，适合波动收敛、成交容量稳定的股票池",
        "implementation": "使用完整Alpha191可计算因子池，权重主要压在低波/规模代理维度，少量价值和资金流用于确认容量与价格支撑；相比30因子精选池更分散，但收益弹性也会被稀释。",
    },
    "advanced_vol_momentum": {
        "label": "前沿 波动目标动量",
        "desc": "参考volatility-managed momentum与残差动量：用中期趋势除以实现波动率，偏好稳定趋势",
        "filters": {"turnover_min": 1},
        "weights": {"value_quality": 0.05, "momentum": 0.55, "money_flow": 0.15, "sentiment": 0.05, "size": 0.20},
        "factor_map": "advanced_quant",
        "family": "Advanced Quant",
        "risk_level": "中高",
        "holding_period": "5-20个交易日",
        "best_for": "趋势连续但波动没有明显失控的行情，用作更稳健的动量增强方案",
        "implementation": "使用Advanced Quant因子映射：动量维度由波动目标动量、趋势一致性和残差动量组成，规模/低波维度由波动稳定性和Amihud流动性控制冲击成本。",
    },
    "advanced_liquidity_reversal": {
        "label": "前沿 流动性冲击反转",
        "desc": "参考流动性冲击与短期反转研究：寻找高成交急跌后的修复机会",
        "filters": {"turnover_min": 2},
        "weights": {"value_quality": 0.05, "momentum": 0.15, "money_flow": 0.35, "sentiment": 0.30, "size": 0.15},
        "factor_map": "advanced_quant",
        "family": "Advanced Quant",
        "risk_level": "高",
        "holding_period": "1-10个交易日",
        "best_for": "短线急跌、成交放大、但流动性仍足够的股票池，必须配合止损和仓位控制",
        "implementation": "核心信号是流动性冲击反转与日内反转，叠加Amihud非流动性和波动稳定性过滤，避免选择冲击成本过高的弱流动标的。",
    },
    "advanced_lowvol_quality": {
        "label": "前沿 低波质量增强",
        "desc": "结合低波异象、Amihud流动性和质量低风险代理，偏防守但保留趋势确认",
        "filters": {"pe_max": 45},
        "weights": {"value_quality": 0.35, "momentum": 0.15, "money_flow": 0.10, "sentiment": 0.00, "size": 0.40},
        "factor_map": "advanced_quant",
        "family": "Advanced Quant",
        "risk_level": "低中",
        "holding_period": "10-40个交易日",
        "best_for": "震荡或风险偏好下降阶段，想降低回撤但保留一部分趋势暴露的用户",
        "implementation": "用波动稳定性、Amihud流动性和低风险质量作为主筛选，少量残差动量和趋势一致性用于避免长期弱势股。",
    },
    "advanced_stable_momentum_opt": {
        "label": "前沿 稳定动量增强 [回测优选]",
        "desc": "Advanced Quant因子权重搜索优选：低风险质量40% + 波动目标动量50% + 反转10%",
        "filters": {"turnover_min": 1},
        "weights": {"value_quality": 0.40, "momentum": 0.50, "money_flow": 0.00, "sentiment": 0.10, "size": 0.00},
        "factor_map": "advanced_quant",
        "family": "Advanced Quant",
        "risk_level": "中高",
        "holding_period": "5-20个交易日",
        "best_for": "想尝试更前沿价量/风险因子，但仍希望用低风险质量约束动量暴露的用户",
        "implementation": "使用波动目标动量、趋势一致性、残差动量识别趋势，配合波动稳定性、Amihud流动性和短线反转过滤高冲击成本标的。",
    },
    "classic_12_1_momentum": {
        "label": "经典 12-1 动量",
        "desc": "跳过最近1个月观察中期赢家延续，并用价格路径与下行风险过滤追高噪音",
        "filters": {"turnover_min": 1},
        "weights": {"value_quality": 0.05, "momentum": 0.60, "money_flow": 0.15, "sentiment": 0.05, "size": 0.15},
        "factor_map": "research_classics",
        "family": "经典研究",
        "risk_level": "中高",
        "holding_period": "10-40个交易日",
        "best_for": "趋势扩散、行业轮动较清晰的阶段；不适合单日情绪脉冲或连续涨停后的追高",
        "implementation": "以12-1月动量和6月动量为核心，叠加价格通道、上涨路径质量和量价确认；下行风险维度用于降低高波动赢家的权重。",
        "research_sources": [
            {
                "title": "Jegadeesh & Titman (1993), Returns to Buying Winners and Selling Losers",
                "url": "https://doi.org/10.1111/j.1540-6261.1993.tb04702.x",
            }
        ],
    },
    "research_value_momentum": {
        "label": "经典 价值×动量",
        "desc": "价值负责安全边际，动量负责避开持续下跌的价值陷阱",
        "filters": {"pe_max": 45},
        "weights": {"value_quality": 0.40, "momentum": 0.35, "money_flow": 0.10, "sentiment": 0.00, "size": 0.15},
        "factor_map": "research_classics",
        "family": "经典研究",
        "risk_level": "中",
        "holding_period": "20-60个交易日",
        "best_for": "估值分化后出现趋势确认的修复行情，希望兼顾赔率与右侧确认的用户",
        "implementation": "用盈利收益率、质量价差和质量估值刻画价值，再与12-1月动量、趋势路径和下行风险共同排序，避免只买便宜不买改善。",
        "research_sources": [
            {
                "title": "Asness, Moskowitz & Pedersen (2013), Value and Momentum Everywhere",
                "url": "https://doi.org/10.1111/jofi.12021",
            }
        ],
    },
    "research_quality_momentum": {
        "label": "经典 质量×动量",
        "desc": "盈利质量与趋势质量双确认，寻找基本面更稳、价格趋势更干净的标的",
        "filters": {"roe_min": 8},
        "weights": {"value_quality": 0.38, "momentum": 0.37, "money_flow": 0.10, "sentiment": 0.00, "size": 0.15},
        "factor_map": "research_classics",
        "family": "经典研究",
        "risk_level": "中",
        "holding_period": "15-50个交易日",
        "best_for": "结构性成长或景气扩散阶段，希望减少纯题材趋势和盈利脆弱标的的用户",
        "implementation": "以ROE趋势、质量价差、动量质量和价格路径为主；量价与下行风险只做确认，不把短期情绪热度当成核心收益来源。",
        "research_sources": [
            {
                "title": "Asness, Frazzini & Pedersen, Quality Minus Junk",
                "url": "https://www.aqr.com/Insights/Research/Working-Paper/Quality-Minus-Junk",
            },
            {
                "title": "Quality Minus Junk (SSRN 2312432)",
                "url": "https://doi.org/10.2139/ssrn.2312432",
            },
        ],
    },
    "research_downside_defense": {
        "label": "经典 下行风险防御",
        "desc": "只惩罚下跌波动与尾部风险，用Sortino和回撤控制构建防御候选池",
        "filters": {"pe_max": 50},
        "weights": {"value_quality": 0.30, "momentum": 0.10, "money_flow": 0.05, "sentiment": 0.00, "size": 0.55},
        "factor_map": "research_classics",
        "family": "经典研究",
        "risk_level": "低中",
        "holding_period": "20-80个交易日",
        "best_for": "指数震荡、风险偏好收缩或组合需要降低尾部暴露的阶段",
        "implementation": "下行波动、Sortino、尾部风险、最大回撤和价格稳定性占主导，质量价值用于避免低波但经营恶化的标的，保留少量趋势确认。",
        "research_sources": [
            {
                "title": "Ang, Hodrick, Xing & Zhang (2006), The Cross-Section of Volatility and Expected Returns",
                "url": "https://doi.org/10.1111/j.1540-6261.2006.00836.x",
            },
            {
                "title": "NBER Working Paper 10852",
                "url": "https://doi.org/10.3386/w10852",
            },
        ],
    },
    "balanced": {
        "label": "综合均衡",
        "desc": "五因子等权 + 无预设偏差 → 适合作为基准组合",
        "filters": {},
        "weights": {"value_quality": 0.20, "momentum": 0.20, "money_flow": 0.20, "sentiment": 0.20, "size": 0.20},
    },
}

# Custom strategy key
CUSTOM_KEY = "custom"


def _strategy_catalog() -> dict:
    catalog = dict(STRATEGIES)
    try:
        from .strategy_optimizer import load_optimized_strategies
        catalog.update(load_optimized_strategies())
    except Exception:
        pass
    return catalog


def _normalize_weights(weights: dict | None) -> dict[str, float]:
    weights = weights or {}
    cleaned = {k: max(0.0, float(weights.get(k, 0) or 0)) for k in SCORE_KEYS}
    total = sum(cleaned.values())
    if total <= 0:
        return {k: 1 / len(SCORE_KEYS) for k in SCORE_KEYS}
    normalized = {}
    running = 0.0
    for key in SCORE_KEYS[:-1]:
        normalized[key] = round(cleaned[key] / total, 6)
        running += normalized[key]
    normalized[SCORE_KEYS[-1]] = round(1.0 - running, 6)
    return normalized


def _infer_family(key: str, cfg: dict) -> str:
    if cfg.get("family"):
        return cfg["family"]
    if key.startswith("opt_"):
        return "回测调权"
    if "value" in key or "dividend" in key:
        return "价值"
    if "growth" in key or "garp" in key:
        return "成长"
    if "flow" in key or "money" in key or "northbound" in key:
        return "资金流"
    if "breakout" in key or "momentum" in key or "limitup" in key:
        return "动量"
    if "reversal" in key or "boll" in key or "pullback" in key:
        return "反转"
    return "综合"


def _infer_risk(weights: dict[str, float], cfg: dict) -> str:
    if cfg.get("risk_level"):
        return cfg["risk_level"]
    aggressive = weights["momentum"] + weights["sentiment"]
    defensive = weights["value_quality"] + weights["size"]
    if aggressive >= 0.55:
        return "高"
    if defensive >= 0.65 and aggressive <= 0.2:
        return "低中"
    return "中"


def _strategy_detail(key: str, cfg: dict) -> dict:
    weights = _normalize_weights(cfg.get("weights"))
    top_dims = sorted(weights, key=weights.get, reverse=True)[:2]
    filters = cfg.get("filters", {}) or {}
    if filters:
        filter_text = "；".join(f"{k}={v}" for k, v in filters.items())
    else:
        filter_text = "无硬性预筛选，主要依赖横截面评分和交易信号二次确认"
    implementation = cfg.get("implementation") or (
        f"先按预筛选条件取股票池，再计算五因子横截面百分位；"
        f"权重最高的维度是{WEIGHT_LABELS[top_dims[0]]}和{WEIGHT_LABELS[top_dims[1]]}。"
        f"最终在AI荐股和股票监控中叠加K线趋势、资金/因子投票、涨跌停与波动风险。"
    )
    return {
        "key": key,
        "label": cfg.get("label", key),
        "desc": cfg.get("desc", ""),
        "family": _infer_family(key, cfg),
        "risk_level": _infer_risk(weights, cfg),
        "holding_period": cfg.get("holding_period", "5-20个交易日"),
        "best_for": cfg.get("best_for", "作为候选股票池筛选策略，需结合个股信号和风险提示确认"),
        "filters": filters,
        "weights": weights,
        "implementation": implementation,
        "backtest_note": cfg.get(
            "backtest_note",
            "历史收益来自当前回测引擎和样本区间，只能用于研究比较，不能视为未来收益承诺。",
        ),
        "research_sources": cfg.get("research_sources", []),
    }


class ScoringEngine:
    """Multi-factor percentile-based stock scoring."""

    def __init__(self, strategy: str = "balanced", custom_weights: dict = None, custom_filters: dict = None):
        if strategy == CUSTOM_KEY and custom_weights:
            self.strategy = CUSTOM_KEY
            self.label = "自定义策略"
            self.desc = "用户自定义权重和筛选条件"
            self.filters = custom_filters or {}
            self.weights = custom_weights
        else:
            catalog = _strategy_catalog()
            cfg = catalog.get(strategy, catalog["balanced"])
            self.strategy = strategy
            self.label = cfg["label"]
            self.desc = cfg["desc"]
            self.filters = cfg["filters"]
            self.weights = cfg["weights"]

    def score_all(self, stocks: list[dict]) -> list[dict]:
        """Score and rank stocks by percentile within the batch."""
        if not stocks:
            return []

        n = len(stocks)
        raw = {s["code"]: {
            "value_quality": self._value_quality_raw(s),
            "momentum": self._momentum_raw(s),
            "money_flow": self._money_flow_raw(s),
            "sentiment": self._sentiment_raw(s),
            "size": self._size_raw(s),
        } for s in stocks}

        pct = {code: {} for code in raw}
        for factor in self.weights:
            vals = sorted([(c, raw[c][factor]) for c in raw], key=lambda x: x[1])
            for rank, (code, _) in enumerate(vals):
                pct[code][factor] = round(rank / max(n - 1, 1) * 100)

        for s in stocks:
            code = s["code"]
            s["_score"] = round(sum(pct[code][f] * self.weights.get(f, 0.2) for f in self.weights))
            s["_factors"] = pct[code]
            s["_reason"] = self._make_reason(pct[code])

        stocks.sort(key=lambda s: s.get("_score", 0), reverse=True)
        return stocks

    def _make_reason(self, pct: dict) -> str:
        best = max(pct, key=pct.get)
        names = {
            "value_quality": "估值优势突出",
            "momentum": "短期动量强劲",
            "money_flow": "主力资金涌入",
            "sentiment": "市场情绪高涨",
            "size": "大市值蓝筹",
        }
        return f"{names.get(best, best)} ({pct[best]}分)"

    # ── Raw Factor Calculators ─────────────────────────────────────────────────

    @staticmethod
    def _value_quality_raw(s: dict) -> float:
        pe = s.get("pe", 0) or 999
        pb = s.get("pb", 0) or 99
        roe = s.get("roe", 0) or 0
        score = 0.0
        if 0 < pe < 100:
            score += min(40, 1000 / pe)
        if 0 < pb < 20:
            score += min(30, 100 / pb)
        if roe > 0:
            score += min(30, roe * 2)
        return score

    @staticmethod
    def _momentum_raw(s: dict) -> float:
        chg = s.get("change_pct", 0) or 0
        turnover = s.get("turnover", 0) or 0
        amp = s.get("amplitude", 0) or 0
        score = chg * 3
        if 3 <= turnover <= 20:
            score += turnover * 2
        elif turnover > 20:
            score += 40
        if amp > 3:
            score += amp * 2
        return score

    @staticmethod
    def _money_flow_raw(s: dict) -> float:
        mf = s.get("main_force_net", 0) or 0
        amount = s.get("amount", 0) or 0
        score = 0.0
        if mf > 0:
            score += math.log10(max(mf, 1)) * 5
        else:
            score -= math.log10(max(-mf, 1)) * 3
        if amount > 1e8:
            score += math.log10(amount / 1e8) * 3
        return max(-30, score)

    @staticmethod
    def _sentiment_raw(s: dict) -> float:
        turnover = s.get("turnover", 0) or 0
        chg = s.get("change_pct", 0) or 0
        score = turnover * 2
        if chg > 3:
            score += (chg - 3) * 3
        return score

    @staticmethod
    def _size_raw(s: dict) -> float:
        mcap = s.get("market_cap", 0) or 0
        if mcap <= 0:
            return 0
        return math.log10(max(mcap, 1e8)) * 10

    @classmethod
    def get_strategies(cls) -> dict:
        return _strategy_catalog()

    @classmethod
    def get_presets(cls) -> list[dict]:
        """Return strategies as a flat list for UI display."""
        return [{"key": k, **v} for k, v in _strategy_catalog().items()]

    @classmethod
    def get_strategy_details(cls) -> list[dict]:
        """Return page-ready strategy metadata with normalized weights."""
        return [_strategy_detail(k, v) for k, v in _strategy_catalog().items()]

    @classmethod
    def get_strategy_detail(cls, key: str) -> dict:
        """Return one strategy detail; fallback to balanced for unknown keys."""
        catalog = _strategy_catalog()
        selected = key if key in catalog else "balanced"
        return _strategy_detail(selected, catalog[selected])
