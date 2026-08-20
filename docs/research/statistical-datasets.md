# Wave E.0 Sidecar — Historical Statistical Dataset Design

Status: DESIGN ONLY

Scope: reproducible datasets for advanced statistical validation

Owner: Wave E.0 statistical validation workstream
Implementation status: not started

This document defines the dataset boundary for Wave E. It does not authorize a
provider integration, a new metric, a new factor, or a change to the existing
domain and storage contracts.

The dataset is a controlled information set for evaluating already-versioned
research methodology. It must preserve what was knowable at the research date,
what universe was eligible, and what subsequently happened. A dataset is not a
flat price/fundamentals export and must not be regenerated from today's data.

## Design principles

- Point-in-time availability is authoritative. `period_end`, `filing_date`,
  `effective_date`, and `retrieved_at` remain separate.
- Research observations and future outcomes are separate partitions with a
  one-way temporal boundary.
- Security identity, date identity, strategy/factor version, universe identity,
  benchmark identity, currency, and corporate-action policy are explicit.
- Historical universe membership is represented by dated snapshots. Current
  membership is never used as a historical substitute without a recorded
  limitation.
- Missingness is information. Missing, not meaningful, insufficient history,
  stale, excluded, and zero are distinct states.
- Every derived observation points to immutable source records and a
  calculation version.
- Dataset manifests are content-addressed and immutable. A changed input
  produces a new dataset version.
- Synthetic data validates mechanics; external data is required for economic
  claims. Neither is silently mixed with the other.

## Dataset identity and manifest

Each dataset release has one canonical manifest, stored with the dataset and
identified independently of filenames:

```yaml
dataset_id: us-equity-research-e1
dataset_version: 1.0.0
manifest_schema_version: 1
release_status: draft | candidate | frozen | retired
created_at: 2026-08-19T00:00:00Z
source_revision: <git-commit-or-archive-digest>
content_digest: <sha256-of-canonical-manifest-and-partitions>
base_currency: USD
calendar: XNYS
security_master_version: security-master-v1
universe_snapshots:
  - id: us-large-cap-2010-01-01-v1
    name: us-large-cap
    as_of: 2010-01-01
    membership_digest: <sha256>
benchmarks:
  - id: sp500-total-return-usd-v1
    return_convention: total_return
    currency: USD
partitions:
  research: {path: research/, digest: <sha256>}
  outcomes: {path: outcomes/, digest: <sha256>}
  prices: {path: prices/, digest: <sha256>}
  corporate_actions: {path: corporate-actions/, digest: <sha256>}
  universe_snapshots: {path: universes/, digest: <sha256>}
  provenance: {path: provenance/, digest: <sha256>}
```

The manifest must also record:

- source systems and dataset extracts, including retrieval timestamps;
- licensing and permitted redistribution;
- transformations, filters, survivorship treatment, and exclusions;
- price adjustment and dividend policy;
- timezone and session-close convention;
- financial statement units, fiscal-period rules, restatement policy, and
  share-count convention;
- benchmark methodology and risk-free-rate convention if applicable;
- known gaps, coverage metrics, and validation status.

The semantic identity of a dataset is the tuple
`(dataset_id, dataset_version, manifest_digest)`. A manifest edit, source
replacement, correction, or methodology change creates a new version rather
than mutating a frozen release.

## Partition model

The dataset has two mandatory logical zones and supporting reference zones.

### Research information zone

Contains only information eligible for a strategy at an as-of timestamp:

- security master records and identifier mappings;
- dated universe memberships;
- raw and normalized prices available by the relevant date;
- corporate actions and adjustment metadata;
- filings and financial observations with public availability dates;
- validated metric observations, factor observations, factor scores, criteria,
  and persisted ResearchRun lineage;
- provenance references and calculation versions.

The research zone is queried through the existing point-in-time semantics. A
row physically present in storage is not automatically visible to an earlier
research date.

### Outcome zone

Contains observations that become available only after the research decision:

- forward security returns by explicit horizon and window;
- benchmark returns for the same window and convention;
- excess return;
- optional drawdown, favorable excursion, and adverse excursion;
- outcome status explaining incomplete or unavailable windows.

Outcome rows must reference the originating ResearchRun/ResearchResult and
must never be exposed to factor or strategy evaluation for that run. Outcome
construction is a post-hoc operation over a frozen research artifact.

### Supporting reference zones

- `security_master`: stable instrument identity, ticker history, exchange,
  currency, listing and delisting dates;
- `prices`: raw bars plus explicit adjustment policy and source provenance;
- `corporate_actions`: typed split, dividend, spin-off, merger, delisting and
  other actions;
- `universe_snapshots`: immutable membership sets;
- `provenance`: source, retrieval, availability, units, currency, raw IDs and
  transformation lineage.

