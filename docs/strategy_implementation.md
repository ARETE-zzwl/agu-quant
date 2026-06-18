# 策略实现说明

本文档说明当前策略体系如何工作，以及新增策略如何被用户选择和回测。

## 1. 策略目录

策略定义集中在 `tradingagents/ranking/scoring_engine.py` 的 `STRATEGIES`。

每个策略包含：

- `label`：页面展示名称
- `desc`：策略逻辑摘要
- `filters`：预筛选条件，例如 `pe_max`、`pb_max`、`roe_min`、`turnover_min`、`change_min`
- `weights`：五个评分维度的权重
- `family`、`risk_level`、`holding_period`、`best_for`：策略库页面展示用信息

五个评分维度是：

| key | 含义 | 主要来源 |
| --- | --- | --- |
| `value_quality` | 价值质量 | PE、PB、ROE |
| `momentum` | 动量趋势 | 涨跌幅、换手率、振幅 |
| `money_flow` | 资金流向 | 主力净流入、成交额 |
| `sentiment` | 情绪/反转 | 换手活跃度、涨幅关注度 |
| `size` | 规模/低波 | 市值规模，回测中用低波/稳定代理 |

## 2. AI 荐股流程

入口在 `web/pages/4_AI_Picks.py`。

流程：

1. 用户选择策略或自定义五因子权重。
2. `screen_stocks()` 按策略的 `filters` 取候选股票池。
3. `ScoringEngine.score_all()` 对候选股做横截面百分位评分。
4. `evaluate_code_signal()` 载入个股 K 线并叠加交易信号。
5. 页面按 `65% 横截面评分 + 35% 个股信号 + 动作加减分` 排序展示。

横截面评分公式：

```text
score = sum(percentile(factor_key) * strategy_weight[factor_key])
```

其中每个 `percentile` 都在当前候选池内部计算，分值范围约为 0 到 100。

## 3. 股票监控流程

入口在 `web/pages/6_Stock_Monitor.py`。

监控页会：

- 按用户选择的策略读取权重
- 对单只或多只股票计算多周期 K 线
- 扫描全部因子买卖信号
- 用 `evaluate_stock_signal()` 给出买入、观察、持有、减仓、止盈、止损等动作

策略权重会影响因子分类贡献，例如资金流策略会放大资金类因子的买卖票权。

## 4. 个股交易信号

核心在 `tradingagents/ranking/signal_engine.py`。

信号由四部分组成：

- 趋势：MA20、MA60、MACD、20/60 日收益
- 反转：RSI、布林位置、短期回撤
- 量价：量比、近 5 日涨跌和放量状态
- 因子票：高 IC 因子的 BUY/SELL/NEUTRAL 投票

风险覆盖包括：

- ATR 波动率
- MA60 下方弱势
- 60 日回撤
- 异常放量
- 接近涨停或跌停

这些风险点会降低最终分数，并改变推荐动作。

## 5. 回测逻辑

核心在 `tradingagents/ranking/strategy_optimizer.py`。

回测流程：

1. `_load_ohlcv_astock()` 获取历史 K 线。
2. `prepare_strategy_backtest()` 计算每个调仓日的五类因子排名。
3. `run_weight_backtest()` 根据策略权重合成分数。
4. 每个调仓日买入排名靠前的 `top_pct` 股票，等权持有。
5. 调仓时按换手率扣除 `cost_rate`。
6. 输出总收益、年化收益、夏普、最大回撤、胜率、平均换手和目标评分。

默认参数：

| 参数 | 默认值 |
| --- | --- |
| `top_pct` | 20% |
| `rebalance_days` | 10 |
| `max_positions` | 10 |
| `cost_rate` | 0.12% |

## 6. 新增高收益策略说明

新增策略不是单纯手写主观权重，而是用最近一年默认股票池做候选权重搜索后，再按风格归类保留：

- `backtest_value_size_alpha`：价值低波 Alpha，近一年默认池总收益约 48.5%，最大回撤约 6.7%
- `flow_value_rotation`：资金价值轮动，近一年默认池总收益约 53.3%
- `flow_trend_confirm`：资金趋势确认
- `defensive_value_size`：防守价值低波
- `capital_lowvol_barbell`：资金低波杠铃
- `volume_breakout_confirm`：放量突破确认
- `quality_flow_compound`：质量资金复合
- `lowvol_core_satellite`：低波核心卫星
- `oversold_flow_rebound`：超跌资金反弹
- `growth_flow_trend`：成长资金趋势
- `balanced_plus`：综合均衡增强

