from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest


def _sample_state() -> dict:
    return {
        "market_report": "<think>hidden</think>技术面保持震荡。",
        "sentiment_report": "市场情绪中性。",
        "news_report": "暂无重大新闻。",
        "fundamentals_report": "基本面稳定。",
        "policy_report": "政策环境平稳。",
        "hot_money_report": "未见异常席位。",
        "lockup_report": "近期无重大解禁。",
        "investment_debate_state": {"judge_decision": "多空分歧有限。"},
        "risk_debate_state": {"judge_decision": "控制单一标的仓位。"},
        "investment_plan": "保持观察。",
        "final_trade_decision": "**Rating**: HOLD\n等待更明确的信号。",
    }


def test_normalize_watchlist_deduplicates_and_limits_codes():
    from tradingagents.reporting.daily import normalize_watchlist

    assert normalize_watchlist("600519, 000001\n600519") == ["600519", "000001"]
    with pytest.raises(ValueError, match="最多"):
        normalize_watchlist(",".join(f"{index:06d}" for index in range(21)))
    with pytest.raises(ValueError):
        normalize_watchlist("../../etc/passwd")


def test_markdown_templates_render_distinct_report_depths():
    from tradingagents.reporting.daily import render_daily_report

    generated_at = datetime(2026, 6, 18, 18, 0)
    brief = render_daily_report(_sample_state(), "600519", "2026-06-18", "Hold", "brief", generated_at)
    full = render_daily_report(_sample_state(), "600519", "2026-06-18", "Hold", "full", generated_at)
    risk = render_daily_report(_sample_state(), "600519", "2026-06-18", "Hold", "risk", generated_at)

    assert "600519 每日投研简报" in brief
    assert "hidden" not in brief
    assert "技术面保持震荡" in brief
    assert "基本面稳定" in full
    assert "控制单一标的仓位" in risk
    assert "未见异常席位" in risk
    assert "不构成证券投资咨询" in brief


def test_run_daily_reports_writes_success_and_continues_after_failure(tmp_path):
    from tradingagents.reporting.daily import run_daily_reports

    class FakeGraph:
        def propagate(self, ticker, trade_date):
            if ticker == "000001":
                raise RuntimeError("provider unavailable")
            return _sample_state(), "Hold"

    results = run_daily_reports(
        ["600519", "000001"],
        "2026-06-18",
        "brief",
        output_dir=tmp_path,
        graph_factory=lambda _config: FakeGraph(),
        config={},
    )

    assert results[0].success
    assert results[0].path and results[0].path.exists()
    assert "600519 每日投研简报" in results[0].path.read_text(encoding="utf-8")
    assert not results[1].success
    assert "provider unavailable" in results[1].error


def test_daily_schedule_config_round_trip(tmp_path):
    from tradingagents.reporting.daily import load_daily_config, save_daily_config

    config_path = tmp_path / "daily-report.json"
    save_daily_config(["600519", "000001"], "risk", config_path)

    loaded = load_daily_config(config_path)
    assert loaded == {"tickers": ["600519", "000001"], "template": "risk"}


def test_daily_report_page_and_windows_scheduler_are_connected():
    root = Path(__file__).resolve().parents[1]
    page = root / "web" / "pages" / "13_Daily_Reports.py"
    scheduler = root / "scripts" / "install_daily_task.ps1"
    sidebar = (root / "web" / "components" / "sidebar.py").read_text(encoding="utf-8")

    assert page.exists()
    assert scheduler.exists()
    assert "pages/13_Daily_Reports.py" in sidebar
    page_text = page.read_text(encoding="utf-8")
    assert "每日投研报告" in page_text
    assert "save_daily_config" in page_text
    assert "run_daily_reports" in page_text
    assert 'require_premium_page("每日投研报告", required_plan="pro")' in page_text
    scheduler_text = scheduler.read_text(encoding="utf-8")
    assert "schtasks" in scheduler_text
    assert "TradingAgents-Astock-Daily" in scheduler_text
    assert scheduler_text.isascii()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'tradingagents = ["reporting/templates/*.md"]' in pyproject
