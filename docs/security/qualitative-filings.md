# Security review: evidence-first qualitative filings

Status: design review for Wave E2 (no implementation approved)

Scope: a local, deterministic SQLite/CLI V1 that stores and displays filing
text or HTML as evidence. V1 has no LLM, no browser execution, no live
monitoring, and no automatic publication. The filing is untrusted input; it is
not an instruction to the application.

## Security objectives

- Preserve source integrity and provenance without treating a source as true
  merely because it was downloaded.
- Make storage and rendering safe for hostile text, HTML, metadata, archives,
  links, and filenames.
- Keep historical availability and retention decisions auditable.
- Ensure a malformed or malicious filing cannot execute code, contact an
  arbitrary host, disclose secrets, or exhaust local resources.
- Keep user-authored notes private and separate from issuer-provided evidence.

The V1 trust boundary is:

```text
provider/network -> acquisition -> validation/quarantine -> SQLite -> CLI renderer
                         untrusted                    structured evidence
user notes ------------------------------------------------^ (different provenance)
```

No V1 component should interpret filing text as commands, SQL, shell input,
Markdown directives, template source, or model instructions.

## Threat register and deterministic mitigations

| Threat | Impact | V1 mitigation | Required test |
|---|---|---|---|
| HTML `<script>`, event attributes, `javascript:` URLs, SVG/XML payloads, CSS or iframe content | Code execution or misleading output | Parse as inert text with an allowlist of content types/tags, or extract text server-side and discard markup. Never execute a browser, JavaScript, CSS, SVG, iframe, object, embed, form, or template. Escape output for the selected terminal/JSON/Markdown context. | Store a fixture containing scripts, event handlers, SVG, and dangerous links; assert no payload is emitted as executable markup and CLI output contains escaped text only. |
| Terminal escape sequences and control characters in issuer text or ticker metadata | Terminal spoofing, hidden output, clipboard/control abuse | Strip or visibly encode C0 controls, ESC, DEL, and terminal control sequences before human-readable output. JSON must use normal escaping. Keep raw bytes only in a quarantined blob, never in a terminal renderer. | Filing with ANSI cursor movement, OSC hyperlinks, newlines, and null bytes; assert rendered output has no ESC byte and record boundaries remain intact. |
| Decompression bomb, oversized response, archive nesting, huge HTML table, or pathological entity expansion | Memory, disk, CPU, or SQLite exhaustion | Enforce limits before decompression and after decompression: response bytes, decompressed bytes, compression ratio, archive entry count, per-entry bytes, total stored bytes, text length, nesting depth, and parse time. Reject archives and formats not explicitly supported. Disable external entities and network fetches. Stream/hash input where possible. | Tiny highly-compressed bomb, nested archive, many entries, oversized declared length, billion-laughs-style XML, deeply nested HTML, and timeout fixtures; assert bounded rejection and no partial trusted record. |
| Path traversal in filenames, archive members, or attachment identifiers | Write outside cache/storage directory or overwrite files | Treat provider identifiers as data, not paths. Allow only generated IDs and a fixed storage root; reject absolute paths, drive prefixes, `..`, separators, NUL, and symlink targets. Use SQLite/blob storage or safe generated filenames. Resolve and verify containment before any filesystem write. | `../../db`, absolute, Windows drive, encoded traversal, NUL, symlink, and hard-link fixtures; assert no outside file is created or modified. |
| Unsafe parser behavior, pickle/YAML/object deserialization, malformed encodings, entity expansion | Code execution, crashes, corrupted evidence | Permit only explicitly selected parsers for bytes/HTML/text/JSON. Never deserialize pickle or arbitrary Python objects. Use safe YAML-free policy for V1. Decode with a strict policy and preserve undecodable bytes as a flagged artifact; reject malformed structure, excessive nesting, and unknown schema versions. | Malformed UTF-8, invalid JSON, hostile YAML/pickle markers, recursive structures, invalid HTML, and unknown media types; assert safe error/status and no object construction. |
| External links, images, CSS, redirects, or embedded resources in a filing | SSRF, tracking, phishing, data exfiltration, non-reproducible rendering | Do not fetch links discovered inside filings. In CLI display links as inert, escaped text or omit them. If acquisition needs a provider URL, use an explicit provider allowlist and operation-specific URL construction; disable redirects to unapproved hosts, private/link-local IPs, localhost, non-HTTP schemes, and user-controlled ports. | Filing with links to localhost, cloud metadata, private IPv4/IPv6, `file:`, `ftp:`, redirects, and DNS-rebinding-shaped names; assert no network call occurs during parse/render and disallowed acquisition URLs fail. |
| SSRF through provider configuration or a malicious source URL | Access to local services or cloud credentials | V1 accepts no arbitrary URL from filing content. Configuration uses named providers, not a URL supplied by the document. Validate scheme/host/IP after resolution, use connect/read timeouts, bounded redirects, and an explicit user-agent. Network acquisition must be separated from parsing and disabled in offline tests. | Local test server and redirect chain; assert arbitrary document URLs are not requested and only an approved provider endpoint can be contacted. |
| Secrets, cookies, authorization headers, or identifying user-agent sent to an untrusted endpoint | Credential or privacy disclosure | Never place API keys in filing text, logs, SQLite evidence, URLs, or user notes. Store secrets only in environment/OS secret facilities. Redact headers and query strings in errors. Use a non-sensitive documented user-agent and send credentials only to the configured provider over TLS. | Endpoint fixture records headers and query; assert no secret/cookie appears, and logs/errors redact sensitive values. |
| Malicious filing text used as prompt injection in a future LLM | False analysis, tool use, data exfiltration, instruction override | V1 has no LLM. Preserve issuer text as quoted evidence with immutable provenance and an explicit `untrusted_content` label. Future model interfaces must pass evidence as data, delimit it, disable tool execution by default, allowlist tools, and require deterministic structured output validation; filing text can never define system/developer policy. | Include text saying “ignore prior instructions”, fake tool commands, and fabricated conclusions; assert V1 treats it as ordinary evidence. Add a future adapter contract test that it cannot invoke tools or alter provenance. |
| Copyright, licensing, retention, or redistribution violation | Legal exposure and irreversible over-retention | Record source, license/terms where known, retrieval time, permitted-use classification, and retention policy. Prefer storing hashes, normalized excerpts, and provider identifiers when full-text retention is not authorized. Do not silently redistribute raw filings. Provide explicit purge/redaction policy without changing immutable analytical lineage; consult the applicable source terms before deployment. | Retention-policy fixture verifies prohibited raw payloads are not persisted; metadata/hash remains inspectable; purge behavior is logged and does not rewrite a research decision. |
| User-authored notes mixed with issuer evidence | Privacy leak, provenance confusion, prompt injection path | Store notes in a distinct table/entity with author, created/updated timestamps, visibility, and provenance type. Escape notes in all renderers, never execute them, and do not include them in deterministic issuer evidence or factor calculations by default. | Note containing HTML, ANSI, SQL, and model-like instructions; assert it is escaped, separately labeled, and absent from evidence hashes/metric inputs. |
| Hash collision, wrong bytes hashed, post-validation mutation, or provider substitution | False provenance and inability to reproduce a filing | Hash the exact received bytes before normalization; record algorithm, byte length, media type, provider, URL/identifier, retrieval time, filing/publication dates, and parser/normalizer version. Verify hash on read and before derivation. Keep raw artifact immutable or content-addressed; derived text references its parent hash. Hash is integrity evidence, not authenticity proof. | Change one byte after ingestion, swap provider payloads, alter normalized text, or reuse an identifier; assert integrity/status failure and no derived metric is silently accepted. |
| Malicious issuer content that abuses Unicode, bidi controls, confusables, giant numbers, or duplicate fields | Misleading human review or inconsistent calculations | Normalize only under a documented version; preserve raw hash. Make bidi/control characters visible or remove them from display. Bound numeric length/precision, reject non-finite numbers, reject duplicate security/filing identifiers, and apply canonical field precedence. Never derive financial facts from untrusted prose in V1. | Bidi override, homoglyph ticker, huge exponent, NaN/Infinity, duplicate fields, and conflicting dates; assert deterministic rejection/visible rendering and no silent overwrite. |
| Denial of service via repeated downloads, retries, cache poisoning, or database growth | Availability loss and corrupted local history | Offline-first cache with bounded total/per-source size, deduplication by content hash, finite retries with backoff, per-operation timeouts, rate limits, cancellation, and atomic writes. Do not retry parse/validation failures. Enforce SQLite limits and transaction boundaries. | Repeated identical payloads, failing endpoint, retry storm, interrupted write, and full quota fixtures; assert bounded attempts, no corrupt row, and deterministic failure status. |
| Source spoofing or malicious filing with plausible issuer metadata | Wrong company/time period enters research | Cross-check ticker/CIK/accession/issuer identity and filing dates against the selected provider contract. Do not infer identity from filename or prose. Mark conflicts as `QUARANTINED` and require explicit review. Keep `effective_date`, `filing_date`, `retrieved_at`, and period end separate for PIT. | Same accession with different issuer, ticker reassignment, future publication date, restatement, and conflicting period fixtures; assert quarantine and no historical availability before publication. |

