# TradingAgents-Astock 宣传文案

以下文案用于项目发布和早期用户招募。发布前请补充真实截图；不要添加收益承诺、夸大胜率或未经确认的付费入口。

项目地址：<https://github.com/simonlin1212/TradingAgents-astock>

## GitHub / Gitee 简介

TradingAgents-Astock 是一个面向 A 股的开源多 Agent 投研框架。

项目在 TradingAgents 基础上增加了政策、游资和解禁分析师，并接入多空辩论、风险评估、多因子研究、策略回测、模拟交易和 Web UI。数据层通过 mootdx 及公开 HTTP 接口获取行情、财务、资金流、龙虎榜、板块和资讯数据。

核心源码采用 Apache 2.0，支持本地部署和自备模型 API Key。

> 仅用于学习、研究和技术演示，不构成证券投资咨询或收益承诺。

## 知乎 / 掘金长文

### 标题

我把 TradingAgents 做成了面向 A 股的 7 Agent 开源投研框架

### 正文

原版 TradingAgents 更偏向通用股票研究。为了适应 A 股，我在市场、情绪、新闻和基本面分析之外，又增加了三个角色：

- 政策分析师：跟踪产业政策、监管变化和政策催化。
- 游资追踪分析师：研究龙虎榜、资金流和短期交易结构。
- 解禁监控分析师：关注限售解禁及潜在供给压力。

系统会让多头和空头研究员围绕分析结果辩论，再经过研究经理和风险角色形成结构化研究报告。项目同时提供多因子研究、策略回测、股票监控、模拟交易和 Streamlit Web UI。

数据侧不依赖 akshare，主要使用 mootdx 和东方财富、腾讯、新浪、同花顺、财联社等公开接口。用户可以自备 DeepSeek、OpenAI、Anthropic 等模型服务的 API Key。

项目核心源码已经按 Apache 2.0 开放：

<https://github.com/simonlin1212/TradingAgents-astock>

后续计划通过官方安装包、稳定更新、研究模板、自动报告、技术支持和私有部署覆盖维护成本。付费服务卖的是交付和持续支持，不是投资收益。

风险提示：任何模型和回测都有局限，历史数据不能保证未来表现，本项目不构成证券投资建议。

## V2EX / 社区短帖

### 标题

[开源] 面向 A 股的 7 Agent 投研框架，支持多空辩论和本地 Web UI

### 正文

最近在维护一个 TradingAgents 的 A 股特化 fork：TradingAgents-Astock。

目前包含 7 个分析角色、多空辩论、风险评估、多因子研究、策略回测、模拟交易和 Streamlit Web UI。数据主要通过 mootdx 和公开 HTTP 接口获取，支持本地部署和自备模型 Key。

项目采用 Apache 2.0：

<https://github.com/simonlin1212/TradingAgents-astock>

欢迎提交数据源稳定性、模型兼容性和 A 股研究流程方面的 Issue。项目只用于研究和技术演示，不提供收益承诺。

## 微信公众号短文

### 标题

开源一个面向 A 股的多 Agent 投研框架

### 正文

TradingAgents-Astock 是一个可以本地运行的 A 股研究工具。它让市场、情绪、新闻、基本面、政策、游资和解禁 7 个分析角色分别完成研究，再通过多空辩论与风险评估生成报告。

除了深度研究，项目还包括多因子选股、策略回测、股票监控、模拟交易和 Web UI。核心源码采用 Apache 2.0，用户可以自行配置模型 API Key。

项目地址：

<https://github.com/simonlin1212/TradingAgents-astock>

后续会优先完善安装体验、自动报告和稳定更新服务。本文仅介绍开源软件，不构成任何投资建议。

## X / Twitter

I open-sourced TradingAgents-Astock, an A-share focused multi-agent research framework:

- 7 analyst roles, including policy, active-capital and lock-up monitoring
- bull/bear debate and multi-stage risk review
- factor research, backtesting and paper trading
- local Streamlit UI with user-provided model API keys

GitHub: <https://github.com/simonlin1212/TradingAgents-astock>

For research and education only. No investment advice or return guarantees.

## 发布检查

- 使用真实产品截图，不使用占位图。
- 确认版本号、安装命令和仓库链接有效。
- 只展示已经开通的付款和客服渠道。
- 不发布历史收益拼接、模拟盘冒充实盘等内容。
- 明示模型成本、数据延迟和第三方接口可能失效。
- 每篇内容保留“不构成投资建议”的风险提示。
