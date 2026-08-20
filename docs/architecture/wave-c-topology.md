# Wave C topology (design only)

Wave C is contract-frozen but implementation is not launched in this checkpoint. Its implementation
must consume validated B1.5/B2/B3/B4 outputs and must not recalculate provider
facts or bypass persisted point-in-time data.

```text
fundamentals.MetricResult + technical.TechnicalSeries
                  │
                  ▼
        factor models / criteria
                  │
                  ▼
       decomposable FactorScore
                  │
                  ▼
       CompositeScore + explanation
                  │
                  ▼
        ScreeningRun / ResearchResult
```

## Proposed workstreams

| Workstream | Owns | Depends on |
|---|---|---|
| C1 Graham strategies | `strategies/value/` | B1 metrics, provenance, versioned criteria |
| C2 quality/forensic factors | `strategies/quality/` | B1 metrics and independently documented variants |
| C3 scoring | `scoring/` | MetricResult/TechnicalSeries, explicit weights |
| C4 screening | `screening/` | C3 scores, versioned universes, ResearchRun persistence |
| C5 portfolio analytics | `analytics/` | B3 ledger and benchmark contracts |
| C6 backtesting foundation | `backtesting/` | B4 data, B3 ledger, persisted PIT research semantics |

## Contracts to freeze before implementation

- `FactorObservation`: metric/technical input reference, status, value, units,
  provenance references, and calculation version.
- `FactorScore`: factor name/version, normalized score or unavailable status,
  weight, component observations, and rationale.
- `CompositeScore`: immutable weighted components with missing-data policy and
  no hidden provider calls.
- `ScreeningRun`: strategy/version, universe/version, parameters, as-of date,
  data snapshot, and persisted results.
- `BacktestDataView`: only observations whose canonical availability is on or
  before the simulation date; no current-universe substitution without a
  limitation marker.

The frozen contract definitions live in `domain.research_engine`,
`interfaces.research_contracts`, and ADR-003. C1–C6 must consume these seams
and may not modify them independently.

The storage watch remains active: do not add separate storage protocols per
feature unless a concrete capability boundary cannot be expressed through the
existing persistence interfaces.
