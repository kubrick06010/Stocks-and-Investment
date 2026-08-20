# Independent review — India PIT / survivorship artifact

## Executive verdict

**Status: NO-GO for economic validation or profitability claims.**

The local artifact is useful as a **provenance and schema-inspection sample** and
as a candidate input for further acquisition work. It is not currently evidence
for an economically valid factor or backtest result. The archive contains three
very different populations that must not be conflated:

| Population | Rows | Unique symbols | What it appears to represent | Review consequence |
|---|---:|---:|---|---|
| `survivorship_universe.csv` | 3,838 | 3,838 | symbol-level universe/security summary | broad name inventory, not dated membership snapshots |
| `prices_sample.csv` | 359,852 | 99 | a price sample | 2.58% of universe names; no benchmark or action ledger |
| `fundamentals_sample.csv` | 417 | 17 | a small accounting sample | 0.44% of universe names; not a representative fundamental panel |

The 17 fundamental symbols are all among the 99 price symbols. This nested
sampling means the artifact cannot support a claim about the 3,838-name
universe, and it cannot support a claim that a factor or strategy was profitable
in India. No profitability claim is made in this review.

## Evidence inspected

Inspected locally:

- `data/external/wave_e/raw/india-pit-survivorship.zip`;
- `docs/research/e1-authoritative-data-sources.md`;
- `docs/methodology/statistical-validation/datasets.md`;
- the frozen statistical-validation contracts and dataset selection code.

The archive has no README, LICENSE, source URL, Kaggle dataset reference,
creator/attribution record, version manifest, schema manifest, benchmark file,
or archive comment. A Kaggle page or description discussed outside the archive
is not sufficient to identify these bytes: the exact dataset reference,
dataset-version metadata, downloaded-file manifest, and licence text must be
recorded alongside the artifact before redistribution or economic use.

The repository's source decision correctly treats public Kaggle/GitHub archives
as exploratory until provenance, licence, point-in-time semantics and delisting
coverage are independently verified. See
[`e1-authoritative-data-sources.md`](../research/e1-authoritative-data-sources.md).

## Independently computed artifact identity

Computed with Python's standard-library `zipfile`, `csv` and `hashlib` readers;
no production loader or metric implementation was used.

| Object | Size | SHA-256 |
|---|---:|---|
| ZIP archive | 5,534,813 bytes | `fcce91f5b1ea66ad687b847a6b0e36538c93cb51d0d6c7ac8d65a04b2c71d306` |
| `fundamentals_sample.csv` | 31,366 bytes | `c32b445667d028b6269f209aa458a6f9c0a6de1fbcd0748d5e7892b09b49cc0b` |
| `prices_sample.csv` | 21,489,968 bytes | `cdebaeb34c8b4b83987504082685c9de52824c63c5fe026a88711e05aa395142` |
| `survivorship_universe.csv` | 326,328 bytes | `bfe1e11b47d9056db7d6aaa41f04b3e6d6aeb468c4a7869153483b330fe7488e` |

The ZIP central directory reports no archive or member comments. The member
timestamps are 2026-06-23, but those timestamps are filesystem/archive metadata,
not an acquisition timestamp, source vintage, or public-availability date.

## Coverage and internal consistency

### Universe summary

Independent counts from the CSV are:

- 3,838 rows and 3,838 unique `symbol` values; no duplicate symbol rows;
- `status=active`: 2,629 (68.5%);
- `status=inactive`: 1,209 (31.5%);
- 3,830 unique `continuity_id` values, with eight continuity IDs reused across
  multiple symbol rows;
- `first_traded`: 2010-06-10 through 2026-06-10;
- `last_traded`: 2010-06-10 through 2026-06-10;
- `n_days`: 1 through 3,947, median 1,165;
- missing `isin`: 1,471 rows;
- missing `company_name`: 1,466 rows;
- missing `listing_date`: 1,480 rows.

The eight repeated continuity IDs may be useful for corporate continuity, but
the archive provides no definition or mapping rule. A symbol and a continuity
ID are therefore not interchangeable identities.

### Price sample

- 359,852 rows, 99 unique symbols;
- dates 2010-06-10 through 2026-06-10;
- 85 sampled symbols are marked active and 14 inactive in the universe table;
- no duplicate `(symbol, date)` keys were found;
- per-symbol row counts range from 504 to 3,947, with median 3,927;
- `isin` is blank on 26,040 of 359,852 rows (7.24%);
- `deliv_pct` is non-empty on 105,463 rows (29.31%).

For all 99 sampled symbols, the minimum and maximum price dates exactly match
`first_traded` and `last_traded` in the universe table. This is a useful internal
join check, not independent proof that either field is economically correct.
It may also indicate that the price sample was selected from the universe table;
it does not establish full-universe price coverage.

