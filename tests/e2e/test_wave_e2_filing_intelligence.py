from datetime import date, datetime, timezone
import json
from pathlib import Path

from stocks_investment.data.providers._http import HttpResponse
from stocks_investment.data.providers.sec_filings import SecFilingsProvider
from stocks_investment.domain import FilingEvidenceSnapshot, FilingSectionKind, Ticker
from stocks_investment.filings.claims import DisclosedRiskPattern, build_disclosed_risk_claims
from stocks_investment.filings.history import compare_filing_sections
from stocks_investment.filings.parser import SafeFilingParser
from stocks_investment.storage import SQLiteStorage


OLD_HTML = b"""<!doctype html><html><body>
<h1>Item 1A Risk Factors</h1>
<p>We may depend on a limited number of suppliers.</p>
<h1>Item 7 Management's Discussion and Analysis</h1><p>Stable demand.</p>
</body></html>"""
NEW_HTML = b"""<!doctype html><html><body>
<h1>Item 1A Risk Factors</h1>
<p>We may depend on a limited number of suppliers. Cybersecurity incidents may disrupt operations.</p>
<h1>Item 7 Management's Discussion and Analysis</h1><p>Demand softened.</p>
</body></html>"""


def _submissions() -> bytes:
    recent = {
        "accessionNumber": ["0000000001-24-000001", "0000000001-25-000001"],
        "filingDate": ["2024-02-15", "2025-02-14"],
        "acceptanceDateTime": ["2024-02-15T21:00:00Z", "2025-02-14T21:00:00Z"],
        "reportDate": ["2023-12-31", "2024-12-31"],
        "form": ["10-K", "10-K"],
        "primaryDocument": ["old.htm", "new.htm"],
    }
    return json.dumps({"filings": {"recent": recent}}).encode()


def test_sec_filing_evidence_claims_changes_and_persistence_are_pit(tmp_path: Path) -> None:
    calls: list[str] = []

    def transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        calls.append(url)
        if "submissions" in url:
            return HttpResponse(_submissions(), 200)
        return HttpResponse(OLD_HTML if url.endswith("old.htm") else NEW_HTML, 200)

    provider = SecFilingsProvider(
        user_agent="wave-e2-tests research@example.com",
        ticker_map={"AAA": "1"},
        transport=transport,
        clock=lambda: datetime(2025, 3, 1, tzinfo=timezone.utc),
        retries=0,
    )
    ticker = Ticker("AAA")
    early = tuple(provider.filings(ticker, date(2024, 12, 31)))
    all_filings = tuple(provider.filings(ticker, date(2025, 2, 14)))
    assert len(early) == 1
    assert len(all_filings) == 2
    old, current = all_filings
    assert current not in early

    parser = SafeFilingParser()
    old_sections = parser.parse(old, provider.content(old))
    current_sections = parser.parse(current, provider.content(current))
    assert tuple(item.kind for item in current_sections) == (
        FilingSectionKind.RISK_FACTORS,
        FilingSectionKind.MD_AND_A,
    )
    claims = build_disclosed_risk_claims(
        current,
        current_sections,
        as_of=current.available_at.date(),
        patterns=(DisclosedRiskPattern("cybersecurity", "Cybersecurity incidents"),),
        created_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )
    assert len(claims) == 1
    changes = compare_filing_sections(old, old_sections, current, current_sections)
    assert any(change.material for change in changes)
    snapshot = FilingEvidenceSnapshot(
        "aaa-filings-2025", ticker, current.available_at.date(),
        (old.id, current.id), tuple(item.id for item in (*old_sections, *current_sections)),
        tuple(item.id for item in claims), "filing_snapshot_v1",
        datetime(2025, 3, 1, tzinfo=timezone.utc),
    )

    path = tmp_path / "wave-e2.db"
    with SQLiteStorage(path) as storage:
        for filing, content in ((old, OLD_HTML), (current, NEW_HTML)):
            storage.save_raw_payload(
                provider=provider.name,
                endpoint=filing.source_url,
                parameters={"accession": filing.accession_number},
                payload=content.decode(),
                retrieved_at=filing.retrieved_at,
            )
            storage.save_filing_document(filing)
        for section in (*old_sections, *current_sections):
            storage.save_filing_section(section)
        for claim in claims:
            storage.save_qualitative_claim(claim)
        for change in changes:
            storage.save_filing_section_change(change)
        storage.save_filing_evidence_snapshot(snapshot)

    provider_calls_before_reopen = tuple(calls)
    with SQLiteStorage(path) as reopened:
        assert reopened.load_filings_available_on(ticker, date(2024, 12, 31)) == (old,)
        assert reopened.load_filings_available_on(ticker, date(2025, 2, 14)) == (old, current)
        assert reopened.load_filing_sections(current.id) == current_sections
        assert reopened.load_qualitative_claims(filing_id=current.id) == claims
        assert {
            item.id: item for item in reopened.load_filing_section_changes(ticker)
        } == {item.id: item for item in changes}
        assert reopened.load_filing_evidence_snapshot(snapshot.id) == snapshot
    assert tuple(calls) == provider_calls_before_reopen
