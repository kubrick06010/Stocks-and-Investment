# Deterministic qualitative filing intelligence (V1 research)

Status: design research only; no provider or production implementation is proposed here.

Checked: 2026-08-19.

## Recommendation in one paragraph

The smallest defensible V1 is an evidence archive, not an NLP or LLM system. Discover a filing from the SEC Submissions API, identify the accepted submission and its documents by CIK, accession number, form, filing date, acceptance timestamp, period of report, and filename, then preserve the official HTML or ASCII document byte-for-byte. Store a cryptographic hash of the raw bytes, a normalized section record with exact anchors into the raw document, and only deterministic or explicitly analyst-authored claims that point back to those anchors. Treat amendments as new immutable submissions and calculate section diffs between immutable snapshots. Do not infer management intent, truth of a claim, materiality beyond the filing’s stated structure, or future availability from a period end date.

## Authoritative SEC evidence model

### Discovery and filing identity

The SEC’s [EDGAR APIs documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) documents the per-filer Submissions API at `data.sec.gov/submissions/CIK##########.json`. It contains filer metadata, ticker/exchange metadata, recent filing history, and links to older history files when needed. The API is updated as filings are disseminated and the SEC also publishes bulk submissions archives. V1 should use this only as a discovery/index source; it is not itself the immutable filing document.

The stable identity of an accepted submission should include:

- `cik` (zero-padded issuer/filer CIK);
- `accession_number` in dashed canonical form and its undashed archive path form;
- `form` exactly as reported, including amendment suffixes such as `10-K/A` and `10-Q/A`;
- `filing_date` / filed-as-of date;
- `acceptance_datetime` when available;
- `period_of_report` / conformed period of report;
- the document filename and sequence from the filing index;
- the canonical SEC archive URL and retrieval timestamp.