No partition may contain an implicit “latest” row used as a historical fallback.

## Observation keys and availability

Every research observation must be uniquely addressable by a key equivalent to:

`(instrument_id, observation_name, period_end, effective_date, filing_date,
as_of_eligible_date, currency, units, source_id, derivation_version)`.

The eligibility rule is:

```text
visible(observation, simulation_timestamp) iff
  observation.effective_date <= simulation_timestamp
  and observation.data_status is usable
```

For filings, `effective_date` is the public availability timestamp, normally
the filing/publication date plus the documented timezone/session convention.
`period_end` describes the economic period and does not imply availability.
`retrieved_at` records when the dataset acquired the record and is not a
substitute for public availability.

For prices, the dataset must define whether availability means session close,
official close publication, or another documented timestamp. Weekend and
holiday dates must not be silently forward-filled.

Restatements are retained as separate observations with source and filing
identity. A historical run may use a later restatement only if its availability
date makes it eligible; otherwise the originally available observation remains
the valid historical input.

## Universe snapshots and delisted securities

Every research date references an immutable `UniverseSnapshot`:

```yaml
id: us-large-cap-2014-12-31-v1
name: us-large-cap
version: 1
as_of: 2014-12-31
members_digest: <sha256>
source: historical-membership-provider-or-archive
survivorship_status: complete | partial | current-membership-proxy
```

Membership is not inferred from price availability. A security may be:

- eligible and listed;
- eligible but subsequently delisted;
- delisted before a later rebalance;
- suspended or missing for a documented interval;
- absent from the universe while still listed.

Delisted securities remain in the security master and historical universe
snapshots. Their final observable prices, delisting returns, liquidation dates,
and corporate actions are retained where available. If a delisting return is
unavailable, the outcome is marked incomplete rather than replaced by zero,
the last price, or a surviving-company proxy.

If historical membership is incomplete, the manifest must state the resulting
survivorship limitation and every analysis report must carry that limitation.
Backtests must not silently use today's constituents for earlier dates.

## Missingness, coverage, and exclusions

Each partition includes explicit status fields. At minimum:

`VALID`, `MISSING`, `NOT_MEANINGFUL`, `INSUFFICIENT_HISTORY`, `STALE`,
`UNAVAILABLE_AT_AS_OF`, `EXCLUDED`, `INCOMPLETE_WINDOW`, `NOT_APPLICABLE`.

Coverage reporting must include, by research date, universe and factor:

- eligible security-date observations;
- observations with required inputs;
- usable observations;
- excluded observations by reason;
- incomplete forward windows;
- delisted observations;
- currency or benchmark exclusions;
- coverage percentage and denominator definition.

The dataset builder must not drop rows solely because a metric is unavailable.
It should retain an exclusion/status record so that coverage differences are
auditable. Statistical summaries must declare whether their denominator is all
eligible observations or only usable observations.

Small cohorts must return an explicit insufficient-sample result. They must not
produce quintile, IC, confidence, or hit-rate statistics that imply precision
the sample cannot support.

## Currency and return conventions

Every monetary observation carries currency and units. The manifest declares a
base currency, but conversion is an explicit transformation with:

- source currency;
- target currency;
- FX source and timestamp;
- conversion method/version;
- availability date;
- whether the result is nominal or real.

No cross-currency ratio, return, benchmark comparison, or portfolio result is
allowed without an explicit conversion policy. Missing FX data is not zero FX.

Returns must declare whether they are price return, total return, or another
defined convention. A total-return benchmark must not be compared to a
price-return security series without recording the mismatch. Risk-free rate,
annualization basis, and trading-day calendar are part of the cohort identity
for risk-adjusted statistics.

## Benchmarks

Benchmarks are versioned instruments with their own provenance and return
convention. Each outcome identifies:

- benchmark ID and version;
- benchmark currency;
- benchmark price/total-return policy;
- window start and end;
- source and availability metadata.

An efficacy cohort cannot silently combine different benchmarks. Strategy
comparisons with different benchmarks are incompatible for direct excess-return
comparison, even if raw security returns are available.

## Corporate actions and price adjustments

Corporate actions are typed records, not one ambiguous numeric value:

- `SplitAction`: numerator, denominator, factor, effective date;
- `DividendAction`: amount per share, currency, ex-date, payment date;
- `SpinoffAction`: distributed instrument, distribution ratio, effective date;
- delisting/merger actions with explicit cash or security consideration where
  available.

The dataset manifest chooses the supported research price policy explicitly:

- `RAW_PLUS_ACTIONS`: raw prices and typed actions; portfolio/backtest applies
  each action once;
- `SPLIT_ADJUSTED`: split effects already reflected; split actions must not be
  applied a second time;
- `TOTAL_RETURN_ADJUSTED`: dividends and splits reflected in the series;
  explicit dividend credit is prohibited for that series;
