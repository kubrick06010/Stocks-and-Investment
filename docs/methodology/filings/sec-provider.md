# SEC filing provider V1

This adapter is an evidence-acquisition boundary. It discovers accepted
submissions from the SEC Submissions endpoint, retrieves the declared primary
document, hashes the exact received bytes, and returns the frozen
`FilingDocument` contract. It does not parse sections, derive claims, or
interpret issuer language.

## Point-in-time semantics

`period_end` is the economic reporting date. `filed_at` is the filing date.
`available_at` uses `acceptanceDateTime` when supplied and otherwise the UTC
start of the filing date. `retrieved_at` is the injected acquisition clock.
`filings(ticker, as_of)` includes a filing only when its public availability
date is on or before `as_of`; it never uses period end as availability and never
falls back to the latest filing.

An amendment is a separate immutable `FilingDocument` because its accession,
form, dates, bytes and hash are distinct. Only the frozen forms `10-K`,
`10-K/A`, `10-Q`, `10-Q/A`, `8-K`, and `8-K/A` are accepted.

## Transport and safety boundary

The adapter requires a descriptive user-agent containing a contact address.
Applications inject the existing `Transport` for deterministic tests. The
network fallback permits only HTTPS `data.sec.gov` and `www.sec.gov` URLs,
uses bounded timeout/retries, and does not disable TLS verification.

Metadata and filing byte limits are enforced before normalization. Primary
documents must be non-empty UTF-8 HTML or plain text; binary content, NUL
bytes, JSON masquerading as a filing, malformed metadata, unsafe document path
components, and HTTP failures are rejected explicitly. MIME is inferred from
the validated bytes because the frozen HTTP response contract carries no MIME
header; the resulting allowlist is `text/html`, `application/xhtml+xml` in the
contract design, and `text/plain` (the current implementation emits the first
or last value based on content).

The SHA-256 digest covers the exact bytes received. `content(filing)` verifies
both digest and byte length, so a changed response cannot silently replace
historical evidence. Embedded links are never fetched. No LLM or current-data
fallback exists in this provider.

## Reproducibility and limitations

The injected clock and transport make offline fixtures deterministic. The
adapter currently consumes the `recent` Submissions payload; older SEC history
files and bulk archives require an explicit future extension. The frozen
`HttpResponse` contract does not expose response MIME headers, so content-type
validation is conservative byte inspection rather than server-header
verification. Public visibility is represented at acceptance timestamp/date
precision, not an exact guarantee of when an archive URL became visible.