## Safe V1 processing policy

1. **Acquire only through a named provider.** The provider adapter owns URL
   construction, TLS, user-agent, timeout, rate limit, and response-size
   checks. A filing cannot select the next endpoint.
2. **Quarantine first.** Verify media type and byte limits, compute the raw
   hash, validate identity/date metadata, and store an explicit rejected or
   quarantined status before any normalization.
3. **Parse inertly.** V1 should support a small allowlist (for example,
   `text/plain` and a constrained HTML-to-text extractor). External resources,
   scripts, active markup, and unsupported encodings are discarded or rejected.
4. **Persist references, not trust.** Every normalized excerpt points to the
   raw hash and provenance record. A hash does not prove that a source is
   authoritative; provider identity and metadata validation remain necessary.
5. **Render by context.** Terminal, JSON, and Markdown have separate escaping
   functions. No generic “render HTML” path belongs in the V1 CLI.
6. **Keep PIT explicit.** A filing is available to research only at its
   public/effective availability timestamp, never merely because it exists in
   SQLite. Future filings remain physically stored but inaccessible to an
   earlier research view.
7. **Fail closed for ambiguity.** Missing identity, conflicting dates,
   unsupported media, quota exhaustion, integrity mismatch, and parser limits
   produce an explicit status and no derived evidence. They are not converted
   to empty text or zero.

