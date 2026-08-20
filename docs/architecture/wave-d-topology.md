# Wave D topology — implemented

# Historical note

This document originated as the design-only topology. Wave D is now implemented
and validated. It consumes immutable Wave B/C
artifacts rather than recompute historical research with current data.

```text
ResearchRun + ResearchResult + FactorScores + Outcomes
        │
        ├── D1 Thesis Engine
        │       └── D2 Thesis History / Change Detection
        ├── D3 Strategy Comparison
        ├── D4 Factor Efficacy / Outcome Analysis
        ├── D5 Watchlists / Monitoring
        └── D6 Reporting / CLI
```

Dependencies:

- D1 consumes persisted criteria, factor scores, provenance and caveats.
- D2 compares persisted runs; it never regenerates the older thesis.
- D3 compares strategy-versioned ResearchRuns and BacktestRuns.
- D4 joins historical FactorScores to later OutcomeObservations.
- D5 observes new ResearchRuns and records changes without mutating history.
- D6 is a read-only presentation boundary over the persisted artifacts.

The shared contract review for Wave D must preserve the existing information
barrier and distinguish research information from outcome information.
