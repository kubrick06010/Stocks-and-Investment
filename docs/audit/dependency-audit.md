# Dependency audit

Agent 3 — Dependency & Execution Auditor

Audit date: 2026-08-19
Scope: requirement files, import coverage, stale/deprecated dependencies, dependency compatibility, and security-sensitive dependency posture. The audit was offline; no package index or vulnerability database was queried.

## Executive result

Both requirement files are unmaintained, exact-pinned snapshots from approximately 2019. They mix an obsolete TensorFlow 1.15 stack with current application code, contain packages not imported by this repository, omit imports that the code requires, and pin network/security-sensitive libraries to versions that should not be retained. They should be replaced after the Python 3.12 source port, not incrementally patched in place.

## Inventory and compatibility assessment

### `requirements.txt`

- 51 exact pins, including `tensorflow==1.15.2`, `tensorflow-estimator==1.13.0`, `numpy==1.16.3`, `pandas==0.24.2`, `matplotlib==3.0.3`, `scipy==1.2.1`, `requests==2.21.0`, `urllib3==1.24.2`, `Werkzeug==0.15.3`, and `PyPDF2==1.26.0`.
- The TensorFlow/Keras/Gast/TensorBoard group is not imported by repository source and is an obsolete, tightly coupled stack. It should be removed unless a separately identified model workload still needs it; if retained, it requires a separately supported ML environment rather than the stock-analysis runtime.
- `comtypes` is Windows/COM-specific and is not imported. It is a portability hazard on the macOS audit host.
- `google-api-python-client`, `google-auth`, `google-auth-httplib2`, `httplib2`, `oauth2client`, and `uritemplate` are not imported by the checked-in code. `google_sheet_class` is imported but is not supplied by either requirements file or the repository.
- `edgar` is imported by `Test/Test_EDGAR.py` but is absent from both requirements files.
- `PyPDF2`, `fpdf`, `seaborn`, `scipy`, `beautifulsoup4`, and several ML/support packages were not identified as required by the active local modules. Confirm usage before retaining them.

### `requirements_stock_class.txt`

- 21 exact pins overlap the main file but still pin `numpy==1.16.2`, `pandas==0.24.2`, `matplotlib==2.2.4`, `requests==2.21.0`, `urllib3==1.24.2`, and `yahoofinancials==1.5`.
- It omits direct imports needed by `mainCode/stock.py`: `pandas-datareader` is listed, but `yahoofinancials` is listed at a historical version with no compatibility contract; the code also relies on the Yahoo provider and lxml/pandas behavior that has changed materially.
- The two requirements files disagree on versions for overlapping packages (`cycler`, `kiwisolver`, and NumPy at minimum), so installing one versus the other does not produce the same runtime.
- `backports.functools-lru-cache` is unnecessary for a native modern Python runtime.

## Offline evidence

The current Python 3.13 environment had these relevant modules available: `requests`, `numpy`, `pandas`, `matplotlib`, and `lxml`. It lacked `pandas_datareader`, `yahoofinancials`, TensorFlow/Keras, Google API modules, `PyPDF2`, `scipy`, `seaborn`, and `edgar`. This is an environment observation, not a claim that those packages should be installed as-is.

`pip check` reported no broken relationships among packages already installed. That does not validate this repository: the repository's legacy requirements were not installed. An offline dry-run of `pip install --no-index -r requirements.txt` failed immediately because the pinned `absl-py==0.7.1` artifact was unavailable locally.

The installed environment also emitted a `RequestsDependencyWarning`: its `urllib3==2.6.3` and `chardet==7.2.0` do not match the supported ranges expected by the installed `requests` build. This warning belongs to the host environment, but it reinforces that dependency compatibility must be tested as a coherent lock, not inferred from individual package presence.

## Staleness and security posture

No live CVE/advisory lookup was performed, so this report does not assign package-specific vulnerability IDs. Nonetheless, the exact pins are materially stale and should be treated as a security and maintenance risk:

