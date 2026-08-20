# Wave E.0 statistical-validation data flow

```text
Persisted ResearchRuns / UniverseSnapshots
                    │
Persisted FactorOutcomeObservations
                    │
                    ▼
       StatisticalDatasetManifest
                    │
             frozen partitions
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
 overlapping cohort   non-overlapping cohort
          │                   │
          └─────────┬─────────┘
                    ▼
       cross-sectional IC by date
                    │
       stability / decay / uncertainty
                    │
      multiple-testing and robustness
                    │
                    ▼
        FactorValidationSummary
                    │
        persisted ValidationRun
```

The information barrier remains one-way. Statistical validation may consume
subsequent outcomes; ResearchRun, FactorScore, ThesisSnapshot, and watchlist
history remain immutable. Walk-forward evaluation freezes the methodology
before each out-of-sample window.
