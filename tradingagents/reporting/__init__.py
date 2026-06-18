"""Automated report generation and templates."""

from .daily import (
    DailyReportResult,
    load_daily_config,
    normalize_watchlist,
    render_daily_report,
    run_daily_reports,
    save_daily_config,
)

__all__ = [
    "DailyReportResult",
    "load_daily_config",
    "normalize_watchlist",
    "render_daily_report",
    "run_daily_reports",
    "save_daily_config",
]