The price columns are `adj_close`, `tr_close` and `deliv_pct`. There is no raw
close, open/high/low, volume, explicit adjustment factor, action type, ex-date,
payment date, dividend amount, split ratio, merger treatment, delisting return,
exchange, timezone or session-close convention.

### Fundamental sample

- 417 rows, 17 unique symbols;
- `period_end`: 2018-03-31 through 2026-03-31;
- `announce_date`: 2018-05-26 through 2026-05-22;
- rows per symbol range from 5 to 33 and are visibly unbalanced;
- `revenue_cr` is missing on 50 rows;
- `pat_cr` is missing on 7 rows;
- `eps_basic` is missing on 4 rows;
- `total_income_cr` is missing on 1 row;
- no duplicate `(symbol, period_end, announce_date, consolidated)` identities;
- all 417 declared `announce_lag_days` values equal the calendar-day difference
  between `announce_date` and `period_end`.

The 17 symbols are:

`ABAN`, `DHFL`, `HDFCBANK`, `HINDUNILVR`, `INFY`, `ITC`, `JETAIRWAYS`,
`JPASSOCIAT`, `LT`, `MARUTI`, `RCOM`, `RELCAPITAL`, `RELIANCE`, `RUCHISOYA`,
`SBIN`, `SUNPHARMA`, and `TCS`.

Ten are marked active and seven inactive in the universe table. The date-lag
check validates only the supplied arithmetic. It does not validate that an
`announce_date` is the first public availability of the reported figures.

### Cross-file coverage

| Check | Result |
|---|---:|
| Price symbols contained in universe | 99 / 99 |
| Fundamental symbols contained in universe | 17 / 17 |
| Price/fundamental symbol overlap | 17 |
| Universe names without sampled prices | 3,739 / 3,838 (97.42%) |
| Universe names without sampled fundamentals | 3,821 / 3,838 (99.56%) |
| Price symbols as a share of universe | 99 / 3,838 (2.58%) |
| Fundamental symbols as a share of universe | 17 / 3,838 (0.44%) |
| Fundamental symbols as a share of price sample | 17 / 99 (17.17%) |

These are sample coverage figures, not population estimates.

## License, attribution and reproducibility

### Finding

**Licence status: UNVERIFIED. Attribution status: INCOMPLETE.**

Nothing in the ZIP grants a licence or identifies an author. A Kaggle dataset
licence, if one exists, must be tied to the exact Kaggle dataset reference and
version that generated this archive. A platform-level hosting term is not a
substitute for the uploader's source licence or for the terms of upstream NSE,
vendor or corporate data.

Before using or redistributing this artifact, record:

1. exact Kaggle owner/dataset slug and version number, or the authoritative
   non-Kaggle source;
2. metadata JSON and licence text captured at acquisition;
3. creator, upstream providers and required attribution;
4. permitted internal, commercial and redistribution uses;
5. download timestamp, source revision and file-level hashes;
6. transformation code/version and every filter used to produce the samples.

Until then, the artifact may be retained locally for review but should not be
treated as a redistributable or licensed research release.

## Point-in-time and `announce_date` semantics

### What the artifact supports

The fundamental rows separate `period_end` from `announce_date`, and the
supplied lag is reproducible. This is better than using period end as a proxy
for availability.

### What it does not establish

`announce_date` is a date, not a timestamp. The archive has no timezone, local
exchange session convention, publication time, filing accession/URL, source
document, amendment/restatement marker, retrieval timestamp, or explicit
`effective_date`. It is therefore not proven that:

- the date is the first public release rather than a vendor-normalized date;
- the complete value set was public at the start of that date;
- an after-close announcement is unavailable to a same-day close strategy;
- amendments and restatements are represented as separate vintages;
- missing fundamentals were genuinely unavailable rather than omitted from the
  sample.

For a strict PIT run, the safe interpretation is **date-level availability only,
pending source verification**. The pipeline must not silently promote this field
to a timestamp-level `effective_date`.

The supplied fundamental data also lacks balance-sheet, cash-flow, share-count,
currency and unit metadata beyond the `*_cr` naming convention. It cannot feed
the project's full validated metric engine without a documented normalization
and provenance mapping.

## Universe, inactive and delisted semantics

The `status` field has only `active` and `inactive`; it is not a typed delisting
event. The file does not distinguish delisting, suspension, merger, acquisition,
name change, ticker reuse, data outage or an instrument that simply stopped
appearing in the source.