## Test plan for a local SQLite/CLI V1

The following tests should be deterministic and offline by default; network
tests, if retained, must be separately marked and never required for the
normal suite.

- **Corpus safety:** hostile HTML/text fixture, controls, Unicode bidi,
  dangerous links, malformed encodings, duplicate fields, and fake issuer
  instructions render safely and preserve raw hash/provenance.
- **Parser sandbox:** unsupported media, XML entity expansion, nesting/length
  limits, non-finite numbers, and parser time/byte quotas fail closed.
- **Archive/filesystem safety:** traversal, absolute names, symlinks, archive
  bombs, and interrupted writes cannot escape the generated storage root or
  corrupt SQLite.
- **Network boundary:** parser/renderers make zero network calls. Provider URL
  tests reject private IPs, non-HTTP schemes, unapproved hosts, unsafe
  redirects, and oversized responses; error output contains no secret.
- **Integrity:** exact-byte hash round-trip succeeds; one-byte mutation,
  metadata mismatch, and provider substitution become an integrity failure.
- **PIT:** a filing physically present but published after `as_of` is not
  returned; the same filing is returned after its availability date. Restated
  or conflicting filings remain separately versioned/quarantined.
- **Privacy and retention:** notes are isolated from issuer evidence and
  calculations; renderer escaping works for text/JSON/Markdown; retention
  policy decisions are explicit and auditable.
- **Resource limits:** repeated downloads, retries, huge payloads, full quota,
  and malformed input terminate within bounded attempts/resources and leave no
  partial trusted record.
- **Future LLM boundary:** with no LLM installed, a fixture containing prompt
  injection remains inert. A later adapter must have a test proving quoted
  evidence cannot change system policy, invoke tools, or alter source lineage.

## Residual risks and explicit non-goals

- Hashes provide tamper detection after acquisition, not cryptographic proof
  that a provider or filing is genuine. TLS, provider authentication and
  issuer/accession cross-checks remain operational dependencies.
- A text extractor can still lose layout meaning, tables, footnotes, or
  amendments. V1 must expose extraction status and parser version rather than
  implying semantic completeness.
- Copyright and retention obligations are source- and jurisdiction-specific;
  this document is not legal advice. Deployment requires a provider-by-provider
  review of permitted storage and redistribution.
- Local SQLite confidentiality depends on filesystem permissions, backups,
  logs, and the host account. Sensitive user notes need an explicit local
  access/backup policy; V1 does not claim encryption at rest unless separately
  implemented and tested.
- Denial-of-service limits reduce but do not eliminate CPU/disk pressure from
  adversarial inputs. The CLI should expose rejection reasons and operators
  should be able to disable acquisition.
- V1 deliberately does not summarize filings with an LLM, execute document
  content, fetch embedded links, or derive investment conclusions from prose.

## Review conclusion

The qualitative filings layer is safe to design only as an evidence ingestion
and inspection boundary with quarantine, bounded parsing, explicit provenance,
context-specific escaping, and point-in-time access controls. It is not ready
to accept arbitrary URLs, active HTML, unbounded archives, or model-generated
interpretations. The mitigations and tests above are release requirements for
any future implementation; unresolved residual risks should remain visible in
the Wave E security gate.

## Required implementation checklist

- [ ] named-provider and URL/SSRF policy implemented
- [ ] byte, archive, parse-time, nesting, and storage quotas enforced
- [ ] safe inert parser and context-specific CLI escaping implemented
- [ ] raw-byte hash and parent-reference verification implemented
- [ ] identity, availability/PIT, media-type, and quarantine statuses persisted
- [ ] user notes isolated and privacy/retention policy documented per source
- [ ] offline adversarial corpus and SQLite round-trip tests pass
- [ ] no LLM or active-content execution path exists in V1
- [ ] security review repeated after implementation diff
