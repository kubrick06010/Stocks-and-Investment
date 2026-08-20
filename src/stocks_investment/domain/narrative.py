"""Evidence-bound narrative contracts; no model or provider is required."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .research_intelligence import ResearchReport, SourceReference


class NarrativeStatus(StrEnum):
    GENERATED = "generated"
    DISABLED = "disabled"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class NarrativePolicy:
    name: str
    version: str
    include_outcomes: bool = False
    max_characters: int = 20_000

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("narrative policy identity is required")
        if not 1 <= self.max_characters <= 1_000_000:
            raise ValueError("narrative max_characters must be in 1..1000000")


@dataclass(frozen=True, slots=True)
class NarrativeResult:
    renderer_name: str
    renderer_version: str
    policy_version: str
    status: NarrativeStatus
    text: str
    source_references: tuple[SourceReference, ...]
    information_boundary: str

    def __post_init__(self) -> None:
        if not self.renderer_name.strip() or not self.renderer_version.strip() or not self.policy_version.strip():
            raise ValueError("narrative renderer and policy identities are required")
        if self.status is NarrativeStatus.GENERATED and not self.text.strip():
            raise ValueError("generated narrative requires text")
        if self.information_boundary not in {"research_only", "research_then_outcome"}:
            raise ValueError("narrative information boundary is invalid")
        identities = tuple(
            (item.entity_type, item.entity_id, item.field) for item in self.source_references
        )
        if len(identities) != len(set(identities)):
            raise ValueError("narrative source references must be unique")


@dataclass(frozen=True, slots=True)
class NarrativeRequest:
    report: ResearchReport
    policy: NarrativePolicy
