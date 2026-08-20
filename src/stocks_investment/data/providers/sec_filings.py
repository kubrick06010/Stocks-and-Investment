"""Bounded, point-in-time SEC filing metadata and content acquisition.

This adapter deliberately stops at immutable evidence acquisition.  It does not
parse filing sections, interpret issuer text, or call any provider other than
the SEC endpoints it constructs from a CIK and accession number.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timezone
from typing import Any
from urllib.parse import urlparse

from stocks_investment.data.providers._http import (
    HttpResponse,
    ProviderError,
    ProviderSchemaError,
    ProviderTimeoutError,
    Transport,
)
from stocks_investment.domain.filings import FilingDocument, FilingForm
from stocks_investment.domain.models import DataProvenance, Ticker


class SecFilingProviderError(ProviderError):
    """Expected SEC acquisition or validation failure."""


Clock = Callable[[], datetime]


class SecFilingsProvider:
    """Fetch accepted SEC submissions and their primary HTML/text documents.

    ``filings`` fetches and validates primary-document bytes so returned
    ``FilingDocument`` objects are content-addressed and reproducible.  The
    injected transport and clock make all normal tests offline and deterministic.
    """

    name = "sec-edgar-filings"
    _submissions_root = "https://data.sec.gov/submissions"
    _archive_root = "https://www.sec.gov/Archives/edgar/data"
    _allowed_forms = frozenset(FilingForm)
    _allowed_mime_types = frozenset({"text/html", "application/xhtml+xml", "text/plain"})

    def __init__(
        self,
        *,
        user_agent: str,
        ticker_map: dict[str, str] | None = None,
        timeout: float = 10.0,
        retries: int = 2,
        backoff: float = 0.0,
        max_metadata_bytes: int = 2_000_000,
        max_content_bytes: int = 20_000_000,
        transport: Transport | None = None,
        clock: Clock | None = None,
    ) -> None:
        if not user_agent.strip() or "@" not in user_agent:
            raise ValueError("SEC user_agent must identify the application and contact")
        if timeout <= 0 or retries < 0 or backoff < 0:
            raise ValueError("timeout must be positive and retries/backoff non-negative")
        if max_metadata_bytes <= 0 or max_content_bytes <= 0:
            raise ValueError("response limits must be positive")
        self.user_agent = user_agent.strip()
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.max_metadata_bytes = max_metadata_bytes
        self.max_content_bytes = max_content_bytes
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._ticker_map = {
            ticker.upper(): _normalize_cik(cik) for ticker, cik in (ticker_map or {}).items()
        }
        self._content_cache: dict[str, bytes] = {}

    def filings(self, ticker: Ticker, as_of: date) -> Iterable[FilingDocument]:
        """Return accepted, allowed filings public on or before ``as_of``."""
        cik = self._cik(ticker)
        metadata = self._request_json(f"{self._submissions_root}/CIK{cik}.json")
        recent = _recent_filings(metadata)
        documents: list[FilingDocument] = []
        for entry in recent:
            form = _filing_form(entry.get("form"))
            if form is None:
                continue
            accession = _required_text(entry, "accessionNumber")
            filed_date = _parse_date(entry.get("filingDate"), "filingDate")
            acceptance = _parse_datetime(entry.get("acceptanceDateTime"))
            available_at = acceptance or _utc_midnight(filed_date)
            if available_at.date() > as_of:
                continue
            primary_document = _required_text(entry, "primaryDocument")
            period_end = _optional_date(entry.get("reportDate"), "reportDate")
            source_url = _archive_url(cik, accession, primary_document)
            content = self._fetch_content(source_url)
            documents.append(
                _document(
                    ticker=ticker,
                    cik=cik,
                    accession=accession,
                    form=form,
                    filed_date=filed_date,
                    available_at=available_at,
                    period_end=period_end,
                    primary_document=primary_document,
                    source_url=source_url,
                    content=content,
                    retrieved_at=self._retrieved_at(available_at),
                )
            )
        return tuple(sorted(documents, key=lambda item: (item.available_at, item.accession_number)))

    def content(self, filing: FilingDocument) -> bytes:
        """Return bytes matching the document's recorded content hash."""
        content = self._content_cache.get(filing.source_url)
        if content is None:
            content = self._fetch_content(filing.source_url)
        digest = hashlib.sha256(content).hexdigest()
        if digest != filing.content_hash or len(content) != filing.size_bytes:
            raise SecFilingProviderError(f"SEC content changed for filing {filing.id}")
        return content

    def _cik(self, ticker: Ticker) -> str:
        try:
            return self._ticker_map[ticker.symbol]
        except KeyError as exc:
            raise KeyError(f"SEC CIK is not configured for ticker: {ticker.symbol}") from exc

    def _request_json(self, url: str) -> dict[str, Any]:
        response = self._request(url)
        if len(response.body) > self.max_metadata_bytes:
            raise SecFilingProviderError("SEC metadata response exceeds configured limit")
        try:
            value = json.loads(response.body)
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("SEC submissions response is not valid JSON") from exc
        if not isinstance(value, dict):
            raise ProviderSchemaError("SEC submissions response must be an object")
        return value

    def _fetch_content(self, url: str) -> bytes:
        response = self._request(url)
        content = response.body
        if len(content) > self.max_content_bytes:
            raise SecFilingProviderError("SEC filing content exceeds configured limit")
        _infer_mime_type(content)
        self._content_cache[url] = content
        return content

    def _request(self, url: str) -> HttpResponse:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = (self._transport or _network_transport)(url, self._headers(), self.timeout)
                if response.status == 429:
                    raise SecFilingProviderError("SEC rate limit response (429)")
                if response.status >= 500:
                    raise SecFilingProviderError(f"SEC server response ({response.status})")
                if response.status >= 400:
                    raise SecFilingProviderError(f"SEC HTTP response ({response.status})")
                return response
            except (SecFilingProviderError, ProviderTimeoutError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    raise
            except (OSError, TimeoutError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    raise SecFilingProviderError("SEC request failed") from exc
            if self.backoff:
                import time as _time

                _time.sleep(self.backoff * (2**attempt))
        raise SecFilingProviderError("SEC request failed") from last_error

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept": "application/json, text/html, text/plain"}

    def _retrieved_at(self, available_at: datetime) -> datetime:
        retrieved = self._clock()
        if retrieved.tzinfo is None:
            retrieved = retrieved.replace(tzinfo=timezone.utc)
        retrieved = retrieved.astimezone(timezone.utc)
        if retrieved < available_at:
            raise SecFilingProviderError("retrieved_at precedes SEC public availability")
        return retrieved


# Descriptive compatibility alias for callers that name the source explicitly.
SecEdgarFilingsProvider = SecFilingsProvider


def _document(**values: object) -> FilingDocument:
    content = values.pop("content")
    if not isinstance(content, bytes):
        raise TypeError("SEC filing content must be bytes")
    retrieved_at = values.pop("retrieved_at")
    available_at = values["available_at"]
    filed_date = values.pop("filed_date")
    if not isinstance(retrieved_at, datetime) or not isinstance(available_at, datetime):
        raise TypeError("filing timestamps must be datetime values")
    if not isinstance(filed_date, date):
        raise TypeError("filing date must be a date")
    source_url = values["source_url"]
    if not isinstance(source_url, str):
        raise TypeError("filing source URL must be text")
    digest = hashlib.sha256(content).hexdigest()
    accession = str(values["accession"])
    cik = str(values["cik"])
    form = values["form"]
    if not isinstance(form, FilingForm):
        raise TypeError("filing form is invalid")
    filing_id = f"{cik}:{accession}:{values['primary_document']}:{digest}"
    provenance = DataProvenance(
        source=source_url,
        provider=SecFilingsProvider.name,
        retrieved_at=retrieved_at,
        effective_date=available_at.date(),
        available_at=available_at,
        filing_date=filed_date,
        period_end=values["period_end"] if isinstance(values["period_end"], date) else None,
        raw_identifier=f"{cik}/{accession}/{values['primary_document']}",
        units="raw filing bytes",
    )
    ticker = values["ticker"]
    if not isinstance(ticker, Ticker):
        raise TypeError("filing ticker is invalid")
    period_end = values["period_end"]
    if period_end is not None and not isinstance(period_end, date):
        raise TypeError("filing period end is invalid")
    return FilingDocument(
        id=filing_id,
        ticker=ticker,
        cik=cik,
        accession_number=accession,
        form=form,
        filed_at=_utc_midnight(filed_date),
        available_at=available_at,
        period_end=period_end,
        primary_document=str(values["primary_document"]),
        source_url=source_url,
        content_hash=digest,
        retrieved_at=retrieved_at,
        mime_type=_infer_mime_type(content),
        size_bytes=len(content),
        provenance=provenance,
    )


def _recent_filings(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    recent = metadata.get("filings", {}).get("recent")
    if not isinstance(recent, dict):
        raise ProviderSchemaError("SEC submissions metadata lacks filings.recent")
    if not recent or any(not isinstance(value, list) for value in recent.values()):
        raise ProviderSchemaError("SEC recent filing fields must be arrays")
    lengths = {len(value) for value in recent.values()}
    if not lengths or len(lengths) != 1:
        raise ProviderSchemaError("SEC recent filing fields have inconsistent lengths")
    rows: list[dict[str, Any]] = []
    for index in range(lengths.pop()):
        row = {key: value[index] for key, value in recent.items() if isinstance(value, list)}
        if not row:
            raise ProviderSchemaError("SEC recent filing row is empty")
        rows.append(row)
    return rows


def _filing_form(value: object) -> FilingForm | None:
    if not isinstance(value, str):
        return None
    try:
        return FilingForm(value)
    except ValueError:
        return None


def _required_text(entry: dict[str, Any], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProviderSchemaError(f"SEC filing field {key} is missing")
    return value.strip()


def _parse_date(value: object, field: str) -> date:
    parsed = _optional_date(value, field)
    if parsed is None:
        raise ProviderSchemaError(f"SEC filing field {field} is invalid")
    return parsed


def _optional_date(value: object, field: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderSchemaError(f"SEC filing field {field} is invalid")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ProviderSchemaError(f"SEC filing field {field} is invalid") from exc


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderSchemaError("SEC acceptanceDateTime is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderSchemaError("SEC acceptanceDateTime is invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _normalize_cik(value: str) -> str:
    if not isinstance(value, str) or not value.isdigit():
        raise ValueError("SEC CIK must contain digits only")
    return value.zfill(10)


def _archive_url(cik: str, accession: str, primary_document: str) -> str:
    if "/" in primary_document or "\\" in primary_document or ".." in primary_document:
        raise ProviderSchemaError("SEC primary document contains an unsafe path")
    if not accession or not cik:
        raise ProviderSchemaError("SEC accession and CIK are required")
    undashed = accession.replace("-", "")
    return f"{SecFilingsProvider._archive_root}/{int(cik)}/{undashed}/{primary_document}"


def _infer_mime_type(content: bytes) -> str:
    if not content or b"\x00" in content:
        raise SecFilingProviderError("SEC filing is empty or contains unsupported binary content")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SecFilingProviderError("SEC filing is not valid UTF-8 text") from exc
    lowered = text.lstrip().lower()
    if lowered.startswith("{") or lowered.startswith("["):
        raise SecFilingProviderError("SEC filing MIME type is not in the allowlist")
    if lowered.startswith("<!doctype html") or "<html" in lowered[:2048]:
        return "text/html"
    if "<" not in lowered and text.strip():
        return "text/plain"
    raise SecFilingProviderError("SEC filing MIME type is not in the allowlist")


def _network_transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
    from urllib.request import Request, urlopen

    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"data.sec.gov", "www.sec.gov"}:
        raise SecFilingProviderError("SEC adapter rejected non-SEC HTTPS URL")
    try:
        with urlopen(Request(url, headers=headers), timeout=timeout) as response:
            return HttpResponse(response.read(), response.status)
    except TimeoutError as exc:
        raise ProviderTimeoutError("SEC request timed out") from exc