- `requests==2.21.0`, `urllib3==1.24.2`, `certifi==2019.3.9`, `idna==2.8`, and `Werkzeug==0.15.3` are old transport/web-stack components. They should not be used for new network-facing execution without an explicit current-version review.
- `oauth2client==4.1.3` is deprecated upstream technology and is not imported here; remove it unless a proven integration requires a supported replacement.
- `PyPDF2==1.26.0`, `google-api-python-client==1.7.8`, and `httplib2==0.12.3` are legacy pins. They are not evidence of an active feature in this checkout and should not be carried forward by default.
- Unbounded/unchecked outbound calls in `stock.py`, `Test/Yahoo_datareader.py`, FTP ticker downloads, and SMTP code make dependency freshness especially important. Add timeouts, TLS/HTTPS enforcement where applicable, status validation, and secret handling as part of the provider migration.
- `Functions and Libs/email_msg.py` contains a hard-coded Gmail password in its `__main__` example. Although this is source hygiene rather than a package issue, credentials must be removed/rotated if real and loaded from a secret manager or environment at runtime.

## Recommended dependency strategy

Do not attempt to make the current pins work on Python 3.12. First port and isolate the application, then create a minimal direct-dependency set. At a minimum, the dependency decision should explicitly cover:

- a maintained market-data provider/client replacing the legacy Yahoo `DataReader` path;
- a maintained `yahoofinancials` alternative or a provider adapter, if fundamentals remain in scope;
- `numpy`, `pandas`, `matplotlib`, `lxml`, and `requests` only where imports and tested behavior require them;
- Google Sheets integration only if `google_sheet_class` is brought into the repository or replaced with a supported client;
- `edgar` only if the EDGAR test is converted into an offline/mockable test and the package is intentionally supported;
- a current SMTP/TLS implementation with credentials supplied externally.

Use a single source of truth (for example, `pyproject.toml` plus a generated lock file), direct pins only for intentional runtime constraints, and a separate optional extra for integrations/ML. CI should install from the lock on Python 3.12, run compile/import checks, and exercise network clients only through fixtures or explicitly marked integration tests.

## Priority actions

| Priority | Action | Reason |
| --- | --- | --- |
| P0 | Remove/rotate the hard-coded email credential and decide whether the email integration is retained. | Immediate secret exposure risk if the value is real. |
| P0 | Remove the TensorFlow 1.x-era bulk unless a real model feature is identified. | Large obsolete attack/maintenance surface with no checked-in imports. |
| P0 | Port code and replace removed pandas APIs before resolving versions. | Dependency changes cannot repair syntax or removed APIs. |
| P1 | Replace exact 2019 pins with a Python 3.12-tested lock and current transport libraries. | Reproducibility and security baseline. |
| P1 | Bring missing integrations into the package or remove their entry points (`google_sheet_class`, `edgar`). | Prevent import-time failures and hidden sibling-directory coupling. |
| P2 | Add dependency/import smoke tests and offline fixtures. | Detect drift without live market/API calls. |

## Structured handoff summary

```yaml
agent: "Agent 3 — Dependency & Execution Auditor"
status: "audit_complete"
authorized_write_scope:
  - docs/audit/runtime-audit.md
  - docs/audit/dependency-audit.md
dependency_status: "legacy_exact_pins_not_suitable_for_modern_runtime"
recommended_runtime: "CPython 3.12"
requirements_files_reviewed:
  - requirements.txt
  - requirements_stock_class.txt
critical_dependency_actions:
  - "replace 2019-era transport/web pins"
  - "remove or isolate TensorFlow 1.x-era stack"
  - "resolve missing google_sheet_class and edgar integrations"
  - "replace legacy Yahoo DataReader/provider path"
  - "remove/rotate hard-coded email credential"
offline_validation:
  pip_check: "passed for host environment only"
  requirements_dry_run: "failed at unavailable absl-py==0.7.1"
  import_smoke: "failed on missing repository dependencies"
files_changed:
  - docs/audit/runtime-audit.md
  - docs/audit/dependency-audit.md
next_owner: "Source/API port owner, then dependency-lock owner"
```
