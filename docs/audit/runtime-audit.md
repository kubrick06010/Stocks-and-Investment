# Runtime audit

Agent 3 — Dependency & Execution Auditor

Audit date: 2026-08-19
Scope: Python compatibility, imports, syntax, runtime execution paths, and API compatibility. No source files were changed.

## Executive result

The repository is not executable as a complete Python 3 application. The codebase is a mixed/unfinished Python 2-to-3 migration with four compile-time failures, missing local modules, unavailable declared imports in the audit environment, and multiple APIs removed from current pandas. A dependency refresh alone will not make it run; the source must first be ported and its execution boundaries made explicit.

## Checks performed

- Parsed every `*.py` file with Python 3.13 `ast.parse`.
- Ran `python3 -m compileall -q -f .`.
- Ran an offline import smoke test with `PYTHONPATH=mainCode:Functions and Libs`.
- Inspected imports, path manipulation, deprecated API use, and network/process calls with `rg`.
- Ran `pip check` and an offline `pip install --dry-run --no-index -r requirements.txt`.

## Findings

### Blockers

| ID | Evidence | Impact |
| --- | --- | --- |
| RT-01 | `Functions and Libs/investing.py:50,74`, `Test/ETF_data.py:24-25`, and `Test/expected_requirements.py:16` use `xrange`/Python 2 `print`; all fail parsing under Python 3. | These modules and scripts cannot even be imported or compiled by the recommended runtime. |
| RT-02 | `mainCode/Tradebill_Library.py:10` contains an invalid backtick in the parameter list: `` `signal_IS=9``. | The module has an unconditional `SyntaxError`, independent of installed dependencies. |
| RT-03 | Importing `stock` fails at `mainCode/stock.py:87` because `yahoofinancials` is not installed in the audit environment; importing `Investment_value`/`value_investment_lookup` also requires the absent `google_sheet_class`. | Main entry points cannot be smoke-tested or started from this checkout. `google_sheet_class` is not present in the repository and is referenced through external path hacks. |
| RT-04 | `mainCode/Investment_value.py:140` uses `pd.Panel`, removed in pandas 1.0; line 129 uses `DataFrame.append`, removed in pandas 2.0. | The investment aggregation path will fail on current pandas even after imports are repaired. |
| RT-05 | `mainCode/stock.py:1587,1653` use `pandas_datareader.data.DataReader(..., 'yahoo', ...)`, while the installed environment has no `pandas_datareader`. | Historical-price construction cannot run; the Yahoo reader/provider path should be replaced and tested against a supported data source. |

### High-risk runtime defects

- `mainCode/stock.py:951` and `mainCode/value_investment_lookup.py:226,239,257,275,293` compare strings with `is` instead of `==`. This is implementation-dependent and can silently select the wrong branch.
- `mainCode/stock.py:1583-1587` computes `start_date` when `from_date` is absent but passes `from_date` (still `None`) to `DataReader`; the default date path is therefore incorrect.
- `mainCode/stock.py:1601-1604,1615-1618,1628-1632` use integer indexing on pandas Series (`series[0]`, `series[i]`). Current pandas treats this ambiguously and may raise or change behavior; use explicit positional or label indexing after porting.
- `mainCode/stock.py:1815` uses `range(1, int(self.amount)/2000)`. Python 3 division yields `float`, causing `TypeError`; use integer division after deciding the intended boundary behavior.
- `mainCode/Investment_value.py:223` constructs `datetime(..., d_dummy.month + 1, ...)` without handling December, producing an invalid month.
- `mainCode/Investment_value.py:242` divides by `month_principal[i]` without a zero guard.
- Several functions use bare `except` (`stock.py:987-989,1012-1019`, `value_investment_lookup.py:24-27`). This masks programming errors and makes failure diagnosis unreliable.
- `mainCode/value_investment_lookup.py:2-3` and `Investment_value.py:3` mutate `sys.path` with relative/Windows-specific paths. Behavior depends on the current working directory and unavailable sibling projects.
- `Test/ETF_data.py:5-7` opens a hard-coded Windows file path and then a relative `ticker_ETF.txt`, which is not in the repository. The script has no reproducible input path.
- `Test/Yahoo_datareader.py:27` performs a network request at import/script execution time, without timeout, status validation, or a required API key contract.

### Import and entry-point observations

`email_msg.py` is the only local module that imported cleanly in the offline smoke test. `Algotrading` and `value_investment_lookup` transitively depend on `stock`; `Investment_value` depends on both `stock` and the missing `google_sheet_class`; `Tradebill_Library` is blocked by syntax before imports can be evaluated. The files under `Test/` are executable scripts, not isolated tests: several perform network access or construct API clients at module import time.

## Recommended runtime target

Target **CPython 3.12** for the port, with a clean virtual environment and a lock file generated after the source/API migration. This is a modern, broadly supported target for the scientific Python ecosystem while avoiding a premature 3.13-specific compatibility decision. Do not add Python 2 shims, aliases for removed pandas APIs, or `six`-style dual-runtime branches. Port the code natively to Python 3, then validate the final dependency set on 3.12.

Suggested runtime contract:

1. `python_requires >=3.12,<3.13` during the initial migration.
2. One supported application entry point with package imports; remove `sys.path.append` dependencies.
3. Network clients with explicit timeouts, status checks, and injectable/mockable providers.
4. A test command that does not perform live network calls at collection/import time.
5. Only after those changes, widen the runtime range based on CI evidence.

## Remediation order

1. Fix syntax and Python 2 constructs (`RT-01`, `RT-02`), then compile every file.
2. Decide whether `google_sheet_class`, `edgar`, and email functionality are in scope; package or remove each integration rather than relying on sibling directories.
3. Replace removed pandas constructs and ambiguous indexing.
4. Replace the Yahoo `DataReader` path with a maintained provider adapter and add offline fixtures.
5. Rebuild requirements from imports and tested providers; run a fresh Python 3.12 environment and CI smoke test.

## Structured handoff summary

```yaml
agent: "Agent 3 — Dependency & Execution Auditor"
status: "audit_complete"
authorized_write_scope:
  - docs/audit/runtime-audit.md
  - docs/audit/dependency-audit.md
runtime_target: "CPython 3.12"
runtime_status: "not_runnable_without_source_port_and_dependency_refresh"
blocking_findings: [RT-01, RT-02, RT-03, RT-04, RT-05]
safe_checks:
  compileall: "failed: 4 syntax errors"
  import_smoke: "failed: missing yahoofinancials/google_sheet_class; syntax-blocked Tradebill_Library/investing"
  pip_check: "passed for currently installed packages"
  offline_requirements_resolution: "failed: legacy pinned artifacts unavailable offline"
files_changed:
  - docs/audit/runtime-audit.md
  - docs/audit/dependency-audit.md
next_owner: "Port source/API boundaries before attempting a dependency lock"
```
