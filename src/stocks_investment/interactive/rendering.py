"""Safe, deterministic renderers for frozen :class:`ResearchView` objects.

This module is deliberately an edge adapter.  It never queries providers or
recalculates a report; it only serializes the evidence already present in a
frozen view.  Stored strings are treated as hostile presentation data.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Mapping

from stocks_investment.domain.interactive import ResearchView

RenderFormat = Literal["text", "json", "markdown"]

_ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
_DANGEROUS_SCHEME = re.compile(r"(?i)\b(?:javascript|vbscript|data):")
_MARKDOWN_SPECIAL = str.maketrans({"\\": "\\\\", "`": "\\`", "*": "\\*", "_": "\\_", "[": "\\[", "]": "\\]", "(": "\\(", ")": "\\)", "!": "\\!", "#": "\\#"})


def render_research_view(
    view: ResearchView,
    format: RenderFormat = "text",
    *,
    max_characters: int | None = None,
) -> str:
    """Render a frozen view with explicit research/outcome boundaries.

    ``max_characters`` is a hard bound.  An oversized result raises
    ``ValueError``; it is never silently truncated.
    """

    if format not in {"text", "json", "markdown"}:
        raise ValueError("format must be text, json, or markdown")
    if max_characters is not None and max_characters < 1:
        raise ValueError("max_characters must be positive")

    normalized = _view_payload(view)
    if format == "json":
        rendered = json.dumps(
            normalized,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    elif format == "markdown":
        rendered = _render_markdown(normalized)
    else:
        rendered = _render_text(normalized)

    if max_characters is not None and len(rendered) > max_characters:
        raise ValueError(
            f"rendered research view exceeds max_characters ({len(rendered)} > {max_characters})"
        )
    return rendered


def _view_payload(view: ResearchView) -> dict[str, Any]:
    report = _value(view.report) if view.report is not None else None
    if report is not None:
        sections = report["sections"]
        report["research_sections"] = [item for item in sections if item["section_type"] != "outcome"]
        report["outcome_sections"] = [item for item in sections if item["section_type"] == "outcome"]
        report["information_boundary"] = "research_sections_then_outcome_sections"
    return {
        "request_id": _safe_string(view.request_id),
        "status": _value(view.status),
        "report": report,
        "links": _value(view.links),
        "source_references": _value(view.source_references),
        "warnings": [_safe_string(item) for item in view.warnings],
    }


def _value(value: object) -> Any:
    if isinstance(value, str):
        return _safe_string(value)
    if isinstance(value, Enum):
        return _safe_string(str(value.value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("research view contains non-finite numeric data")
        return value
    if value is None or isinstance(value, (bool, int)):
        return value
    if is_dataclass(value):
        return {field.name: _value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            safe_key = _safe_string(str(key))
            if safe_key in normalized:
                raise ValueError("research view mapping keys collide after safe normalization")
            normalized[safe_key] = _value(item)
        return normalized
    if isinstance(value, (tuple, list)):
        return [_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_value(item) for item in sorted(value, key=repr)]
    raise TypeError(f"unsupported research view value: {type(value).__name__}")


def _safe_string(value: str) -> str:
    value = _ANSI_OSC.sub("[OSC removed]", value)
    value = _ANSI_CSI.sub("[ANSI removed]", value)
    value = value.replace("\x1b", r"\x1b")
    value = "".join(
        character if ord(character) >= 32 and ord(character) != 127 else rf"\x{ord(character):02x}"
        for character in value
    )
    value = _DANGEROUS_SCHEME.sub("[scheme removed]:", value)
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_text(payload: Mapping[str, Any]) -> str:
    lines = [f"Research view: {payload['request_id']}", f"Status: {payload['status']}"]
    report = payload["report"]
    if report is not None:
        lines.extend([f"Report: {report['report_type']}", "RESEARCH INFORMATION"])
        lines.extend(_section_text(section) for section in report["research_sections"])
        lines.append("SUBSEQUENT OUTCOME INFORMATION")
        lines.extend(_section_text(section) for section in report["outcome_sections"])
    if payload["warnings"]:
        lines.append("WARNINGS: " + " | ".join(payload["warnings"]))
    return "\n".join(lines)


def _section_text(section: Mapping[str, Any]) -> str:
    source = ", ".join(_source_text(item) for item in section["source_references"])
    body = json.dumps(section["payload"], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return f"[{section['section_type']}] {section['title']}: {body}" + (f" (sources: {source})" if source else "")


def _source_text(source: Mapping[str, Any]) -> str:
    suffix = f".{source['field']}" if source.get("field") else ""
    return f"{source['entity_type']}:{source['entity_id']}{suffix}"


def _render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [f"# {_md(payload['request_id'])}", f"- Status: {_md(payload['status'])}"]
    report = payload["report"]
    if report is not None:
        lines.extend([f"- Report: {_md(report['report_type'])}", "", "## Research information"])
        lines.extend(_section_markdown(section) for section in report["research_sections"])
        lines.extend(["", "## Subsequent outcome information"])
        lines.extend(_section_markdown(section) for section in report["outcome_sections"])
    if payload["warnings"]:
        lines.extend(["", "## Warnings", "- " + "\n- ".join(_md(item) for item in payload["warnings"])])
    return "\n".join(lines)


def _section_markdown(section: Mapping[str, Any]) -> str:
    title = _md(str(section["title"]))
    section_type = _md(str(section["section_type"]))
    sources = ", ".join(_md(_source_text(item)) for item in section["source_references"])
    body = _md(json.dumps(section["payload"], ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    suffix = f" — sources: {sources}" if sources else ""
    return f"### {title}\n- Section type: {section_type}{suffix}\n- Payload: `{body}`"


def _md(value: str) -> str:
    return value.translate(_MARKDOWN_SPECIAL)
