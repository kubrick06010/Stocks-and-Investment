"""Deterministic, identity-safe comparison of persisted filing sections.

This module compares already parsed, immutable evidence.  It deliberately does
not fetch filings, interpret their meaning, or make causal claims about a
change.  Section identity is the normalized pair ``(item, kind)``; ordinal
position is never used for alignment.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import re
from typing import Iterable

from stocks_investment.domain.filings import (
    FilingChangeType,
    FilingDocument,
    FilingEvidenceReference,
    FilingSection,
    FilingSectionChange,
)


DEFAULT_METHODOLOGY_VERSION = "filing_section_diff_v1"
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class SectionDiffPolicy:
    """Versioned thresholds for transparent token-level comparison."""

    methodology_version: str = DEFAULT_METHODOLOGY_VERSION
    unchanged_similarity_threshold: float = 0.98
    material_similarity_threshold: float = 0.90

    def __post_init__(self) -> None:
        if not self.methodology_version.strip():
            raise ValueError("methodology version is required")
        if not 0 <= self.material_similarity_threshold <= self.unchanged_similarity_threshold <= 1:
            raise ValueError(
                "thresholds must satisfy 0 <= material <= unchanged <= 1"
            )


class FilingHistoryComparator:
    """Compare two filings without positional or current-data fallbacks."""

    version = DEFAULT_METHODOLOGY_VERSION

    def __init__(
        self,
        policy: SectionDiffPolicy | None = None,
        *,
        allow_parser_mismatch: bool = False,
    ) -> None:
        self.policy = policy or SectionDiffPolicy()
        self.version = self.policy.methodology_version
        self.allow_parser_mismatch = allow_parser_mismatch

    def compare(
        self,
        previous_filing: FilingDocument,
        previous_sections: Iterable[FilingSection],
        current_filing: FilingDocument,
        current_sections: Iterable[FilingSection],
    ) -> tuple[FilingSectionChange, ...]:
        """Return deterministic changes keyed by normalized item and section kind."""
        if previous_filing.id == current_filing.id:
            raise ValueError("cannot compare a filing with itself")
        if previous_filing.ticker != current_filing.ticker:
            raise ValueError("filing comparison requires matching tickers")
        if current_filing.available_at < previous_filing.available_at:
            raise ValueError("filing comparison cannot move from future to past")

        previous = self._index(previous_sections, previous_filing.id)
        current = self._index(current_sections, current_filing.id)
        parser_versions = {section.parser_version for section in (*previous.values(), *current.values())}
        if len(parser_versions) > 1 and not self.allow_parser_mismatch:
            raise ValueError("parser-version mismatch requires explicit opt-in")

        changes: list[FilingSectionChange] = []
        for identity in sorted(set(previous) | set(current)):
            before = previous.get(identity)
            after = current.get(identity)
            if before is None:
                if after is None:
                    raise AssertionError("section identity index lost during comparison")
                changes.append(self._added(previous_filing, current_filing, after, identity))
            elif after is None:
                changes.append(self._removed(previous_filing, current_filing, before, identity))
            else:
                changes.append(self._matched(previous_filing, before, current_filing, after, identity))
        return tuple(changes)

    def _index(
        self, sections: Iterable[FilingSection], filing_id: str
    ) -> dict[tuple[str, str], FilingSection]:
        indexed: dict[tuple[str, str], FilingSection] = {}
        for section in sections:
            if section.filing_id != filing_id:
                raise ValueError("section does not belong to its filing")
            identity = (_normalize_identity(section.item), section.kind.value)
            if identity in indexed:
                raise ValueError(f"duplicate section identity: {identity!r}")
            indexed[identity] = section
        return indexed

    def _added(
        self,
        previous_filing: FilingDocument,
        current_filing: FilingDocument,
        section: FilingSection,
        identity: tuple[str, str],
    ) -> FilingSectionChange:
        return self._change(
            previous_filing,
            current_filing,
            None,
            section,
            FilingChangeType.SECTION_ADDED,
            None,
            True,
            f"section {identity[0]} ({identity[1]}) is present only in the later filing",
        )

    def _removed(
        self,
        previous_filing: FilingDocument,
        current_filing: FilingDocument,
        section: FilingSection,
        identity: tuple[str, str],
    ) -> FilingSectionChange:
        return self._change(
            previous_filing,
            current_filing,
            section,
            None,
            FilingChangeType.SECTION_REMOVED,
            None,
            True,
            f"section {identity[0]} ({identity[1]}) is present only in the earlier filing",
        )

    def _matched(
        self,
        previous_filing: FilingDocument,
        before: FilingSection,
        current_filing: FilingDocument,
        after: FilingSection,
        identity: tuple[str, str],
    ) -> FilingSectionChange:
        similarity = _token_similarity(before.normalized_text, after.normalized_text)
        unchanged = similarity >= self.policy.unchanged_similarity_threshold
        material = similarity < self.policy.material_similarity_threshold
        change_type = (
            FilingChangeType.SECTION_UNCHANGED if unchanged else FilingChangeType.SECTION_MODIFIED
        )
        if unchanged:
            rationale = (
                f"section {identity[0]} ({identity[1]}) is unchanged under token similarity "
                f"{similarity:.6f}"
            )
        else:
            rationale = (
                f"section {identity[0]} ({identity[1]}) matched by identity and has token "
                f"similarity {similarity:.6f}; material={material}"
            )
        return self._change(
            previous_filing,
            current_filing,
            before,
            after,
            change_type,
            similarity,
            material,
            rationale,
        )

    def _change(
        self,
        from_filing: FilingDocument,
        to_filing: FilingDocument,
        before: FilingSection | None,
        after: FilingSection | None,
        change_type: FilingChangeType,
        similarity: float | None,
        material: bool,
        rationale: str,
    ) -> FilingSectionChange:
        refs = tuple(
            reference
            for reference in (
                _reference(before),
                _reference(after),
            )
            if reference is not None
        )
        identity = "|".join(
            (
                from_filing.id,
                to_filing.id,
                before.id if before else "",
                after.id if after else "",
                change_type.value,
                self.policy.methodology_version,
            )
        )
        change_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return FilingSectionChange(
            id=change_id,
            ticker=from_filing.ticker,
            from_filing_id=from_filing.id,
            to_filing_id=to_filing.id,
            from_section_id=before.id if before else None,
            to_section_id=after.id if after else None,
            change_type=change_type,
            methodology_version=self.policy.methodology_version,
            similarity=similarity,
            material=material,
            rationale=rationale,
            source_references=refs,
        )


def compare_filing_sections(
    previous_filing: FilingDocument,
    previous_sections: Iterable[FilingSection],
    current_filing: FilingDocument,
    current_sections: Iterable[FilingSection],
    *,
    policy: SectionDiffPolicy | None = None,
    allow_parser_mismatch: bool = False,
) -> tuple[FilingSectionChange, ...]:
    """Convenience wrapper around :class:`FilingHistoryComparator`."""
    return FilingHistoryComparator(
        policy=policy,
        allow_parser_mismatch=allow_parser_mismatch,
    ).compare(previous_filing, previous_sections, current_filing, current_sections)


def _normalize_identity(value: str) -> str:
    return " ".join(value.split()).casefold()


def _token_similarity(left: str, right: str) -> float:
    left_tokens = tuple(_TOKEN_RE.findall(left.casefold()))
    right_tokens = tuple(_TOKEN_RE.findall(right.casefold()))
    if not left_tokens and not right_tokens:
        return 1.0
    return SequenceMatcher(None, left_tokens, right_tokens, autojunk=False).ratio()


def _reference(section: FilingSection | None) -> FilingEvidenceReference | None:
    if section is None:
        return None
    return FilingEvidenceReference(
        filing_id=section.filing_id,
        section_id=section.id,
        source_start=section.source_start,
        source_end=section.source_end,
        excerpt_hash=section.content_hash,
    )
