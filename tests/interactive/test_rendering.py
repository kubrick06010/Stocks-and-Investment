import json
from datetime import date

import pytest

from stocks_investment.domain import (
    ReportSection,
    ResearchView,
    ResearchViewStatus,
    SourceReference,
)
from stocks_investment.domain.research_intelligence import ResearchReport
from stocks_investment.interactive.rendering import render_research_view


def _view(*, hostile: bool = False) -> ResearchView:
    text = "AAA <script>alert(1)</script> [click](javascript:alert(1)) ![x](bad)"
    if hostile:
        text += "\x1b]8;;https://evil.example\x07click\x1b]8;;\x07\x1b[2J\x00"
    report = ResearchReport(
        "historical_stock",
        date(2025, 1, 1),
        ("run-t0",),
        (
            ReportSection("Research", "research", {"summary": text}, (SourceReference("run", "run-t0", "summary"),)),
            ReportSection("Outcome", "outcome", {"forward_return": 0.25}, (SourceReference("outcome", "o1"),)),
        ),
        {"strategy_version": "strategy_v1"},
    )
    return ResearchView("view-1", ResearchViewStatus.VALID, report, (), (), ("warn\x1b[31m",))


def test_json_is_stable_explicit_and_separates_outcome() -> None:
    first = render_research_view(_view(), "json")
    second = render_research_view(_view(), "json")
    assert first == second
    decoded = json.loads(first)
    report = decoded["report"]
    assert report["information_boundary"] == "research_sections_then_outcome_sections"
    assert report["research_sections"][0]["section_type"] == "research"
    assert report["outcome_sections"][0]["section_type"] == "outcome"
    assert "forward_return" not in json.dumps(report["research_sections"])
    assert "strategy_version" in json.dumps(report)


def test_text_and_markdown_neutralize_stored_terminal_html_and_links() -> None:
    text = render_research_view(_view(hostile=True), "text")
    markdown = render_research_view(_view(hostile=True), "markdown")
    for rendered in (text, markdown):
        assert "\x1b" not in rendered
        assert "<script>" not in rendered
        assert "javascript:" not in rendered
        assert "OSC removed" in rendered
        assert "RESEARCH INFORMATION" in rendered or "Research information" in rendered
        assert "SUBSEQUENT OUTCOME" in rendered or "Subsequent outcome information" in rendered


def test_json_rejects_non_finite_numbers() -> None:
    report = ResearchReport("test", date(2025, 1, 1), (), (ReportSection("x", "research", {"x": float("nan")}),))
    view = ResearchView("view", ResearchViewStatus.VALID, report, (), ())
    with pytest.raises(ValueError, match="non-finite"):
        render_research_view(view, "json")


def test_size_limit_fails_without_truncating() -> None:
    with pytest.raises(ValueError, match="max_characters"):
        render_research_view(_view(), "markdown", max_characters=20)


def test_invalid_format_and_limit_fail_explicitly() -> None:
    with pytest.raises(ValueError, match="format"):
        render_research_view(_view(), "html")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="positive"):
        render_research_view(_view(), "text", max_characters=0)


def test_mapping_key_normalization_cannot_silently_overwrite_evidence() -> None:
    report = ResearchReport(
        "test", date(2025, 1, 1), (),
        (ReportSection("x", "research", {"\x1b[2Jkey": 1, "[ANSI removed]key": 2}),),
    )
    with pytest.raises(ValueError, match="collide"):
        render_research_view(
            ResearchView("view", ResearchViewStatus.VALID, report, (), ()), "json"
        )