这些策略会自动出现在 AI 荐股、股票监控和策略库页面的下拉列表中。

## 7. Alpha191 风格量化方案

本项目新增了一个 `GTJA Alpha191` 因子类别，目前注册并可计算 190 个 Alpha191 风格因子：

- `gtja_alpha001` 到 `gtja_alpha191` 均已注册，按用户要求跳过复杂的 `gtja_alpha030`。
- 其中 30 个为手工公式化实现，160 个为 OHLCV 兼容生成实现。
- 当前项目单股 `compute_series()` 不能直接拿到原公式所需的完整横截面、行业中性、市值、SMB/HML 和指数回归数据；这些缺失项使用现有 K 线、成交量、成交额/VWAP 代理落地。

手工公式化实现的代表因子：

- `gtja_alpha001`：量价背离
- `gtja_alpha002`：收盘位置反转
- `gtja_alpha003`：真实波动累积
- `gtja_alpha006`：开盘量价相关
- `gtja_alpha012`：量价冲击
- `gtja_alpha014`：五日反转
- `gtja_alpha015`：隔夜跳空
- `gtja_alpha016`：量价相关反转
- `gtja_alpha018`：五日价格比
- `gtja_alpha020`：六日动量
- `gtja_alpha021`：均线斜率反转
- `gtja_alpha024`：平滑五日动量
- `gtja_alpha028`：VWAP 偏离
- `gtja_alpha029`：量能六日动量
- `gtja_alpha031`：均线偏离
- `gtja_alpha041`：波动收缩
- `gtja_alpha046`：均线均值回归
- `gtja_alpha054`：日内压力
- `gtja_alpha057`：九日通道位置
- `gtja_alpha088`：二十日动量
- `gtja_alpha094`：三十日符号量能
- `gtja_alpha101`：衰减量价相关
- `gtja_alpha105`：开盘量价相关
- `gtja_alpha115`：高位量价共振
- `gtja_alpha126`：典型价格
- `gtja_alpha128`：资金流失衡
- `gtja_alpha132`：二十日成交额
- `gtja_alpha150`：典型成交额
- `gtja_alpha172`：趋势方向强度
- `gtja_alpha191`：量低价偏离

实现边界：

- 覆盖状态：当前覆盖 190/191，`gtja_alpha030` 按用户要求跳过。
- 严格边界：不是所有 190 个都等价于机构原始横截面精确版；其中需要行业/市值/指数项的公式采用 OHLCV 兼容代理，方便先在当前交易系统中可选、可评分、可回测。
- Alpha191 原始公式大量使用横截面 `rank`、时间序列 `ts_rank`、`correlation`、`decay_linear` 等算子；当前项目单股 `compute_series()` 场景下，用滚动时间序列排名和价量代理实现可计算版本。
- 回测时，Alpha191 策略使用独立的 `alpha191_style` 因子映射，不污染默认五因子回测。

新增可选方案：

- `alpha191_balanced`：Alpha191 价量均衡
- `alpha191_momentum_reversal`：Alpha191 动量反转
- `alpha191_flow_volatility`：Alpha191 资金波动
- `alpha191_momentum_core`：Alpha191 动量核心，默认池近一年候选调权中表现较好
- `alpha191_flow_lowvol_opt`：Alpha191 低波容量增强，190 因子池近一年权重搜索优选，价值 20% + 资金流 10% + 低波 70%，默认池一年总收益约 34.3%

参考来源：

- DolphinDB `gtja191Alpha` 模块说明：https://docs.dolphindb.com/zh/modules/gtja191Alpha/191alpha.html
- BigQuant Alpha191 公式页：https://bigquant.com/wiki/doc/Pyf0TYya6H
- 聚宽 Alpha191 数据说明：https://joinquant.com/data/dict/alpha191
- 国泰君安研报 PDF：https://guorn.com/static/upload/file/3/134065454575605.pdf

## 8. Advanced Quant 前沿因子方案

本次新增 `Advanced Quant` 因子类别，目标不是复刻某一家机构闭源模型，而是把公开研究里更常用的现代量化思想转成当前项目可计算、可回测、可让用户选择的方案。