`last_traded` is a last observed date, not necessarily an exchange-confirmed
delisting date or a realizable exit date. There is no delisting price/return,
liquidation value, corporate-action chain, reason code or post-delisting
outcome. Consequently:

- the presence of 1,209 inactive rows is evidence that the file is not plainly a
  current-survivor-only list;
- it is **not** evidence that all economically relevant delisted names and their
  delisting returns are complete;
- it is **not** evidence of historical universe membership at each research date;
- a backtest using `status=inactive` as a delisting rule would be an unsupported
  assumption.

The 3,838-name table is best described as a symbol-level inventory with trading
interval summaries. It is not yet an immutable sequence of dated
`UniverseSnapshot` membership sets. A historical run cannot answer from this
file alone whether a symbol was eligible on each rebalance date.

## Price and total-return semantics

The name `tr_close` strongly suggests a total-return-related field, but the
archive supplies no definition, formula, adjustment history or source
documentation. It must therefore be treated as **provider-defined/unknown**,
not automatically as a validated total-return series.

Likewise, `adj_close` does not say whether it is split-adjusted, dividend-
adjusted, total-return-adjusted or another vendor adjustment. The sparse
`deliv_pct` field cannot substitute for a dividend ledger; in Indian market data
“delivery percentage” is commonly a trading-delivery measure, and its semantics
are not documented here. It must not be interpreted as a dividend field.

Without raw prices plus a typed corporate-action ledger, it is impossible to
independently prove that:

- a split changes shares and price exactly once;
- dividends are included exactly once in `tr_close`;
- mergers/spin-offs are economically continuous;
- inactive securities receive correct final returns;
- a benchmark and security series use the same price/total-return convention.

The artifact is therefore unsuitable for a return or wealth calculation until
the adjustment policy is documented and reconciled against independent action
records. Any use of `adj_close` or `tr_close` in E1 must carry an explicit
`PriceAdjustmentPolicy`, source version and corporate-action coverage status.

## Ticker identity risks

The price table is keyed operationally by `symbol` and date; `isin` is absent on
7.24% of price rows. The universe table has a `continuity_id`, but its meaning
and mapping rules are undocumented, and eight continuity IDs are reused across
symbol rows. There is no exchange/venue field or effective-dated identifier
mapping.

Risks include ticker reuse, corporate name changes, mergers, symbol changes,
multiple listings and accidental joins on a symbol after an instrument's
identity changed. The observed exact boundary-date joins are reassuring but do
not eliminate these risks.

Required production identity is an effective-dated instrument/security master
with stable ID, exchange, ISIN where available, ticker history, continuity and
corporate-action mappings. Symbol-only joins must remain prohibited for the
economic run.

## Benchmark limitations

The archive contains no benchmark series, benchmark ID, index membership,
benchmark currency, benchmark adjustment policy or risk-free rate. It cannot
support benchmark-relative return, excess return, beta, alpha or a meaningful
strategy comparison. Supplying a current NIFTY index series later would not
repair historical PIT or total-return semantics by itself.

A valid economic run needs a versioned benchmark with matching date windows,
currency, calendar and price/total-return convention, plus provenance and
availability metadata.

## Selection, survivorship and residual bias

The broad table includes inactive names, which is a positive design signal, but
the artifact does not establish that the 3,838 names are a historical
point-in-time universe. It has no membership snapshots, entry/exit dates by
universe, source selection rule or historical constituent revisions.

The price and fundamental panels are explicit samples. Their selection rule is
not recorded. The samples are highly unbalanced and nested: all fundamentals
are in the price sample, while 97.42% of universe names have no sampled prices
and 99.56% have no sampled fundamentals. This creates several residual risks:

- selection on data availability or ease of retrieval;
- overrepresentation of well-known or recently researched names;
- exclusion of hard-to-map names and firms with incomplete identifiers;
- survivorship in the price/fundamental sample despite inactive rows in the
  broader inventory;
- look-ahead through a source-generated sample that was selected after the
  research period;
- inability to separate missing-at-random from economically informative missing
  data;
- omission of delisting and merger outcomes.

The inactive fraction (31.5%) is descriptive only. It cannot be used as a
survivorship-bias correction without verifying how inactive status was assigned
and how final returns are handled.

## Fitness assessment

| Use | Decision | Reason |
|---|---|---|
| Archive integrity/hash smoke test | GO | Files are readable and hashes/counts are reproducible. |
| Schema and identity contract testing | GO, limited | Useful for testing explicit missingness and joins, subject to the identity caveats above. |
| PIT date-field exploratory audit | CONDITIONAL | `period_end`/`announce_date` arithmetic is present, but public-availability semantics are unverified. |
| Full-universe factor efficacy | NO-GO | Only 17 fundamental symbols and no persisted factor-score panel. |
| India profitability claim | NO-GO | No valid benchmark, complete outcomes, licensed provenance or representative sample. |
| Survivorship-free backtest | NO-GO | No dated universe snapshots, typed delisting events or delisting returns. |
| Total-return portfolio simulation | NO-GO | `tr_close`/`adj_close` policy and corporate actions are undocumented. |

