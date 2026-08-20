"""Structured research report assembly and edge renderers."""

from stocks_investment.reporting.builder import (
    build_historical_stock_report,
    build_report,
    render_json,
    render_markdown,
)
from stocks_investment.reporting.filings import (
    build_filing_evidence_report,
    build_filing_history_report,
)
from stocks_investment.reporting.automation import (
    build_automation_run_report,
    render_automation_run_json,
    render_automation_run_markdown,
    render_automation_run_text,
)
from stocks_investment.reporting.portfolio_construction import (
    build_portfolio_construction_report,
    render_portfolio_construction_json,
    render_portfolio_construction_markdown,
)

__all__ = [
    "build_filing_evidence_report",
    "build_filing_history_report",
    "build_historical_stock_report",
    "build_report",
    "render_json",
    "render_markdown",
    "build_automation_run_report",
    "render_automation_run_json",
    "render_automation_run_markdown",
    "render_automation_run_text",
    "build_portfolio_construction_report",
    "render_portfolio_construction_json",
    "render_portfolio_construction_markdown",
]
