# agu-quant

[中文](#中文) · [English](#english)

## 中文

一个用于 A 股行情查看、条件筛选、因子研究和模拟交易的 Python 项目，带有 Streamlit 界面。单股分析会结合行情、新闻和基本面等信息，调用语言模型生成报告。

它把看盘、选股和策略实验放在同一个本地界面里。模拟盘用于记录和观察策略表现；模型生成的分析需要结合原始数据判断。本项目仅供学习研究，不构成投资建议。

### 目前包含什么

| 模块 | 内容 |
| --- | --- |
| 大盘与板块 | 指数、涨跌家数、行业与概念板块 |
| 条件选股 | 按估值、盈利能力、市值等条件筛选 |
| 因子研究 | 因子计算、回测、IC/IR 和相关性分析 |
| 单股分析 | 多个分析角色分别处理信息，再汇总研究和风控意见 |
| 股票监控与模拟盘 | 行情、技术指标、模拟持仓与交易记录 |
| 缠论与知识库 | 缠论分析入口和本地研究资料 |

### 安装与启动

需要 Python 3.10 或更新版本，建议使用独立虚拟环境。

```bash
git clone https://github.com/ARETE-zzwl/agu-quant.git
cd agu-quant
python -m venv .venv
```

Windows PowerShell 激活环境：

```powershell
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

macOS / Linux：

```bash
source .venv/bin/activate
cp .env.example .env
```

安装项目并启动网页：

```bash
python -m pip install -e .
python -m streamlit run web/app.py --server.port 8501
```

打开 [localhost:8501](http://localhost:8501)。也可以使用安装后的 `agu-quant` 命令进入 CLI，或用 `agu-quant-web` 启动网页。

### 模型配置

在 `.env` 中填入所选服务的 API Key，例如：

```dotenv
DEEPSEEK_API_KEY=your-api-key
```

在侧栏选择供应商和模型。界面提供 DeepSeek、Qwen、GLM、MiniMax、OpenAI、Anthropic、Gemini、xAI 和 Ollama 等选项；具体可用性取决于对应服务、模型和本地配置。

使用 Gemini 时，额外安装：

```bash
python -m pip install -e ".[google]"
```

API 调用可能产生费用。行情接口也可能限流、延迟或暂时不可用。邮箱注册与通知另需配置 Resend，变量见 [.env.example](.env.example)。

### 激活模块

当前界面区分基础功能和赞赏功能。大盘、板块和条件选股列为基础功能；深度分析、AI 选股、因子引擎、股票监控和模拟盘列为赞赏功能。

仓库保留了邮箱试用、激活码和管理员页面。激活页目前显示 99 元/月与 299 元永久套餐；部署这部分功能前，请核对自己的邮箱服务、管理员配置和激活流程。

### 代码位置

```text
web/             Streamlit 页面与组件
cli/             命令行入口
tradingagents/   数据接口、分析流程、因子和模拟交易模块
docs/knowledge_base/  本地研究资料
tests/           测试
```

## English

A Python project for Chinese A-share market views, stock screening, factor research and paper trading, with a Streamlit UI. Stock reports combine market data, news and fundamentals with language-model analysis.

The local interface brings market browsing and strategy experiments together. Paper trading records simulated positions and trades. Check generated reports against the underlying data. This project is for learning and research and does not provide investment advice.

### Modules

Market and sector views, condition-based screening, factor calculation and backtesting, IC/IR and correlation analysis, stock reports, monitoring, paper trading, Chan analysis and a local knowledge base.

### Install and run

Use Python 3.10 or later, preferably in a virtual environment.

```bash
git clone https://github.com/ARETE-zzwl/agu-quant.git
cd agu-quant
python -m venv .venv
```

Activate with `.\.venv\Scripts\Activate.ps1` on Windows PowerShell or `source .venv/bin/activate` on macOS/Linux. Copy `.env.example` to `.env`, then run:

```bash
python -m pip install -e .
python -m streamlit run web/app.py --server.port 8501
```

Open [localhost:8501](http://localhost:8501). Installed commands are `agu-quant` for the CLI and `agu-quant-web` for the web UI.

### Configuration and activation

Set the relevant API key in `.env` and choose a provider and model in the sidebar. Options include DeepSeek, Qwen, GLM, MiniMax, OpenAI, Anthropic, Gemini, xAI and Ollama. Availability depends on the service and configuration. For Gemini, install `python -m pip install -e ".[google]"`.

Model calls may incur charges; market-data sources can be rate-limited, delayed or unavailable. Email registration and notifications require Resend configuration; see [.env.example](.env.example).

The UI lists market views, sectors and screening as basic features, and stock reports, AI picks, factors, monitoring and paper trading as premium features. Email trials, activation codes and an admin page remain in the repository. The activation page currently displays CNY 99/month and CNY 299 lifetime plans. Check your email, admin and activation setup before deploying these features.

### Source layout

`web/` contains Streamlit pages, `cli/` the command-line entry, and `tradingagents/` the data, analysis, factor and paper-trading modules. Research notes live in `docs/knowledge_base/`; tests live in `tests/`.

## License

[Apache-2.0](LICENSE). Required notices are retained in [NOTICE](NOTICE).
