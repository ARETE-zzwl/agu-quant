from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fund_center_is_a_standalone_frontend_page():
    page = ROOT / "web" / "pages" / "11_Fund_Center.py"
    text = page.read_text(encoding="utf-8")

    assert page.exists()
    assert "基金中心" in text
    assert "fund-hero" in text
    assert "FUND RESEARCH CONSOLE" in text
    assert "基金筛选" in text
    assert "基金详情" in text
    assert "基金组合" in text
    assert "基金模拟舱" in text
    assert "一键筛选基金" in text
    assert "场内 ETF/LOF" in text
    assert "场外开放式" in text
    assert "股票模拟盘" in text


def test_sidebar_keeps_fund_navigation_separate_from_stock_navigation():
    sidebar = (ROOT / "web" / "components" / "sidebar.py").read_text(encoding="utf-8")

    assert "📋 股票功能" in sidebar
    assert "🧾 基金投资" in sidebar
    assert "pages/11_Fund_Center.py" in sidebar
