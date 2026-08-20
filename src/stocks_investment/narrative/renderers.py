"""Deterministic narrative renderers; no LLM or provider is used here."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable, cast

from stocks_investment.domain.narrative import NarrativeRequest, NarrativeResult, NarrativeStatus
from stocks_investment.domain.research_intelligence import SourceReference


class StructuredNarrativeRenderer:
    """Render report sections as a traceable narrative without interpretation."""

    name = "structured"
    version = "structured_narrative_v1"

    def render(self, request: NarrativeRequest) -> NarrativeResult:
        report = request.report
        sections = tuple(
            item for item in report.sections
            if request.policy.include_outcomes or item.section_type != "outcome"
        )
        if not sections:
            return NarrativeResult(
                self.name, self.version, request.policy.version,
                NarrativeStatus.INSUFFICIENT_DATA, "", (),
                "research_then_outcome" if request.policy.include_outcomes else "research_only",
            )
        lines = [
            f"Research report: {report.report_type}",
            f"As-of: {report.as_of.isoformat()}",
            "",
        ]
        references: list[SourceReference] = []
        saw_outcome = False
        for section in sections:
            if section.section_type == "outcome" and not saw_outcome:
                lines.extend(("SUBSEQUENT OUTCOME", ""))
                saw_outcome = True
            elif section.section_type != "outcome" and not references:
                lines.extend(("RESEARCH AS OF THE RECORDED DATE", ""))
            lines.append(f"{section.title} [{section.section_type}]")
            lines.append(_json(section.payload))
            lines.append("")
            references.extend(section.source_references)
        text = "\n".join(lines).strip()
        if len(text) > request.policy.max_characters:
            raise ValueError("generated narrative exceeds policy max_characters")
        return NarrativeResult(
            self.name, self.version, request.policy.version, NarrativeStatus.GENERATED,
            text, _unique_refs(references),
            "research_then_outcome" if saw_outcome else "research_only",
        )


class DisabledNarrativeRenderer:
    """Explicit safe result for installations where narrative generation is off."""

    name = "optional_llm"
    version = "optional_llm_disabled_v1"

    def render(self, request: NarrativeRequest) -> NarrativeResult:
        references = _unique_refs(
            reference
            for section in request.report.sections
            for reference in section.source_references
            if section.section_type != "outcome" or request.policy.include_outcomes
        )
        return NarrativeResult(
            self.name, self.version, request.policy.version, NarrativeStatus.DISABLED,
            "", references,
            "research_then_outcome" if request.policy.include_outcomes else "research_only",
        )


def _json(value: object) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True, ensure_ascii=True, allow_nan=False)


def _json_default(value: object) -> object:
    if is_dataclass(value):
        return asdict(cast(Any, value))
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported narrative value: {type(value).__name__}")


def _unique_refs(references: Iterable[SourceReference]) -> tuple[SourceReference, ...]:
    result: list[SourceReference] = []
    seen: set[tuple[str, str, str | None]] = set()
    for reference in references:
        identity = (reference.entity_type, reference.entity_id, reference.field)
        if identity not in seen:
            seen.add(identity)
            result.append(reference)
    return tuple(result)
