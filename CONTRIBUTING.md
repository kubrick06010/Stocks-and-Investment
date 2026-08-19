# Contributing

Thank you for helping improve Stocks and Investment. Contributions should keep
research reproducible, explainable, and explicit about data limitations.

## Before opening a change

1. Search existing issues and pull requests.
2. Use an issue template for bugs, feature proposals, or data-quality concerns.
3. Keep changes focused. Discuss changes to public contracts, persistence
   schemas, financial formulas, or point-in-time semantics before implementing
   them.
4. Never include credentials, private portfolio data, paid datasets, or data
   whose terms prohibit redistribution.

## Development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Run the relevant focused tests while developing, then run the complete offline
suite before requesting review:

```bash
pytest
ruff check src tests
mypy src
```

If a full check cannot run, state exactly what was run and why the remainder
was skipped. Live tests must not be required for ordinary pull requests.

## Pull requests

- Explain the problem and the chosen approach.
- Link the relevant issue or decision record.
- Add or update tests for behavioral changes.
- Document formula definitions, units, missing-data behavior, provenance, and
  known limitations where applicable.
- Keep migrations additive and demonstrate round-trip persistence.
- Avoid unrelated formatting or generated artifacts.
- Update user-facing documentation when commands or outputs change.

## Financial and statistical changes

Changes to calculations require evidence. Include a source or derivation,
boundary cases, independent fixtures, tolerance rules, and an explanation of
how missing or restated data behaves. Backtests must identify their universe,
benchmark, costs, corporate-action treatment, and sources of bias.

## Licensing boundary

New contributions under `src/` are submitted under the MIT terms described in
[LICENSING.md](LICENSING.md). Historical upstream files remain outside that
grant until their copyright holder provides an explicit license. Do not copy
protected expression from the historical implementation into V2.

By submitting a contribution, you represent that you have the right to submit
it under the applicable project terms.

## Conduct and security

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Do not
put vulnerability details in a public issue; follow [SECURITY.md](SECURITY.md).