- `PROVIDER_ADJUSTED`: permitted only when the provider's exact semantics are
  documented and stable.

Each price row carries the policy ID. Combining policies within one return
calculation is invalid unless an explicit normalization step produces a new,
versioned series. A corporate action must affect economic wealth exactly once.

## Immutable partitions for development, validation, and OOS

Partition assignment is made at the time a dataset release is frozen and is
stored in the manifest. It is not selected dynamically by the evaluator.

Recommended temporal partitions:

```text
development:  earliest research dates through D_end
validation:   (D_end, V_end]
out_of_sample:(V_end, OOS_end]
```

The boundary is based on research information dates, not merely outcome dates.
All observations belonging to a research date stay in that date's partition;
future outcomes may cross a boundary only under a documented outcome-evaluation
protocol. A security must not be split randomly across partitions when that
would leak its time series or issuer-specific information.

For repeated cross-sectional studies, a second grouping key may be needed for
issuer or cohort blocking. The manifest records the assignment algorithm and
seed if any deterministic sampling is used. Once frozen, partitions are
append-only through a new dataset version; no row is moved retroactively in
place.

Wave E must distinguish:

- methodology development, where thresholds may be defined;
- validation, used once for design decisions;
- OOS evaluation, which remains untouched until the methodology is frozen.

No factor, threshold, universe rule, or cost assumption may be tuned using OOS
outcomes and then reported as OOS evidence.

## Synthetic and external validation datasets

### Synthetic dataset

The existing AAA–EEE historical fixture remains the deterministic contract and
information-barrier test. A larger synthetic generator may extend it for
mechanics such as delisting, splits, dividends, missing filings, currencies,
and deliberately injected future records. Synthetic data must be labelled in
the manifest and must never support claims about real market efficacy.

Synthetic validation is appropriate for:

- point-in-time visibility;
- universe entry/exit and delisting handling;
- corporate-action wealth conservation;
- missingness and coverage accounting;
- partition immutability;
- deterministic reruns and adversarial leakage tests.

### External historical dataset

External data is required for economic validation. It must be assembled from
documented sources with a reproducible extraction date, raw archive or digest,
license record, normalization log, and source-specific caveats. The first
external release should be deliberately small and inspectable before scaling.

External validation must report:

- actual historical universe coverage;
- survivorship and delisting coverage;
- filing/publication-date coverage;
- corporate-action completeness;
- benchmark alignment;
- missing financial periods and restatements;
- symbol changes and security-master quality.

The first external release was executed on 2026-08-20 using the hash-pinned
Finance_Broski Kaggle v3 CC BY sample. It validated the pipeline and produced an
explicit economic `NO-GO`: 17 raw fundamental symbols cannot represent the
3,838-name inventory, and terminal/benchmark semantics are not independently
authoritative. See `docs/validation/india-pit-economic-validation.md`. Scaling
now requires the requested full panel or a separately approved licensed source.

Synthetic and external rows must have different dataset IDs or explicit source
domains. They must not be pooled without a documented cohort definition.

## Reproducibility and licensing caveats

The manifest must include the legal and operational conditions needed to rebuild
the dataset:

- source license, attribution, redistribution and retention restrictions;
- API terms, rate limits and whether raw responses may be archived;
- exact extraction queries or archive identifiers;
- software/tool versions and transformation code revision;
- timezone, calendar and locale assumptions;
- checksums for raw inputs and normalized partitions;
- known provider revisions and non-deterministic endpoints.

If a source cannot legally be redistributed, the repository should distribute a
manifest, schema, transformation recipe, and verification hashes rather than
the restricted raw data. A user may need to obtain the source independently.
The dataset is not reproducible merely because the code is public if the raw
inputs, license, or availability semantics cannot be reconstructed.

Provider credentials must never be embedded in manifests or fixtures. Network
acquisition remains outside this sidecar; a future provider workstream must
implement it against the frozen dataset contract.

## Required release checks

Before a statistical dataset is marked frozen, validate:

- manifest digest and partition digests reproduce;
- every research row has an availability date and provenance reference;
- every outcome has a source ResearchRun and explicit horizon;
- no outcome is visible to its originating research information set;
- universe snapshots are dated, versioned, and membership-addressable;
- delisted and missing observations are counted, not silently removed;
- currency, benchmark, and adjustment policies are homogeneous within each
  cohort;
- development, validation, and OOS partitions are immutable;
- a second build from the same inputs produces identical canonical outputs;
- synthetic and external validation are clearly separated;
- license and redistribution limitations are present in the manifest;
- a report can explain exclusions, coverage, survivorship, and known gaps.

This sidecar is complete when the future Wave E architecture can consume these
manifests without asking providers for “latest” data or reconstructing a past
information set from present-day records.
