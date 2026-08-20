# ADR: Data-provider strategy

- **Status:** Accepted
- **Date checked:** 2026-08-19
- **Decision owners:** Data Provider Research / Program Lead

## Context

The repository needs two evidence classes: issuer financial facts reconstructable as of a historical public-availability date, and market prices/corporate actions with provider-specific adjustment and licensing semantics. The current code implements `SecEdgarProvider` and `AlphaVantageMarketProvider`. This ADR freezes their roles without allowing provider schemas into the domain.

## Decision

1. **SEC EDGAR is canonical for U.S. issuer fundamentals and filing metadata.** Use submissions, company facts, filing archives and as-filed documents. Retain accession, form, XBRL context/unit, period, amendment identity and `filed_at`; expose facts historically only when availability is at or before `as_of`.
2. **Alpha Vantage remains the default market adapter for local/small-universe EOD work.** Its documentation covers time series, splits and raw/adjusted series. The adapter preserves adjustment policy and never double-counts explicit actions.
3. **The default free path is SEC + Alpha Vantage with local raw caching.** This is a development/small-research default, not a promise of high-volume capacity or redistribution rights. Alpha Vantage documents 25 API requests/day for most free datasets, with a verified open-source/educational exception.
4. **Paid/enriched alternatives are opt-in:** FMP, Polygon, EODHD, Tiingo, Alpha Vantage paid, OpenBB or finagg may be added behind the same interfaces after plan, vintage, retention, display and redistribution review. FMP, Polygon, EODHD and Tiingo are enrichment/market candidates; OpenBB and finagg are aggregation/integration options, not canonical evidence sources.
5. **Yahoo/yfinance and Stooq are not default automated providers.** yfinance documents unofficial/personal-use limitations and Yahoo terms restrict automated collection and competing archives/feeds. Stooq’s public history lacks enough authoritative licensing, adjustment, correction and PIT documentation for the canonical path.
6. **No provider supplies historical universe membership by assumption.** `UniverseSnapshot` is application-owned and versioned. Current constituents used historically must carry a survivorship limitation.

## Evidence boundary

Primary sources checked on 2026-08-19:

* [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) and [EDGAR API toolkit](https://api.edgarfiling.sec.gov/) — company facts/submissions, updates, bulk archives, User-Agent and rate-limit behavior.
* [Alpha Vantage API](https://www.alphavantage.co/documentation/) and [support](https://www.alphavantage.co/support/) — time series, split endpoint, quotas and split/cash-dividend adjustment.
* [FMP pricing](https://site.financialmodelingprep.com/pricing-plans) and [terms](https://site.financialmodelingprep.com/developer/docs/terms-of-service).
* [Polygon stocks/pricing](https://polygon.io/stocks), [REST overview](https://polygon.io/docs/rest/stocks/overview) and [market-data terms](https://polygon.io/terms/market_data_terms.pdf).
* [EODHD limits](https://eodhd.com/financial-apis/api-limits) and [quick start](https://eodhd.com/financial-apis/quick-start-with-our-financial-apis).
* [Tiingo pricing](https://www.tiingo.com/about/pricing), [fundamentals](https://www.tiingo.com/documentation/fundamentals) and [EOD](https://www.tiingo.com/documentation/end-of-day).
* [OpenBB ODP quick start](https://docs.openbb.co/odp/python/quickstart) and [license FAQ](https://docs.openbb.co/odp/python/faqs/license).
* [finagg](https://github.com/theOGognf/finagg), [yfinance](https://ranaroussi.github.io/yfinance/), [Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html), and [Stooq data page](https://stooq.com/q/d/).

The provider comparison in [data-provider research](../research/data-providers.md) distinguishes these verified claims from engineering inferences. Vendor plans and terms are time-sensitive and must be rechecked before deployment or redistribution.

## Rationale

SEC is the strongest baseline for U.S. filing provenance because it is the primary filing source and exposes availability metadata. It does not solve prices, corporate actions, ticker identity or historical index membership. Alpha Vantage is retained because it is the currently implemented, documented market adapter and makes adjustment policy explicit, while its quota is honest for local fixtures and small refreshes.

OpenBB can route multiple providers, but routing does not create PIT semantics. finagg is useful prior art for cache/SQL aggregation, but direct SEC ownership keeps our contracts explicit. FMP, Polygon, EODHD and Tiingo are credible optional enrichments with different history, quota and licensing trade-offs. Yahoo/yfinance and Stooq do not currently meet the default reproducibility/licensing bar.

## Consequences

### Positive

- Historical fundamentals can be filtered by public availability rather than current “latest” values.
- Market adjustment semantics are explicit and testable.
- Provider changes stay behind adapters and do not alter domain calculations.
- Raw payloads, provenance and content hashes support audit and schema-drift diagnosis.

### Costs and limitations

- SEC XBRL requires taxonomy/context mapping, issuer handling, amendment policy and CIK/security identity management.
- Alpha Vantage’s free tier cannot support broad frequent screening; paid licensing/entitlements must be reviewed before distribution.
- Paid alternatives have plan-dependent history, quotas, exchange rights and retention/display conditions.
- None removes survivorship bias; historical universes must be persisted separately.
- Different adjustment/correction policies may produce different valid results; source and policy must remain visible.

## Operational requirements

- Send a truthful identifying SEC User-Agent; honor fair access, 429s, bounded concurrency, retries and backoff.
- Persist `as_of`, `effective_date`/`filed_at` and `retrieved_at` separately.
- Preserve raw/adjusted/total-return distinctions and explicit corporate actions.
- Store provider, endpoint/parameters, plan or entitlement, raw identifier, content hash and schema/version.
- Never use a current snapshot as a historical vintage without a valid provider vintage.
- Keep failures visible; missing data is not zero and fallbacks retain source identity.

## Rejected alternatives

- **Yahoo/yfinance as default:** unofficial/personal-use path and current terms are inadequate for an automated persistent mirror.
- **FMP as canonical fundamentals:** broad and convenient, but provider-derived and plan-dependent; not SEC as-filed provenance.
- **OpenBB as canonical source:** routing/aggregation platform; underlying provider remains the evidence and licensing boundary.
- **finagg as runtime foundation:** useful reference, but its dependency/upstream choices should not dictate domain/storage contracts.
- **SEC only:** cannot supply complete EOD price and corporate-action semantics.
- **Unversioned latest cache:** destroys restatement and PIT reproducibility.

## Follow-up contract requests

1. Keep or extend `MarketDataProvider` with an explicit corporate-actions capability returning typed action semantics.
2. Add raw-response persistence/content hashes at the data boundary.
3. Extend provenance or attach typed provider evidence for endpoint, parameters, accession/context, adjustment mode, entitlement and delay metadata.
4. Keep ticker-to-CIK/security identity and historical ticker changes in application-owned reference data.
5. Make quota/retry/provider-error taxonomy observable so rate limits do not become silent missing observations.
