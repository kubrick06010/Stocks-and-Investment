# ADR-002: canonical market records and explicit adjustment semantics

Status: accepted

## Decision

`PriceBar`, `Quote`, and corporate actions are canonical domain records in `domain/market.py`, not provider-layer schemas. Interfaces import them from the domain. The data package re-exports them only as a compatibility convenience.

Corporate actions are a tagged union of `DividendAction`, `SplitAction`, and `SpinoffAction`. Dividends carry `amount_per_share` and currency; splits carry numerator/denominator and expose a factor; spinoffs carry a distributed ticker and distribution ratio. No generic numeric `value` is permitted.

Price data carries `PriceAdjustmentPolicy`: `RAW`, `SPLIT_ADJUSTED`, `TOTAL_RETURN_ADJUSTED`, or `PROVIDER_ADJUSTED`. Providers must declare the policy; `PROVIDER_ADJUSTED` is intentionally not interpreted by the domain. Portfolio reconstruction uses raw prices plus explicit actions unless a total-return series is explicitly requested.

## Consequences

Technical indicators must state their input adjustment policy. Backtests and portfolio valuation cannot silently mix raw, split-adjusted, and total-return series. Provider adapters normalize into these records before storage.
