# Wave E.0 statistical-validation contracts

Wave E evaluates whether relationships observed in Wave D are credible. It does
not create new factor scores, alter historical ResearchRuns, or optimize
strategies.

Canonical records live in `domain/statistical_validation.py`:

- `StatisticalDatasetManifest` freezes data window, source snapshots, factor,
  universe, benchmark, currency, and known limitations.
- `ValidationCohort` identifies a dataset partition, cohort identity, sampling
  policy, immutable observation membership, and minimum evidence requirements.
- `CrossSectionalICObservation` keeps one research date and population attached
  to one rank IC result.
- `ConfidenceInterval` records method, confidence level, resample count, and
  block size where temporal dependence requires it.
- `HypothesisTestResult` records the hypothesis family and multiple-testing
  correction.
- `WalkForwardWindow` prevents development/validation data from overlapping the
  out-of-sample evaluation period.
- `FactorValidationSummary` remains decomposable into dated IC observations and
  uncertainty evidence.
- `StatisticalValidationRun` freezes methodology and dataset versions.

## Invariants

1. Inputs are persisted `FactorOutcomeObservation` records, never current data.
2. Factor, universe, benchmark, horizon, cadence, and currency identity cannot
   be mixed silently.
3. Development, validation, and out-of-sample partitions are immutable.
4. Non-overlapping sampling cannot claim overlapping outcome windows.
5. Confidence and significance claims require an explicit methodology version.
6. Multiple-testing corrections retain the full hypothesis family identity.
7. A future outcome may evaluate a frozen factor score but cannot modify it.
8. No validation service mutates a strategy or tunes weights automatically.

Service seams live in `interfaces/statistical_validation.py` and remain
provider-independent.
