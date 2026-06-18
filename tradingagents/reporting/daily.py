"""Generate scheduled Markdown research reports for an A-share watchlist."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable

from tradingagents.default_config import DEFAULT_CONFIG


TEMPLATE_NAMES = ("brief", "full", "risk")
DEFAULT_CONFIG_PATH = Path.home() / ".tradingagents" / "daily-report.json"
DEFAULT_OUTPUT_DIR = Path.home() / ".tradingagents" / "daily_reports"
_TICKER_RE = re.compile(r"^\d{6}$")
_THINK_RE = re.compile(r"<think>.*?</think>\s*", flags=re.DOTALL)


@dataclass(frozen=True)
class DailyReportResult:
    ticker: str
    success: bool
    path: Path | None = None
    signal: str = ""
    error: str = ""


def normalize_watchlist(raw: str | Iterable[str], limit: int = 20) -> list[str]:
    values = re.split(r"[,\s]+", raw.strip()) if isinstance(raw, str) else list(raw)
    tickers: list[str] = []
    for value in values:
        ticker = str(value or "").strip()
        if not ticker:
            continue
        if not _TICKER_RE.fullmatch(ticker):
            raise ValueError(f"无效股票代码: {ticker}，自动日报仅接受 6 位代码")
        if ticker not in tickers:
            tickers.append(ticker)
    if not tickers:
        raise ValueError("请至少配置一个股票代码")
    if len(tickers) > limit:
        raise ValueError(f"自动日报最多支持 {limit} 只股票")
    return tickers


def _validate_template(template: str) -> str:
    value = str(template or "").strip().lower()
    if value not in TEMPLATE_NAMES:
        raise ValueError(f"未知报告模板: {template}")
    return value


def _clean(value: object) -> str:
    return _THINK_RE.sub("", str(value or "")).strip() or "暂无数据"


def _nested(state: dict, section: str, key: str) -> str:
    value = state.get(section)
    return _clean(value.get(key, "")) if isinstance(value, dict) else "暂无数据"


def _template_path(template: str) -> Path:
    return Path(__file__).with_name("templates") / f"{_validate_template(template)}.md"


def render_daily_report(
    state: dict,
    ticker: str,
    trade_date: str,
    signal: str,
    template: str = "brief",
    generated_at: datetime | None = None,
) -> str:
    generated = generated_at or datetime.now()
    template_text = _template_path(template).read_text(encoding="utf-8")
    values = {
        "ticker": ticker,
        "trade_date": trade_date,
        "generated_at": generated.strftime("%Y-%m-%d %H:%M"),
        "signal": _clean(signal),
        "market_report": _clean(state.get("market_report")),
        "sentiment_report": _clean(state.get("sentiment_report")),
        "news_report": _clean(state.get("news_report")),
        "fundamentals_report": _clean(state.get("fundamentals_report")),
        "policy_report": _clean(state.get("policy_report")),
        "hot_money_report": _clean(state.get("hot_money_report")),
        "lockup_report": _clean(state.get("lockup_report")),
        "debate_decision": _nested(state, "investment_debate_state", "judge_decision"),
        "risk_decision": _nested(state, "risk_debate_state", "judge_decision"),
        "investment_plan": _clean(state.get("investment_plan")),
        "final_decision": _clean(state.get("final_trade_decision")),
    }
    return template_text.format_map(values).rstrip() + "\n"


def save_daily_config(
    tickers: str | Iterable[str],
    template: str,
    path: str | Path = DEFAULT_CONFIG_PATH,
) -> Path:
    destination = Path(path)
    payload = {
        "tickers": normalize_watchlist(tickers),
        "template": _validate_template(template),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination


def load_daily_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("自动日报配置格式无效")
    return {
        "tickers": normalize_watchlist(data.get("tickers", [])),
        "template": _validate_template(data.get("template", "brief")),
    }


def build_daily_graph_config() -> dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["llm_provider"] = os.getenv("TA_DAILY_LLM_PROVIDER", "deepseek")
    config["quick_think_llm"] = os.getenv("TA_DAILY_QUICK_MODEL", "deepseek-chat")
    config["deep_think_llm"] = os.getenv("TA_DAILY_DEEP_MODEL", "deepseek-chat")
    config["output_language"] = "Chinese"
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["data_vendors"] = {key: "a_stock" for key in config["data_vendors"]}
    return config


def _default_graph_factory(config: dict):
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    return TradingAgentsGraph(debug=False, config=config)


def run_daily_reports(
    tickers: str | Iterable[str],
    trade_date: str,
    template: str = "brief",
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    graph_factory: Callable[[dict], object] = _default_graph_factory,
    config: dict | None = None,
) -> list[DailyReportResult]:
    normalized = normalize_watchlist(tickers)
    template_name = _validate_template(template)
    datetime.strptime(trade_date, "%Y-%m-%d")
    day_dir = Path(output_dir) / trade_date
    day_dir.mkdir(parents=True, exist_ok=True)
    graph_config = config if config is not None else build_daily_graph_config()

    results: list[DailyReportResult] = []
    for ticker in normalized:
        try:
            graph = graph_factory(graph_config)
            state, signal = graph.propagate(ticker, trade_date)
            report = render_daily_report(state, ticker, trade_date, signal, template_name)
            report_path = day_dir / f"{ticker}_{template_name}.md"
            report_path.write_text(report, encoding="utf-8")
            results.append(DailyReportResult(ticker, True, report_path, str(signal)))
        except Exception as exc:
            results.append(DailyReportResult(ticker, False, error=str(exc)))
    return results


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate daily A-share research reports")
    parser.add_argument("--tickers", default="")
    parser.add_argument("--template", choices=TEMPLATE_NAMES, default="brief")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--save-config", action="store_true")
    parser.add_argument("--configure-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.tickers:
        tickers = normalize_watchlist(args.tickers)
        template = args.template
        if args.save_config:
            save_daily_config(tickers, template)
    else:
        saved = load_daily_config()
        tickers = saved["tickers"]
        template = saved["template"]

    if args.configure_only:
        return 0

    results = run_daily_reports(tickers, args.date, template, args.output_dir)
    for result in results:
        if result.success:
            print(f"[OK] {result.ticker}: {result.path}")
        else:
            print(f"[ERROR] {result.ticker}: {result.error}")
    return 0 if all(result.success for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
