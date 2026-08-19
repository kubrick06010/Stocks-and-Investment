# Stocks and Investment

[![Project status: Alpha](https://img.shields.io/badge/status-alpha-f59e0b)](#current-capabilities)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](#quick-start)
[![License: MIT (V2)](https://img.shields.io/badge/license-MIT%20(V2)-2ea44f)](LICENSING.md)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-0e8a16)](CONTRIBUTING.md)

Stocks and Investment is an explainable, reproducible investment-research
engine. Its V2 architecture turns point-in-time market and fundamental data
into auditable metrics, screens, scores, theses, backtests, watchlists, and
historical reports.

> [!IMPORTANT]
> V2 is alpha software for research and informational purposes. It does not
> place trades, provide financial advice, or guarantee the accuracy of data or
> results.

## Why this project exists

Investment research is difficult to reproduce when formulas, data vintages,
universe membership, and assumptions are implicit. V2 makes those decisions
explicit and keeps provenance attached to the resulting research artifacts.

Core design goals:

- point-in-time data access that rejects future observations;
- versioned formulas, factors, strategies, and research runs;
- explainable screening and scoring rather than opaque recommendations;
- persisted assumptions, limitations, and source provenance;
- deterministic offline tests with optional live-provider checks;
- provider-neutral interfaces and a local SQLite persistence layer.

## Current capabilities

- Fundamental metrics and Graham-style value criteria
- Quality factors, normalization, scoring, and screening
- Portfolio performance analytics and benchmark alignment
- Low-frequency backtesting with explicit costs and corporate actions
- Thesis snapshots, change history, and watchlist transitions
- Strategy comparison and factor-efficacy summaries
- Statistical validation primitives for sampling, uncertainty, multiple
  testing, dependence, information coefficients, and walk-forward analysis
- SEC, Alpha Vantage, and deterministic fixture providers
- SQLite persistence plus text, JSON, and Markdown reporting

Architecture, methodology, validation evidence, and roadmap documentation are
maintained alongside their corresponding V2 implementation workstreams.

## Quick start

V2 requires Python 3.12 or newer.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Check the installation:

```bash
stocks version
stocks doctor
```

Run the offline test suite:

```bash
pytest
```

Tests marked `live` require network access and provider credentials or quota;
they are excluded from normal offline validation.

## CLI

The CLI reads persisted research from SQLite. Commands that inspect research
history require `--db` and, where applicable, a ticker.

```bash
stocks thesis AAPL --db research.sqlite
stocks changes AAPL --db research.sqlite --format json
stocks report AAPL --db research.sqlite --format markdown
stocks watchlist --db research.sqlite
stocks compare-strategies --db research.sqlite --backtest-a run-a --backtest-b run-b
stocks factor-efficacy quality --db research.sqlite --horizon 12M
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/stocks_investment/` | New V2 package |
| `tests/` | Unit, contract, integration, E2E, and adversarial tests |
| `docs/architecture/` | Contracts, topology, data flow, and status |
| `docs/methodology/` | Research and validation methodology |
| `docs/audit/` | Legacy, dependency, runtime, and formula audits |
| `Functions and Libs/`, `mainCode/`, `Test/` | Historical upstream implementation; not part of V2 releases |

## Legacy code and licensing

The historical upstream repository did not declare an open-source license.
The MIT grant applies only to the new V2 implementation under `src/`; it does
not retroactively license inherited files. The upstream clarification request
is public in [galanCA/Stocks-and-Investment#28](https://github.com/galanCA/Stocks-and-Investment/issues/28).

Read [LICENSING.md](LICENSING.md) before redistributing any part of this
repository.

## Contributing and support

Before contributing, read [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Use the issue templates for reproducible
bug reports, feature proposals, and data-quality concerns. General usage help
is described in [SUPPORT.md](SUPPORT.md); security concerns belong in the
private process documented in [SECURITY.md](SECURITY.md).

## Disclaimer

This software and its outputs are provided for research and informational
purposes only. They are not investment, tax, accounting, or legal advice.
Market and fundamental data may be delayed, incomplete, adjusted, restated, or
incorrect. Independently verify every input, assumption, and result before
making a financial decision.
