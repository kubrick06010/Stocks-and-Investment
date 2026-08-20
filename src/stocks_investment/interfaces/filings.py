"""Provider-independent service seams for filing intelligence."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Protocol

from stocks_investment.domain.filings import (
    FilingDocument,
    FilingEvidenceSnapshot,
    FilingSection,
    FilingSectionChange,
    QualitativeClaim,
)
from stocks_investment.domain.models import Ticker


class FilingDocumentProvider(Protocol):
    name: str

    def filings(self, ticker: Ticker, as_of: date) -> Iterable[FilingDocument]: ...

    def content(self, filing: FilingDocument) -> bytes: ...


class FilingParser(Protocol):
    version: str

    def parse(self, filing: FilingDocument, content: bytes) -> tuple[FilingSection, ...]: ...


class QualitativeClaimBuilder(Protocol):
    version: str

    def build(
        self, filing: FilingDocument, sections: Iterable[FilingSection], as_of: date
    ) -> tuple[QualitativeClaim, ...]: ...


class FilingChangeDetector(Protocol):
    version: str

    def compare(
        self,
        previous_filing: FilingDocument,
        previous_sections: Iterable[FilingSection],
        current_filing: FilingDocument,
        current_sections: Iterable[FilingSection],
    ) -> tuple[FilingSectionChange, ...]: ...


class FilingEvidenceReader(Protocol):
    def filing_snapshot(self, ticker: Ticker, as_of: date) -> FilingEvidenceSnapshot | None: ...

    def filings_available_on(self, ticker: Ticker, as_of: date) -> tuple[FilingDocument, ...]: ...
