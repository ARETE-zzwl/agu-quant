<h1 align="center">A股量化系统</h1>

<p align="center">
  AI驱动的A股量化投研平台<br>
  97因子 · 7Agent协作 · 回测验证 · 模拟交易<br>
  <b>开源免费使用，赞赏解锁全部功能</b>
</p>

<p align="center">
  <b>⚠️ 免责声明：本项目仅供学习研究与技术演示，不构成任何投资建议。</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python"/>
  <img src="https://img.shields.io/badge/License-Apache_2.0-green" alt="License"/>
  <img src="https://img.shields.io/badge/平台-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform"/>
</p>

---

## 快速开始

### 1. 下载代码
```bash
git clone https://github.com/YOUR_USERNAME/agu-quant.git
cd agu-quant
```

### 2. 安装依赖
```bash
pip install -e .
```

### 3. 配置API Key
复制 `.env.example` 为 `.env`，填入 DeepSeek API Key：
```
DEEPSEEK_API_KEY=sk-xxxxx
```
> 获取免费/低价 Key: [platform.deepseek.com](https://platform.deepseek.com)

### 4. 启动
```bash
# 方式1: 命令行
streamlit run web/app.py --server.port 8501

# 方式2: Windows双击 启动.bat
```
浏览器打开 `http://localhost:8501`

---

## 功能总览

| 功能 | 说明 | 免费 |
|------|------|:---:|
| 大盘看盘 | 实时指数、涨跌家数、北向资金、热门板块/个股 | ✅ |
| 板块分析 | 90行业+50概念排名，双色Treemap热力图 | ✅ |
| 一键选股 | PE/PB/ROE/市值多条件筛选 | ✅ |
| AI荐股 | 15套策略·97因子评分·DeepSeek点评 | 🔒 |
| 因子引擎 | 8大类97因子·回测·IC/IR分析·AI权重优化 | 🔒 |
| 深度分析 | 7Agent协作·多空辩论·风控决策 | 🔒 |
| 股票监控 | 多周期K线·技术指标·买卖点标记 | 🔒 |
| 模拟盘 | A股真实规则·T+1·涨跌停·行情刷新 | 🔒 |
| PDF导出 | 深度分析报告下载 | 🔒 |

> 🔒 = 赞赏解锁 (99元/月 或 299元/永久)

---

## 系统截图

<p align="center">
  <img src="https://via.placeholder.com/800x450/f97316/ffffff?text=大盘看盘" width="400"/>
  <img src="https://via.placeholder.com/800x450/15803d/ffffff?text=板块热力图" width="400"/>
  <img src="https://via.placeholder.com/800x450/7f1d1d/ffffff?text=AI荐股" width="400"/>
  <img src="https://via.placeholder.com/800x450/1a1a2e/ffffff?text=因子引擎" width="400"/>
</p>

---

## 赞赏支持

| 套餐 | 价格 | 说明 |
|------|------|------|
| 免费版 | ¥0 | 大盘看盘·板块分析·基础选股 |
| 月付赞赏 | ¥99/月 | 全部功能解锁 |
| 永久买断 | ¥299 | 全部功能·永久有效·2台设备 |

**赞赏流程**：微信 `agu_quant` 或 Telegram `@agu_quant_bot` 转账 → 获取激活码 → 软件内激活

**邮箱注册**：启动后在「赞赏激活」页面输入邮箱 → 获取7天免费试用

---

## 技术栈

Python · Streamlit · Plotly · LangChain/LangGraph · DeepSeek · mootdx · 东方财富Push2 · backtrader · Resend

---

## 发布到GitHub

```bash
git add .
git commit -m "v1.0: A股量化系统"
git push origin main
```

## 网页下载

1. GitHub Release: 打包 `dist/` 目录为 zip 上传
2. 或使用网盘: 上传到百度网盘/蓝奏云，分享链接
3. 个人网站: 用 GitHub Pages 建一个简单的下载页

---

<p align="center"><b>⭐ 如果这个项目对你有帮助，请给一个Star！</b></p>
