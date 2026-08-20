# India PIT real-data pilot — economic validation gate

## Verdict

**NO-GO for factor profitability or strategy efficacy claims.**

The exact Kaggle v3 artifact was acquired, hash-pinned, normalized, persisted,
closed, reopened and evaluated without provider calls. It proves that the
external-artifact and point-in-time validation path works on real data. It does
not supply the breadth, independent source verification, benchmark authority or
terminal-return semantics required for economic validation.

The full-panel access request is public at
[Finance-broski/pit-data-sample#1](https://github.com/Finance-broski/pit-data-sample/issues/1).
No purchase, commercial term or raw-data redistribution has been accepted.

## Acquired artifact

| Field | Value |
|---|---|
| Publisher | Finance_Broski |
| Dataset | Survivorship-Free Indian Equity Data (NSE/BSE) |
| Kaggle version | 3 |
| Declared license | CC BY 4.0 |
| Published | 2026-06-23T08:36:36.933Z |
| ZIP bytes | 5,534,813 |
| ZIP SHA-256 | `fcce91f5b1ea66ad687b847a6b0e36538c93cb51d0d6c7ac8d65a04b2c71d306` |
| Tracked manifest | `data/manifests/india-pit-sample-v1.json` |
| Raw redistribution | disabled; `data/external/` is ignored |

The Kaggle metadata ties the declared CC BY 4.0 license to this dataset version.
That does not independently establish the publisher's upstream rights in every
NSE/BSE-derived field. The exact source documents, extraction code and action
ledger are not in the ZIP, so those claims remain source assertions rather than
independently reproduced evidence.

## Coverage

The archive contains 3,838 inventory rows, including 1,209 marked inactive,
359,852 price rows for 99 symbols and 417 fundamental rows for 17 symbols. One
raw fundamental symbol has no usable positive-revenue observation under the
pilot formula, leaving 16 usable fundamental symbols.

The deterministic run used 28 quarter-end research dates from 2018-06-30
through 2025-03-31 and 3M/12M horizons:

| Measure | Result |
|---|---:|
| Factor-outcome observations | 638 |
| Usable observations | 556 |
| Excluded observations | 82 |
| Terminal-cash approximations excluded | 32 |
| Missing outcomes excluded | 50 |
| 3M coverage | 90.28% |
| 12M coverage | 84.01% |

The factor is explicitly a pilot: latest announce-date-available quarterly
`PAT / revenue`, ranked cross-sectionally from 0 to 100. It is not a production
Quality factor and was not optimized against outcomes.

## Descriptive results

| Horizon | Mean dated rank IC | 95% moving-block interval | Pooled top-bottom excess spread |
|---|---:|---:|---:|
| 3M | 0.0537 | [-0.1145, 0.2431] | -0.0193 |
| 12M | -0.0531 | [-0.2652, 0.1622] | -0.1803 |

Both uncertainty intervals include zero. The statistics are descriptive of a
small, selected sample and must not be read as evidence that profitability
margin helps or hurts expected returns. The large negative 12M pooled spread is
especially vulnerable to selection, composition, overlapping windows and
unverified benchmark/terminal semantics.

## Point-in-time and outcome controls

- `period_end` and `announce_date` remain distinct.
- A row is unavailable before its `announce_date`.
- Future prices are used only in the outcome layer.
- Symbol identity is preserved through every calculation.
- Missing active-security horizon prices remain missing.
- Inactive-security last-price/cash approximations carry a distinct status and
  are excluded from validation evidence.
- The source ZIP and every member file are SHA-256 verified before parsing.
- Derived observations are persisted with the source snapshot identity.
- SQLite close/reopen equality is verified without HTTP/provider access.
- A second clean SQLite run produced the same observations, derived SHA-256
  (`6f838c75d517296613b7e953661dc59574afca06498d4ac2f2fa2fc764b5f6ca`),
  exclusions and economic payload.

## Why this is not the requested large validation dataset

The 3,838-row file is a security inventory with first/last traded dates, not a
complete sequence of official dated index memberships. Prices cover only 99
symbols and fundamentals only 17; 16 have a usable positive-revenue input and
15 appear in the pilot window. The source also mixes consolidated and
non-consolidated statements. The sample has no raw action ledger,
exchange-confirmed delisting return, authoritative benchmark series, accession
or source-document identity, restatement history, or timestamp-level
availability convention.

The publisher describes a non-public full panel with about 3,800 price series,
about 1,400 announce-date fundamental histories and PIT membership. Access,
license scope and methodology evidence are pending the issue linked above.

## Acceptance conditions for the full panel

Economic validation remains blocked until an acquired snapshot provides:

1. a signed/explicit license covering project use, local retention and derived
   aggregate publication;
2. immutable file/version identifiers and hashes;
3. dated universe membership or a documented reproducible eligibility rule;
4. stable instrument identity across renames, mergers and ticker reuse;
5. typed corporate actions and economically defined delisting outcomes;
6. as-reported fundamentals with first-public availability and revisions;
7. a matching total-return benchmark and currency/calendar convention;
8. enough cross-sectional and longitudinal coverage for held-out,
   non-overlapping and regime analysis;
9. independent source and economic review before any alpha claim.

## Reproduction

With the untracked ZIP at the manifest-declared path:

```console
PYTHONPATH=src python3 -m stocks_investment.statistical_validation.india_pit_validation
```

Generated CSV, SQLite and JSON outputs are written under
`data/derived/wave_e/india-pit-pilot-v1/` and intentionally ignored by Git.