新增因子：

- `adv_vol_target_momentum`：波动目标动量。参考 volatility-managed momentum，把 63 日动量按 20 日实现波动率缩放。
- `adv_trend_consistency`：趋势一致性。用上涨天数比例和路径效率过滤剧烈震荡的假趋势。
- `adv_liquidity_shock_reversal`：流动性冲击反转。捕捉高成交急跌后的短线修复机会。
- `adv_amihud_liquidity`：Amihud 非流动性代理。用单位成交额带来的价格波动衡量冲击成本，越高越差。
- `adv_vol_stability`：波动稳定性。综合近期波动、下行波动和波动率漂移，偏好低风险稳定股票。
- `adv_residual_momentum`：残差动量代理。剔除自身长期均值后的 12-1 动量，降低短期反转噪声。

新增可选方案：

- `advanced_vol_momentum`：前沿波动目标动量，主打动量但用波动和流动性控制追涨风险。
- `advanced_liquidity_reversal`：前沿流动性冲击反转，偏短线高风险。
- `advanced_lowvol_quality`：前沿低波质量增强，偏防守。
- `advanced_stable_momentum_opt`：前沿稳定动量增强，默认池近一年权重搜索优选，低风险质量 40% + 动量 50% + 反转 10%。

实现边界：

- 当前项目没有完整历史横截面财务字段、分钟高频盘口、指数成分和真实冲击成本，所以这些是“公开思想的可计算复现”，不是机构原模型全量复刻。
- Advanced Quant 使用独立 `advanced_quant` 因子映射，可单独回测，不改变默认策略和 Alpha191 子集策略。

参考研究脉络：

- Momentum crash / volatility-managed momentum 思路
- Residual momentum / idiosyncratic momentum 思路
- Amihud illiquidity 与流动性冲击成本
- Low-volatility anomaly / defensive quality 思路

## 9. 模拟舱一键选股和持仓信号

模拟舱入口在 `web/pages/7_Paper_Trade.py`。

本次新增 `paper_signal_opt`，页面展示为“模拟舱稳健增强 [默认]”。它不是新的黑箱模型，而是把表现更好的模拟舱交易规则固定成默认：

- 选股权重：价值质量 45% + 资金流 10% + 规模/低波 45%。
- 入场动作：允许 `BUY`，也允许高分 `WATCH` 入池。
- 入场门槛：默认信号分 `>=65`，且风险等级不能为高。
- 持仓管理：继续沿用统一信号引擎的 `ADD`、`REDUCE`、`TAKE_PROFIT`、`STOP_LOSS`、`EXIT`。

默认 15 股池、`2023-06-15` 到 `2026-06-14` 的模拟舱规则回测：

| 方案 | 入场规则 | 总收益 | 年化 | 最大回撤 | 夏普 |
| --- | --- | ---: | ---: | ---: | ---: |
| 原默认 `balanced` | 只允许 `BUY` | 27.67% | 8.87% | 12.02% | 0.63 |
| `backtest_value_size_alpha` | 只允许 `BUY` | 28.79% | 9.21% | 11.99% | 0.66 |
| `paper_signal_opt` | `BUY/WATCH` 且信号分 >= 65 | 33.79% | 10.66% | 12.00% | 0.73 |

对应回测脚本为 `scripts/backtest_paper_trade_signals.py`。模拟假设是 T 日收盘生成信号，T+1 开盘执行，保留模拟舱的 T+1、涨跌停、A 股手数和交易费用规则。

一键选股函数在 `tradingagents/ranking/recommendation_engine.py` 的 `run_paper_trade_quick_select()`。它先取高流动性股票池，用策略横截面分排序，再用 `evaluate_code_signal()` 做同源交易信号确认。用户可以把候选股填入买入单，也可以在交易时段一键买入候选进入模拟舱观察。

## 10. 风险和局限

- 回测收益是历史样本结果，不代表未来收益。
- 默认股票池只有 15 只核心股票，收益可能存在样本选择偏差。
- 高收益策略可能更依赖近一年市场风格，样本外需要继续验证。
- 当前回测按等权组合模拟，没有完整撮合盘口、滑点、停牌和极端涨跌停无法成交建模。
- 策略输出适合研究和模拟盘，不应直接作为实盘交易指令。
