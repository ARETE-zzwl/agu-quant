"""Windows desktop launcher for the bundled Streamlit application."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


HOST = "127.0.0.1"
PORT = int(os.getenv("TA_WEB_PORT", "8501"))
_CHILD_FLAG = "--streamlit-child"
_DAILY_FLAG = "--daily-report"


def _bundle_imports() -> None:
    """Expose runtime-loaded Web dependencies to PyInstaller's static analysis."""
    import backtrader  # noqa: F401
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import plotly.express  # noqa: F401
    import plotly.graph_objects  # noqa: F401
    import stockstats  # noqa: F401
    import yfinance  # noqa: F401
    from fpdf import FPDF  # noqa: F401
    from langchain_anthropic import ChatAnthropic  # noqa: F401
    from langchain_openai import ChatOpenAI  # noqa: F401
    from langgraph.graph import StateGraph  # noqa: F401
    from mootdx.quotes import Quotes  # noqa: F401
    from tradingagents import factors  # noqa: F401
    from tradingagents.chan import analyze_chan  # noqa: F401
    from tradingagents.fund_center import fetch_fund_profile  # noqa: F401
    from tradingagents.fund_paper_trade import get_fund_account  # noqa: F401
    from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: F401
    from tradingagents.paper_trade import get_account  # noqa: F401
    from tradingagents.ranking.recommendation_engine import run_one_click_recommendation  # noqa: F401
    from tradingagents.ranking.scoring_engine import ScoringEngine  # noqa: F401


def _bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _app_path() -> Path:
    return _bundle_root() / "web" / "app.py"


def _streamlit_args() -> list[str]:
    return [
        "streamlit",
        "run",
        str(_app_path()),
        "--server.address",
        HOST,
        "--server.port",
        str(PORT),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.3)
        return connection.connect_ex((HOST, port)) == 0


def _run_streamlit_child() -> None:
    from streamlit.web import cli as streamlit_cli

    sys.argv = _streamlit_args()
    raise SystemExit(streamlit_cli.main())


def _child_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, _CHILD_FLAG]
    return [sys.executable, "-m", *_streamlit_args()]


def _wait_until_ready(process: subprocess.Popen, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        if _port_in_use(PORT):
            return True
        time.sleep(0.25)
    return False


def main() -> int:
    if _DAILY_FLAG in sys.argv:
        from tradingagents.reporting.daily import main as daily_main

        daily_args = [arg for arg in sys.argv[1:] if arg != _DAILY_FLAG]
        return daily_main(daily_args)
    if _CHILD_FLAG in sys.argv:
        _run_streamlit_child()
        return 0

    url = f"http://{HOST}:{PORT}"
    if _port_in_use(PORT):
        webbrowser.open(url)
        return 0

    process = subprocess.Popen(_child_command())
    if not _wait_until_ready(process):
        process.terminate()
        return 1

    webbrowser.open(url)
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
