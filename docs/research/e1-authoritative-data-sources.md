# E1 authoritative dataset decision

## Finding

The current repository can validate statistical machinery offline, but a
credible economic run needs two distinct evidence families:

1. point-in-time filings and accounting observations;
2. historical prices, corporate actions, delistings and universe membership.

No public source found during this review provides all of those fields at the
required scale with independently verifiable methodology. One real CC BY
sample has now been acquired and used to validate the integration path, but it
does not close the economic gate.

## Candidate sources

| Source | Useful coverage | Missing/constraint | Decision |
|---|---|---|---|
| [SEC EDGAR APIs](https://www.sec.gov/edgar/sec-api-documentation) | public submissions, XBRL facts and filing availability | no complete market-price, delisting or historical-index-membership dataset | use for US filing evidence where acquired and cached |
| [CRSP US Stock Database](https://www.crsp.org/research/crsp-us-stock-database) | active/inactive securities, corporate actions and delisting history; academic-grade market history | licensed/institutional access; redistribution terms must be confirmed | preferred authoritative market/universe source when licensed |
| [Finance_Broski India PIT sample](https://www.kaggle.com/datasets/financebroski/survivorship-free-indian-equity-data-nsebse) | 3,838-name inventory, 99 total-return price histories, 17 announce-date fundamental histories; Kaggle v3 declares CC BY 4.0 | bounded selected sample; no independently reproduced action/delisting methodology, authoritative benchmark or full dated membership panel | acquired and hash-pinned for real-data integration only; economic `NO-GO` |
| Finance_Broski full India panel | publisher describes ~3,800 price histories, ~1,400 PIT fundamental histories and historical membership | non-public; access, full-panel license, schema and source evidence pending | access requested in [issue #1](https://github.com/Finance-broski/pit-data-sample/issues/1) |
| Public Kaggle/GitHub archives | potentially useful exploratory prices | provenance, licence, PIT universe and delisting completeness vary | never treat as authoritative without independent verification |

The SEC's official API documentation describes public submissions and extracted
XBRL data, while CRSP's documented product scope includes active and inactive
securities and delisting history. These are complementary, not interchangeable.

## Required acquisition manifest

Before an economic validation run, persist separate hash-pinned artifacts for
filings and market/universe data, each with:

- source URI and provider/version;
- licence identifier and permitted use;
- acquisition timestamp;
- SHA-256 content hash;
- coverage window and base currency;
- universe membership/delisting semantics;
- mapping from artifact snapshot to `StatisticalDatasetManifest`.

The artifact boundary now supports both canonical factor-outcome CSVs and the
exact hash-pinned India sample bundle. The acquisition manifest records Kaggle
dataset/version identity, declared license, member hashes and limitations. Raw
and derived data remain outside Git.

## Decision

Keep the E1 machinery and the India real-data pilot validated, but keep economic
conclusions unvalidated until the requested full panel or an authorized
CRSP/Compustat-/Sharadar-equivalent snapshot passes the acceptance conditions.
SEC-only data cannot close survivorship and price-history requirements. See the
[pilot review](../validation/india-pit-economic-validation.md) and
[ADR-011](../decisions/ADR-011-real-pit-data-evidence-gate.md).