The correct conclusion from this artifact is about data readiness, not about
whether any strategy works.

## Explicit GO conditions

Economic validation may proceed only after all of the following are evidenced:

1. **Source and licence:** exact source reference/version, metadata, licence,
   attribution and permitted use are stored in a hash-pinned manifest.
2. **Security master:** stable instrument IDs, effective-dated ticker/ISIN
   mappings, exchange, continuity and symbol-change rules are present.
3. **Historical eligibility:** dated universe snapshots and their source,
   membership rule and digest are available for every research date.
4. **Delisting completeness:** inactive/delisted events, reasons where known,
   final prices/returns and merger/spin-off treatment are explicit; unavailable
   values remain incomplete rather than zero-filled.
5. **PIT filings:** source accession/document, filing/publication timestamp,
   timezone/session rule, amendments/restatements and retrieval lineage are
   recorded. `announce_date` may be used only after this mapping is verified.
6. **Price policy:** raw prices, corporate actions and a documented choice among
   `RAW`, `SPLIT_ADJUSTED` and `TOTAL_RETURN_ADJUSTED` are reconciled. Dividend
   and split effects must be counted exactly once.
7. **Benchmark:** a versioned benchmark with matching currency, calendar,
   adjustment/total-return convention, provenance and risk-free assumptions is
   included.
8. **Coverage:** the research panel is large enough and its selection is
   documented; coverage is reported separately for eligible, usable, excluded,
   inactive and incomplete observations. The 99/17 samples may remain as
   fixtures, but cannot be labelled full-universe evidence.
9. **Independent reconciliation:** selected prices, actions, filings,
   delisting records and representative financial values are checked against
   independent primary or licensed records.
10. **Manifest integration:** a `StatisticalDatasetManifest` names source
    snapshot IDs, factor/universe/benchmark versions, transformations,
    limitations and file digests. The existing loader and E1 cohort filters
    then run without bypassing point-in-time or information barriers.

## Recommended disposition

Retain the archive locally as an **unverified candidate/sample**. Do not call it
the real India PIT dataset in research results, do not publish a profitability
number from it, and do not mark the E1 economic-validation gate complete.

The next data-acquisition step is to obtain either:

- a licensed India market/security-master source with historical membership,
  corporate actions and delisting returns, plus a separate PIT fundamentals
  source; or
- a documented equivalent source whose complete manifest satisfies every GO
  condition above.

Until that evidence exists, the scientifically correct status remains **NO-GO**
for economic validation and **GO only for local integrity/contract review**.

## Required agent report

**WORKSTREAM:** Independent scientific/data-governance review — India PIT dataset

**STATUS:** REVIEW / NO-GO for economic validation

**Scope completed:** Inspected the local ZIP, computed independent counts and hashes, reviewed PIT/statistical dataset contracts and source-governance documentation, and assessed licence, identity, universe, price, fundamental, benchmark and survivorship semantics.

**Files created:** `docs/validation/india-pit-dataset-review.md`

**Files modified:** None

**Tests added:** None; production code was not modified.

**Tests executed:** Independent standard-library ZIP/CSV audit scripts; no repository test suite was changed or required for this documentation-only review.

**Results:** Archive is readable and internally joinable for sampled names; coverage is 3,838 universe names vs 99 price names vs 17 fundamental names. Licence/source identity, PIT availability semantics, dated memberships, corporate actions, delisting returns and benchmark are insufficiently evidenced.

**Architecture issues discovered:** The artifact cannot yet satisfy the repository's manifest contract for source snapshot, benchmark, price-adjustment policy, security master, universe snapshots and filing availability. `announce_date` must not be silently promoted to a timestamp-level `effective_date`.

**Assumptions:** Counts refer exactly to the three CSV members in the local ZIP; blank fields are treated as missing; no external claim was used to infer undocumented column semantics.

**Known limitations:** This review cannot identify the upstream source or licence from the archive alone and cannot independently validate financial values, delisting completeness or total-return construction without source records.

**Shared-contract changes requested:** None.

**Recommended next action:** Acquire and record an authoritative, licensed manifest and complete PIT market/universe/fundamental snapshot; reconcile it independently, then rerun E1 with separate coverage and limitation reporting.
**Exact file changed:** `docs/validation/india-pit-dataset-review.md`
