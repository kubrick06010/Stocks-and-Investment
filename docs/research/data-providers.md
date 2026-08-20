# Data-provider research

**Checked:** 2026-08-19
**Scope:** U.S. point-in-time fundamentals, prices, corporate actions, licensing, quotas, caching, reproducibility, and survivorship risk.

This is a provider assessment, not a claim that any vendor supplies a bias-free historical database. “PIT” means the source exposes an availability/publication timestamp that we can enforce. A historical period or current snapshot is not PIT by itself.

## Decision at a glance

| Role | Decision | Evidence and limitation |
| --- | --- | --- |
| Canonical U.S. fundamentals | SEC EDGAR APIs, filing archives, stored as-filed documents | SEC exposes submissions and extracted XBRL company facts without an API key; JSON is updated during the day and bulk archives nightly. Filtering by `filed`/availability is our responsibility. [SEC API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) |
| Current fundamentals adapter | `SecEdgarProvider` | Appropriate baseline for U.S. filing-derived facts. Not a quote or complete corporate-action feed; contexts, custom tags, amendments, and issuer mapping require explicit handling. |
| Current market adapter | `AlphaVantageMarketProvider` | Documented OHLCV, split/dividend endpoints, and raw/adjusted series. Free service is 25 requests/day for most datasets; use only within plan and exchange entitlements. [Alpha Vantage docs](https://www.alphavantage.co/documentation/), [limits/adjustments](https://www.alphavantage.co/support/) |
| Default free/local path | SEC + Alpha Vantage, cached locally and opt-in | Suitable for development and small universes, not high-volume refresh or redistribution without reviewing terms. |
| Optional enrichment | FMP, Tiingo, Polygon, EODHD, Alpha Vantage paid, OpenBB, or finagg adapters | Select per deployment and license. None silently replaces SEC as canonical PIT fundamentals. |
| Yahoo/yfinance | Manual/personal fallback only | yfinance calls itself unofficial and intended for research/education; Yahoo terms restrict automated collection and competing archives/feeds. [yfinance](https://ranaroussi.github.io/yfinance/), [Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) |

## Comparative assessment

| Candidate | Fundamentals / PIT | Prices / actions | Cost, limits, licensing | Reproducibility and survivorship |
| --- | --- | --- | --- | --- |
| **SEC direct** | Strongest U.S. source: submissions, company facts, accession, form, filed date, XBRL context/unit. PIT is achievable only after retaining filing identity and filtering availability. | Not a general market-price or corporate-action feed. | Public API, no key; requires identifying User-Agent and fair-access behavior. Real-time JSON; nightly bulk ZIPs. [API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [toolkit](https://api.edgarfiling.sec.gov/) | Excellent as-filed provenance. Amendments/restatements must remain distinct. Ticker history and universe membership are application concerns. |
| **OpenBB / ODP** | Aggregation/router, not canonical evidence. Endpoints can use different providers; PIT depends on selected provider and stored response. | Routes historical price endpoints to providers including Alpha Vantage, FMP, Polygon, Tiingo, and yfinance. [ODP quick start](https://docs.openbb.co/odp/python/quickstart) | ODP is currently AGPL with commercial options; upstream provider terms still apply. [license FAQ](https://docs.openbb.co/odp/python/faqs/license) | Useful integration surface, but it does not remove vintage or survivorship risk. Not a baseline dependency. |
| **finagg** | Aggregation/normalization package; SEC module exposes `filed` and local SQL installation. [project](https://github.com/theOGognf/finagg) | Depends on upstream APIs; not a market-data licensor. | Apache-2.0 code; upstream data terms apply. Includes HTTP cache and SQL storage. | Useful reference for ingestion/cache patterns. Direct SEC ownership keeps our provenance explicit. |
| **Alpha Vantage** | Statements/company overview are provider snapshots unless a vintage is supplied; fiscal period alone is not PIT. | Daily/weekly/monthly/intraday OHLCV; raw/adjusted series; historical split events; adjusted values incorporate splits and cash dividends. [docs](https://www.alphavantage.co/documentation/), [support](https://www.alphavantage.co/support/) | Most datasets: 25 requests/day free; verified open-source/education exception; premium for higher volume and realtime/15-minute U.S. data. | Good documented adapter for small EOD work. Store raw/adjusted separately, response hash, retrieval time, and action payload. No historical universe membership. |
| **yfinance / Yahoo** | Current summaries/statements are not safe historical vintages. | Historical prices, dividends, splits, and adjusted OHLC via unofficial wrapper; adjustment semantics must be recorded. | Open-source wrapper, but documentation says Yahoo data is personal-use oriented; Yahoo terms restrict automated collection and competing databases/feeds. | Convenient but unsuitable as default persistent provider. Current symbol mapping/corrections create reproducibility risk. |
| **Stooq** | No canonical filing fundamentals or public PIT filing model identified. | Daily historical prices are available through download/query pages for supported instruments; adjustment/action semantics are not sufficiently documented for our canonical path. [data page](https://stooq.com/q/d/) | Public access is convenient, but licensing, redistribution, quotas, correction policy, and SLA should be confirmed before use. | Candidate for offline price research only after a written contract and fixtures. Not selected. |
| **FMP** | Broad statements, ratios, estimates and profiles; provider fields are not automatically as-filed PIT vintages. | EOD, realtime/intraday, corporate calendars/actions and bulk features vary by plan. [quickstart](https://site.financialmodelingprep.com/developer/docs/quickstart) | Basic advertises 250 calls/day and EOD/profile/reference; history, bandwidth and endpoints vary. Display/redistribution requires a specific agreement. [pricing](https://site.financialmodelingprep.com/pricing-plans), [terms](https://site.financialmodelingprep.com/developer/docs/terms-of-service) | Strong enrichment candidate, not canonical PIT fundamentals. Persist endpoint, plan/vintage, raw payload and limitations. Historical S&P membership has documented gaps. |
| **Polygon** | Fundamentals/reference endpoints exist, but filing-vintage semantics are not its primary strength. | Strong U.S. coverage, REST/WebSocket/flat files, corporate actions; history and real-time entitlements vary by plan. [overview](https://polygon.io/docs/rest/stocks/overview), [pricing](https://polygon.io/stocks) | Basic advertises 5 calls/min and 2 years; paid plans expand history/access. Market-data terms and exchange licensing apply. [terms](https://polygon.io/terms/market_data_terms.pdf) | Credible paid U.S. market adapter. Requires plan-specific retention/display review and explicit adjustment policy. |
| **EODHD** | Fundamentals available, but endpoint vintage/filing availability must be demonstrated. | EOD, intraday, live, fundamentals, news and corporate actions; broad international coverage. [quick start](https://eodhd.com/financial-apis/quick-start-with-our-financial-apis) | Free advertises 20 calls/day and past-year EOD; paid default 100,000 API calls/day and 1,000 requests/min, with endpoint weights. [limits](https://eodhd.com/financial-apis/api-limits) | Enrichment/global price candidate. Plan licensing, adjustment definitions and universe coverage need metadata. |
| **Tiingo** | Historical statements/daily fundamentals via third-party feed; documentation says usually 12–24h after SEC availability, not a complete as-filed PIT archive. [fundamentals](https://www.tiingo.com/documentation/fundamentals) | EOD raw/adjusted, dividends/splits; adjusted method follows CRSP-style split/dividend adjustments. [EOD](https://www.tiingo.com/documentation/end-of-day) | Starter pricing lists 50 requests/hour, 1,000/day, 1 GB/month and internal-use-only terms; redistribution needs a license. [pricing](https://www.tiingo.com/about/pricing) | Good licensed EOD enrichment and stable `permaTicker` for delisted/recycled symbols, not canonical SEC evidence. |

## Verified facts versus engineering inferences

Verified facts are those stated in the linked primary documentation: SEC API shape/update schedule/access requirements; Alpha Vantage quotas and adjustment behavior; FMP plan/terms; Polygon coverage/plans/terms; EODHD quotas; Tiingo pricing, permaTicker and adjustment description; OpenBB license/routing; yfinance legal notice; and finagg cache/SQL architecture.

Engineering inferences for this repository:

* A source is PIT-capable only when we preserve availability time and reproduce the information set. “Historical” or “adjusted” does not prove it.
* SEC should be canonical for U.S. filing facts because it is the primary filing source and exposes filing metadata. This does not mean every XBRL fact is comparable without context mapping.
* Provider ratios, estimates, profiles and “latest” endpoints are snapshots unless a valid vintage is exposed and stored.
* No candidate supplies historical index membership by default. Persist `UniverseSnapshot` or record survivorship limitation.

## Recommended architecture and cache policy

1. Keep `SecEdgarProvider` canonical for U.S. fundamentals. Store raw payload, accession, form, XBRL concept/unit/context, `filed_at`, retrieval time, and content hash. Filter `filed_at <= as_of`; retain amendments/restatements.
2. Keep `AlphaVantageMarketProvider` as the documented EOD adapter for development/small universes. Persist raw and adjusted bars separately and explicit split/dividend events. Never add explicit dividends to a total-return/dividend-adjusted series.
3. Treat FMP, Polygon, EODHD, Tiingo, Alpha Vantage paid, OpenBB and finagg as optional. Retain provider, endpoint/parameters, plan/vintage, retrieval time, adjustment mode, raw identifier and licensing scope.
4. Keep yfinance and Stooq out of the default persistent path until legal terms, stability, adjustment semantics and correction behavior are documented.
5. Use immutable/content-addressed raw cache for filings/responses. Use refreshable price windows only within provider license. Cache is not redistribution permission.
6. Keep ticker-to-CIK/security identity and historical universe membership application-owned; persist mapping versions and stable IDs where available.

## Existing adapter handoff and open risks

The implementation currently contains `SecEdgarProvider` and `AlphaVantageMarketProvider`; this refresh adds no provider or code. Both remain behind provider-neutral interfaces and must not calculate ratios or silently apply corporate actions. Live tests are opt-in and normal tests stay offline.

Remaining risks are SEC XBRL context/custom-tag/amendment handling; Alpha Vantage’s low free quota; paid-provider display/retention/exchange entitlements; delisted-symbol identity; and historical universe membership. Before adding another adapter, add tests for raw provenance, adjustment policy, retry/quota behavior and PIT filtering.
