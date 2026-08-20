# Wave E status

| Workstream | Status | Evidence |
|---|---|---|
| E0 contract freeze | VALIDATED | 7 contract tests; 173 total, 1 live skip |
| E1A Dataset manifests | VALIDATED | deterministic selection, exclusions and coverage |
| E1B Cohort sampling | VALIDATED | overlapping/non-overlapping identity-safe cohorts |
| E1C IC/stability | VALIDATED | dated cross-sectional IC, stability and decay |
| E1D Uncertainty | VALIDATED | seeded IID and moving-block bootstrap |
| E1E Multiple testing | VALIDATED | BH/Holm with family and hypothesis identity guards |
| E1F OOS/walk-forward | VALIDATED | explicit partitions and leakage attacks |
| E1G Dependence/interactions | VALIDATED | identity-safe correlation and fixed Value×Quality interaction |
| E1H Robustness/turnover | VALIDATED | explicit regime slices and traded-notional cost adjustment |
| E1I Independent adversarial review | VALIDATED | two identity defects found, fixed and regression-tested |
| Wave E1 integration | VALIDATED | 144-observation persisted E2E; 245 total tests, 1 live skip |
| E1 real-data PIT pilot | VALIDATED AS INTEGRATION PILOT | Kaggle v3 CC BY sample; 638 observations; PIT + deterministic SQLite rerun; independent economic NO-GO |
| E1 full economic validation | BLOCKED | full licensed panel requested; no publisher response yet |

E1 validates statistical machinery and the bounded real-data ingestion path,
not real-world factor profitability. Synthetic fixtures and the 17-name
fundamental sample prove determinism, identity, persistence and information
barriers; a large independently reviewed PIT panel remains required before
economic conclusions.

## E2–E6 closure

| Workstream | Status | Evidence |
|---|---|---|
| E2 Qualitative filings | VALIDATED | persisted PIT filing evidence and qualitative claims |
| E3 Research automation | VALIDATED | deterministic synchronous automation with provider-free replay |
| E4 Portfolio construction | VALIDATED | deterministic long-only targets, constraints, turnover and cost guards |
| E5 Interactive research | VALIDATED | local read-only service/shell, 11 view kinds, provider kill-switch E2E |
| E6 Optional narrative | VALIDATED | deterministic structured renderer, disabled LLM boundary, narrative CLI |
| Wave E integration | VALIDATED | 481 passed, 1 intentional live-provider skip; lint/type/compile/diff gates green |

E6 deliberately does not add an LLM dependency. Its contract is an evidence-bound
extension point; the structured renderer is the V1 implementation and future
model-backed rendering requires a separate security and reproducibility gate.