The [SEC Filing Detail example](https://www.sec.gov/Archives/edgar/data/1388658/000138865826000055/0001388658-26-000055-index.htm) demonstrates the useful distinction between Form 8-K, filing date, accepted timestamp, period of report, accession number, primary document, complete submission text, and exhibits. The [SEC EDGAR search assistance page](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) documents archive paths, complete submission text files, index files, and the accession-number directory convention.

An accession number is a submission identity, not a version of a paragraph. A post-acceptance correction or amendment must therefore remain a new immutable submission record. A later filing may supersede an earlier interpretation for a new research run, but must not rewrite the earlier raw object.

### Dates and point-in-time availability

The SEC [Webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions) and [EDGAR PDS specification](https://www.sec.gov/info/edgar/pdsdissemspec111811.pdf) distinguish:

- `conformed_period_of_report`: the reporting period end, an economic/accounting date;
- `filed_as_of_date`: the official filing date assigned by EDGAR, including certain post-acceptance corrections;
- `acceptance_datetime`: when EDGAR accepted the submission;
- `date_as_of_change`: when the filing-date field was last changed, where present.

The SEC explicitly states that there is no timestamp identifying when filing content first became available on `sec.gov`; it also says filings are often available within roughly 1–3 minutes of the EDGAR system timestamp. Consequently, V1 must retain both the official EDGAR timestamps and our own `retrieved_at`, but must not claim millisecond-level public visibility. For conservative historical research, an observation is eligible only when its acceptance/filing availability boundary is at or before the research timestamp according to the project’s explicit policy. At date-only precision, use a conservative end-of-day/business-day policy and record the policy version.

Never use `period_of_report` as `effective_date`. A 2025-03-31 quarter can become public weeks later. Store `period_end`, `filing_date`, `acceptance_datetime`, and `retrieved_at` separately.

The [SEC filing-status guide](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/determine-status-my-filing) confirms that an electronically transmitted submission is not an official filing until accepted and assigned a filing date. This supports using accepted EDGAR submissions—not attempted, suspended, or merely downloaded artifacts—as the default public-information boundary.

### Form semantics and amendments

The [SEC Forms Index](https://www.sec.gov/submit-filings/forms-index) is the authoritative directory of form definitions and links to the current form PDFs. V1 should preserve the exact form code and use a small versioned semantic map rather than assuming every filing has the same section structure.

Initial semantics:

| Form family | V1 interpretation | Typical qualitative targets |
|---|---|---|
| `10-K` | Annual report under Exchange Act Sections 13/15(d) | Business, risk factors, MD&A, market risk, controls, exhibits |
| `10-Q` | Quarterly report under Exchange Act Sections 13/15(d) | Quarterly financial condition, MD&A, controls, legal/market-risk updates |
| `8-K` | Current report for specified events and other material events | Item-specific event disclosures; do not assume all 8-Ks are comparable |
| `10-K/A`, `10-Q/A`, `8-K/A` | Amendment to the corresponding form | New immutable submission; changed scope must be recorded |

The exact item and section labels must be parsed from the filed document and retained as observed evidence. The form code alone does not prove that a section is present or that the company discussed a topic.

For amendments, preserve:

- `amends_accession_number` when determinable from filing metadata or document text;
- amendment form and filing/acceptance dates;
- the complete amended raw document, not only changed paragraphs;
- a deterministic diff against the selected predecessor, with an explicit `predecessor_selection_method`;
- whether the amendment appears to restate, replace, add, or correct content.

Do not infer that every `/A` filing changes every financial statement or that absence of a phrase means absence of a risk. A filing can amend a limited item, exhibit, signature, certification, or other component.

### Official document versus XBRL and rendered views

The SEC’s [About EDGAR](https://www.sec.gov/edgar/searchedgar/aboutedgar.htm) states that plain-text and HTML documents are the official filings and cautions that XBRL documents should not replace review of the official filing. The SEC’s [Inline XBRL filing guidance](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/operating-company-inline-xbrl-filing-tagged-data) explains that Inline XBRL embeds machine-readable facts in a human-readable HTML document. The SEC also documents [XBRL validation and rendering](https://www.sec.gov/data-research/xbrl-validation-rendering), but a rendered view is a presentation/validation aid, not a substitute for preserving the submitted document.

V1 policy:

1. Hash and archive the primary HTML or ASCII filing bytes.
2. Store the complete submission text and filing index identity where acquired, with separate hashes.
3. Treat Inline XBRL facts and extracted XML as secondary structured evidence linked to the same accession/document; preserve fact context, units, decimals, dimensions, and source element anchors where available.
4. Never silently replace a textual disclosure with an XBRL fact or vice versa.
5. Record parser/viewer version because HTML rendering and extracted text can change across tooling versions.

## Minimal immutable V1 data model

The following is a storage recommendation, not an implementation contract.

### Raw submission and document

`FilingSubmission`:

- issuer/filer CIK and optional issuer identity snapshot;
- accession number;
- form and amendment flag;
- period of report;
- filed-as-of date;
- acceptance datetime, if present;
- SEC archive/index URLs;
- retrieval timestamp and declared retrieval policy;
- source response metadata sufficient to audit acquisition;
- `raw_submission_sha256` and status.

`FilingDocument`:

- submission identity plus sequence, filename, document type/description;
- primary-document flag;
- media type and byte length;
- immutable raw object location/content-addressed key;
- `raw_document_sha256`;
- normalized text hash and parser/version metadata;
- exact source URL and retrieved-at timestamp.

Raw bytes should be write-once in the logical model. If a URL later serves different bytes, preserve both hashes as separate retrieval observations and flag the identity conflict; do not overwrite the original.

### Normalized sections and anchors

`FilingSection` should contain:

- submission/document identity;
- form-family semantic version;
- observed section/item label, e.g. `Item 1A`;
- normalized section type, e.g. `RISK_FACTORS`, `MD&A`, `MARKET_RISK`;
- heading text exactly as observed;
- normalized text content, with a documented whitespace/HTML normalization algorithm;
- `source_anchor_start` and `source_anchor_end` in a canonical byte or character coordinate system;
- optional DOM locator such as element `id`/heading path;
- section hash and parser version;
- extraction status and caveats.

Use both a stable textual offset and a DOM/HTML locator when possible. DOM locators alone are brittle; offsets alone are hard to inspect after normalization. Anchors must always point into the immutable raw document version that produced the section.

The initial section map should cover the requested high-value targets when present:

- `Item 1` / Business;
- `Item 1A` / Risk Factors;
- `Item 7` / Management’s Discussion and Analysis;
- `Item 7A` / Quantitative and Qualitative Disclosures About Market Risk.

For 10-Q and 8-K, do not force annual 10-K item names. Store observed item labels and map only where the form’s official structure supports a defensible equivalence.

### Claims and diffs

`FilingClaim` should be one of two explicitly different kinds:

- `DETERMINISTIC`: generated by a documented rule over structured/normalized filing evidence, such as “Item 1A was present” or “the exact phrase occurred at anchor X”; or
- `ANALYST_AUTHORED`: authored by a human with author, timestamp, methodology/version, and supporting source anchors.

Each claim must include polarity/values only if its rule defines them, source section/document references, source offsets/anchors, and a claim/methodology version. A claim is not a fact merely because it is deterministic; it is an interpretation of the cited filing content.

`SectionDiff` should compare two immutable section versions and contain:

- predecessor and successor submission/document/section identities;
- diff algorithm and normalization version;
- added/removed/unchanged status;
- deterministic line/token/paragraph hunks with old/new anchors;
- changed hashes and materiality status, if a versioned materiality policy is applied;
- no causal or sentiment label unless explicitly supported by a rule or analyst claim.

## Deterministic V1 processing boundary

Safe initial operations:

1. Discover filing metadata from Submissions API and resolve an accession/document URL.
2. Verify the archive/index metadata against the downloaded complete submission and primary document.
3. Hash raw bytes and persist immutable identity.
4. Normalize HTML/ASCII for search and section extraction while retaining raw bytes.
5. Locate headings/items using exact/controlled patterns and retain all ambiguity/no-match statuses.
6. Extract Inline XBRL facts as linked evidence, not as unqualified truth.
7. Produce deterministic presence, text-diff, hash-diff, and numeric/XBRL-context claims.
8. Compare filings by explicit issuer, form family, period, accession and predecessor policy.
9. Expose evidence and limitations in reports.

Do not include sentiment scoring, “management confidence,” event probability, litigation severity, business quality, fraud probability, or investment recommendations in V1. Those require stronger semantic validation and often depend on context outside the filing.

## Point-in-time, restatements, and amendments

The system must distinguish four questions:

1. When did the economic period occur?
2. When was the submission accepted/filed?
3. When did our system retrieve it?
4. Which version was available to a historical research run?

For a run at timestamp `T`, only accepted submissions whose conservative public-availability boundary is `<= T` may enter the information set. A later `10-K/A`, `10-Q/A`, 8-K amendment, or corrected submission is unavailable to an earlier run even if the raw bytes are already cached locally.

Restatement handling V1:

- retain original and amended filings as separate immutable records;
- link a later amendment/restatement to the earlier filing when the relation is explicit or deterministically matched, otherwise leave linkage uncertain;
- mark facts/sections as `original`, `amended`, or `uncertain_predecessor` where the source supports it;
- never silently backfill an earlier ResearchRun with later corrected figures;
- let a new ResearchRun choose whether it uses contemporaneously available or latest-known historical data, and record that policy.

The SEC’s [About EDGAR guidance](https://www.sec.gov/edgar/searchedgar/aboutedgar.htm) also cautions that XBRL data can have quality/compliance issues and should be checked against the official filing. Therefore restatement detection based only on changed XBRL facts is insufficient; the official HTML/ASCII filing and amendment semantics remain authoritative evidence.

## Fair access and archive linking

The SEC’s [data/process limits guidance](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/observe-data-process-filing-limits) and [Webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions) require declared user-agent identification for scripted access and describe a current monitored request-rate ceiling of 10 requests per second. V1 must:

- send a descriptive `User-Agent` with an administrative contact;
- enforce conservative rate limiting, retries only for transient failures, and bounded timeouts;
- cache immutable responses by URL/content hash;
- prefer Submissions API/bulk archives for discovery at scale rather than serially crawling filing pages;
- preserve SEC archive URLs and accession links in stored provenance;
- never bypass SSL verification, access controls, or rate limits;
- surface HTTP/status/parser failures instead of silently dropping documents.

The API documentation notes that `data.sec.gov` does not support CORS and that bulk ZIP archives are republished nightly. This supports an offline-first ingestion workflow: acquire under fair-access rules, persist raw artifacts, and run all qualitative analysis locally and reproducibly.

## What cannot be safely inferred in V1

The filing alone does not safely establish:

- that a risk is probable, severe, immaterial, or resolved merely because it is mentioned or omitted;
- that management’s language is truthful, complete, optimistic, pessimistic, or intentionally misleading;
- that a changed section caused a price move or business outcome;
- that a phrase’s absence means the underlying risk disappeared;
- that two differently worded sections express equivalent business facts without a validated semantic rule;
- that an amendment supersedes every part of the original filing;
- that an XBRL fact is correct, comparable, complete, or properly tagged without checking context and the official document;
- that filing date equals public availability at an exact instant;
- that a reporting period’s data was known at period end;
- that a filing’s “materiality” in legal/accounting context can be reduced to a word count or diff size;
- that a disclosed risk applies to a particular security or portfolio exposure without linking the issuer/security identity and scope;
- that a section change is economically meaningful without a versioned rule and human review.

These are explicit `UNKNOWN`/`UNSUPPORTED` outcomes, not missing values converted to neutral or positive signals.

## V1 acceptance checklist

- [ ] Submission metadata and primary document are identified by CIK + accession + filename/sequence.
- [ ] Form, amendment status, period end, filing date, acceptance datetime, and retrieval time remain separate.
- [ ] Raw official HTML/ASCII bytes are immutable and hashed.
- [ ] XBRL is linked secondary evidence and checked against the official filing.
- [ ] Sections preserve normalized content plus exact raw anchors and parser version.
- [ ] Claims are deterministic or analyst-authored, never opaque generated prose.
- [ ] Section diffs are deterministic, identity-safe, and versioned.
- [ ] PIT access uses accepted filing availability, not period end or current latest data.
- [ ] Amendments/restatements are additive historical versions.
- [ ] SEC fair-access/user-agent/rate-limit requirements are explicit.
- [ ] Reports expose source URLs, accession identity, hashes, and limitations.

## Primary official sources checked

- [EDGAR Application Programming Interfaces](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) — Submissions API, XBRL API, bulk archives, update behavior.
- [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) — archive/index paths and complete submission files.
- [EDGAR Filing Detail example](https://www.sec.gov/Archives/edgar/data/1388658/000138865826000055/0001388658-26-000055-index.htm) — accession, form, filing date, accepted time, period, document list.
- [Webmaster Frequently Asked Questions](https://www.sec.gov/about/webmaster-frequently-asked-questions) — filing/acceptance timestamps, public availability caveat, user-agent and request limits.
- [EDGAR Public Dissemination Technical Specification](https://www.sec.gov/info/edgar/pdsdissemspec111811.pdf) — submission header fields and filing-date definitions.
- [Determine the Status of My Filing](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/determine-status-my-filing) — acceptance and filing-date rules.
- [Forms Index](https://www.sec.gov/submit-filings/forms-index) — official form definitions and form PDFs.
- [About EDGAR System](https://www.sec.gov/edgar/searchedgar/aboutedgar.htm) — official HTML/ASCII versus unofficial XBRL caution.
- [Operating Company Inline XBRL Filing of Tagged Data](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/operating-company-inline-xbrl-filing-tagged-data) — Inline XBRL’s human/machine-readable model.
- [XBRL Validation and Rendering](https://www.sec.gov/data-research/xbrl-validation-rendering) — SEC rendering/validation context.
- [Observe Data and Process Filing Limits](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/observe-data-process-filing-limits) — fair-access and document-processing guidance.
