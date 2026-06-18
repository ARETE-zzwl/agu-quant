# TradingAgents-Astock

面向 A 股的多 Agent 投研框架，基于
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
深度特化。系统通过市场、情绪、新闻、基本面、政策、游资和解禁 7 个分析角色，结合多空辩论与风险评估生成研究报告。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache--2.0-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.7-orange)](CHANGELOG.md)

> 本项目仅用于学习、研究和技术演示，不构成证券投资咨询或任何收益承诺。市场有风险，决策需独立判断。

![Web UI](assets/web-ui-welcome.png)

## 主要能力

- 7 个 A 股投研 Analyst：市场、情绪、新闻、基本面、政策、游资、解禁。
- Bull/Bear 多空辩论、研究经理决策和三方风险辩论。
- A 股行情、财务、资金流、龙虎榜、板块、资讯等直连数据源。
- 多因子选股、策略回测、模拟交易、股票监控和 PDF 报告。
- 中文股票名称自动解析为 6 位代码。
- Streamlit Web UI 和命令行两种使用方式。

## 快速开始

### 1. 获取代码

```bash
git clone https://github.com/simonlin1212/TradingAgents-astock.git
cd TradingAgents-astock
```

### 2. 安装

```bash
pip install -e .
```

如需使用 Google 模型：

```bash
pip install -e ".[google]"
```

### 3. 配置模型

复制 `.env.example` 为 `.env`，填入所选模型服务的 API Key。例如：

```env
DEEPSEEK_API_KEY=sk-your-key
```

### 4. 启动

```bash
tradingagents-web
```

也可以直接运行：

```bash
streamlit run web/app.py
```

Windows 用户还可以双击 `启动.bat`。

## 每日投研报告

先在 Web 侧边栏打开“每日投研报告”，保存 6 位股票代码和报告模板。立即生成：

```bash
python -m tradingagents.reporting.daily --tickers 600519,000001 --template brief
```

Windows 定时任务：

```powershell
.\scripts\install_daily_task.ps1 -Time "18:30" -Tickers "600519,000001" -Template brief
```

模板包括 `brief`、`full` 和 `risk`，报告默认保存到 `~/.tradingagents/daily_reports/`。自动运行会产生模型调用费用。

## 数据源

项目的数据层不依赖第三方金融数据库 SDK，主要通过 mootdx 与公开 HTTP 接口获取数据：

| 数据源 | 主要用途 |
|---|---|
| mootdx | K 线、财务快照、F10 文本 |
| 腾讯财经 | PE、PB、市值、换手率 |
| 东方财富 | 行情、资金流、龙虎榜、板块、解禁、新闻 |
| 新浪财经 | 历史 K 线、财务报表 |
| 同花顺 | 一致预期、热股题材 |
| 财联社 | 全球财经快讯 |
| 百度股市通 | 概念板块归属 |

公开接口可能变化或限流，请勿将单一数据源结果视为交易依据。

## 商业支持

核心源码继续按 Apache 2.0 开放。项目可以通过官方构建、托管服务、自动化报告、模板、技术支持和私有部署获得持续维护资金，而不是承诺投资收益。

### 支持开源计划

| 方案 | 建议价格 | 主要权益 |
|---|---:|---|
| 社区版 | 免费 | GitHub 源码、本地运行、自备模型 Key、社区支持 |
| 支持者版 | 99 元/年 | Windows 一键包、国内镜像、稳定更新、配置指南和模板包 |
| Pro 版 | 39 元/月或 299 元/年 | 每日投研报告、定时任务、报告模板和优先支持 |
| 私有部署 | 2999 元起 | 部署、模型/数据源接入、定制 Agent 和培训 |

购买入口仅在应用内“支持开源计划”页面通过真实环境配置展示。未看到官方入口时，请勿向第三方账户付款。

当前商业化设计和上线前安全清单见
[商业化落地方案](docs/COMMERCIALIZATION.md)。正式购买入口尚未开放，请勿向非官方账户付款。

需要真实账号和外部环境完成的事项见 [商业化上线清单](docs/COMMERCIALIZATION_LAUNCH_CHECKLIST.md)。

## 开发与测试

```bash
python -m pytest tests/ -v
```

Web UI 本地验证：

```bash
streamlit run web/app.py
```

## 私有部署

复制 `.env.enterprise.example` 为 `.env.private`，配置管理员和至少一个模型 API Key，然后运行：

```powershell
.\scripts\start_private.ps1 -EnvFile .env.private
```

详细交付范围、安全要求和验收标准见 [私有部署服务](docs/PRIVATE_DEPLOYMENT.md)。定制 Agent 可使用 [需求说明模板](docs/CUSTOM_AGENT_BRIEF.md) 明确数据、工具、权限和输出契约。

## 项目文档

- [更新日志](CHANGELOG.md)
- [与上游的差异](CHANGES_FROM_UPSTREAM.md)
- [商业化落地方案](docs/COMMERCIALIZATION.md)
- [Issue 归档](issues/)

## 许可证

项目采用 [Apache License 2.0](LICENSE)。第三方数据与模型服务仍受各自条款约束。
