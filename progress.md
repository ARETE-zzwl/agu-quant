# 工作进度

## 2026-05-26
- 创建轻量计划文件，明确本次目标是统一策略与信号体系，并先处理页面导航稳定性。
- 完成外部资料检索和现有代码复核：当前主要割裂点是选股、监控、模拟盘各自生成信号。
- 新增 `tradingagents/ranking/signal_engine.py`，输出统一的买入/观察/补仓/减仓/止盈/平仓动作。
- 将统一信号接入 AI 荐股、股票监控、模拟盘持仓明细。
- 修复启动脚本提前开浏览器的问题，并将主页侧栏跳转改为 `st.switch_page`。
- 验证：`pytest tests\test_strategy_signals.py -q` 通过；页面与核心模块 `py_compile` 通过；`http://localhost:8501/` 返回 200。
- 新增 `tradingagents/ranking/strategy_optimizer.py`：用历史分类因子排名回测五因子权重，按年化、夏普、回撤、胜率、换手生成目标评分。
- 因子引擎新增「策略调权」标签页，可选择基准策略、股票池、周期、调仓频率并一键调权。
- 保存后的优化策略会写入 `~/.tradingagents/optimized_strategies.json`，并自动出现在 AI荐股/股票监控策略下拉中。
- 验证：`pytest tests\test_strategy_optimizer.py tests\test_strategy_signals.py -q` 通过；真实小股票池 smoke test 成功；Streamlit 首页返回 200。
- 新增 `tradingagents/ranking/recommendation_engine.py`：一键拉取当前高流动性股票池，回测比较预设策略，再输出当前候选股。
- AI荐股页新增「一键推荐当下候选股」入口，默认用60只高流动性股票、近180天回测、10天调仓筛选胜出策略。
- 默认60只股票池回测 smoke test：胜出策略为“价值低波”，候选股输出成功；加入日内涨幅>7%的防追高降级规则。
- 验证：7个策略/信号测试通过；新增模块和 AI荐股页 py_compile 通过；Streamlit 首页返回 200。
- 重排模拟盘页面：顶部保留账户总览，主体改为「持仓信号 / 下单交易 / 资产委托 / 规则管理」四个标签页。
- 下单交易页把订单表单和行情K线并排；持仓页可从持仓直接填入卖出或加仓；买入金额现在会覆盖默认股数按金额下单。
- 验证：`web/pages/7_Paper_Trade.py` 编译通过；账户加载正常；`tests/test_strategy_signals.py` 通过；Streamlit 首页返回 200。
- 研究缠论资料后新增 `tradingagents/chan`：实现三K分型、交替成笔、三笔重叠中枢、MACD/笔力度背驰近似、三类买卖点信号和下一根开盘价执行回测。
- 新增 `web/pages/8_Chan_Agent.py` 并接入侧边栏：支持日线/周线/月线，多K线窗口、成笔间隔、缠论策略回测、K线/分型/笔/中枢可视化、止损止盈和可选AI交易解读。
- 验证：`python -m py_compile` 通过；`pytest tests\test_chan_engine.py -q` 通过；`pytest tests\test_strategy_signals.py tests\test_strategy_optimizer.py -q` 通过；真实600519数据烟测输出缠论动作和回测指标；Streamlit health 返回 `ok`。
- 建立 `docs/knowledge_base` 规范化知识库：包含缠论总览、核心概念、买卖点策略、工程化规则、A股交易规则、量化因子、技术指标、回测风控和Agent使用规范。
- 新增 `docs/knowledge_base/catalog.json` 作为机器可读目录，便于后续AI Agent做检索增强和页面展示。
- 新增 `web/pages/9_Knowledge_Base.py` 并接入侧边栏「知识库」，支持目录浏览和关键词搜索。
- 验证：知识库目录 JSON 校验通过，9篇文档均存在；`python -m py_compile web\pages\9_Knowledge_Base.py web\components\sidebar.py` 通过；Streamlit health 返回 `ok`。
