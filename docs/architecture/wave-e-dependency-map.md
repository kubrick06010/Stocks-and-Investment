# Wave E.0 dependency and ownership map

| Workstream | Owned implementation | Inputs | Forbidden dependencies |
|---|---|---|---|
| E1A Dataset manifests | `statistical_validation/datasets.py` | persisted outcomes, universe snapshots | providers, scoring |
| E1B Cohort sampling | `statistical_validation/sampling.py` | manifests, cohort identity | strategy mutation |
| E1C IC and stability | `statistical_validation/information_coefficient.py` | frozen cohorts | providers, current data |
| E1D Uncertainty | `statistical_validation/uncertainty.py` | dated statistics | factor recomputation |
| E1E Multiple testing | `statistical_validation/multiple_testing.py` | hypothesis families | parameter optimization |
| E1F OOS/walk-forward | `statistical_validation/walk_forward.py` | frozen windows/runs | rewriting methodology versions |
| Integration | `statistical_validation/engine.py` | E1A–E1F contracts | analytical duplication |

Each implementation agent owns the matching test module and methodology page.
No feature agent may edit `domain/`, `interfaces/`, `storage/`, or another
workstream. Shared changes require Program Lead review.

E2 qualitative filings, E3 automation, E4 portfolio construction, E5 UI, and
E6 optional LLM narrative remain closed until E1 passes its integration gate.
