from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AI_PICKS = ROOT / "web" / "pages" / "4_AI_Picks.py"
SMALL_CAPITAL = ROOT / "web" / "pages" / "14_Small_Capital.py"


def test_original_ai_picks_page_is_not_modified_by_small_capital_controls():
    text = AI_PICKS.read_text(encoding="utf-8")

    assert 'max_positions=10' in text
    assert '可用资金（元）' not in text
    assert 'small_account_plan' not in text
    assert '🤝 多策略共识' not in text


def test_small_capital_has_a_dedicated_page_and_session_state():
    text = SMALL_CAPITAL.read_text(encoding="utf-8")

    assert 'page_title="小资金策略"' in text
    assert 'run_small_account_strategy' in text
    assert '小资金策略结果' in text
    assert 'small_capital_result' in text
    assert '加入模拟仓候选' in text
