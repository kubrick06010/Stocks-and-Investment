# Wave E1I — adversarial statistical review

## Scope

This review tests the public Wave E statistical-validation primitives without
providers, storage, or production changes. The test inputs are synthetic and
the expected values are hand-derived in the test itself.

Owned artifacts:

- `tests/integration/test_wave_e_adversarial.py`
- `docs/validation/wave-e-statistical-review.md`

## Adversarial coverage

- Dataset selection preserves ticker/date identity, reports missing outcomes,
  does not turn missing values into zero, and rejects mixed factor, universe,
  benchmark, and currency identities.
- Cohort sampling is deterministic under input reordering, applies
  non-overlap independently per ticker, and rejects a horizon mismatch.
- Cross-sectional IC is keyed by date and ticker, handles tied ranks using
  average ranks, rejects duplicate securities, and rejects incompatible
  cohort identity.
- Bootstrap confidence intervals are reproducible for a fixed seed, preserve
  the ordered-date contract, and do not mutate inputs.
- Multiple-testing correction is invariant to input order and rejects mixed
  hypothesis families.
- Walk-forward assignment keeps development and out-of-sample evidence
  separate, rejects reordered schedules, and is invariant to evidence order.
- Factor dependence joins by security identity, has a hand-checked Spearman
  result, and rejects mixed universes.
- Rebalance economics are checked independently through the existing public
  `rebalance_metrics` API: gross traded notional, turnover, cost, investable
  capital, zero turnover, and partial turnover.

## Hand-derived checks

For the factor-dependence case, joined values are:

```text
AAA: Value 1, Quality 20
BBB: Value 2, Quality 30
CCC: Value 3, Quality 10
```

The rank sequences are `(1, 2, 3)` and `(2, 3, 1)`, producing Spearman rho
`-0.5`.

For the turnover case, a 1,000 portfolio changes from AAA/BBB/CCC values
`500/300/200` to AAA/BBB/DDD target weights `25%/25%/50%`. The traded
notional is `250 + 50 + 200 + 500 = 1,000`; turnover under the implemented
gross-notional convention is `1.0`; at a 1% rate the cost is `10`, leaving
`990` investable.

## Results

Initial independent focused command:

```text
python3 -m pytest -q -p no:cacheprovider tests/integration/test_wave_e_adversarial.py
12 passed, 2 failed (release-blocking adversarial findings)
```

Additional checks:

```text
ruff check tests/integration/test_wave_e_adversarial.py     PASS
mypy src                                                   PASS (68 files)
python3 -m pytest -q -p no:cacheprovider                  234 passed, 2 failed, 1 skipped
python3 -m compileall -q src                             PASS
git diff --check                                          PASS
```

The first test run exposed only an error in the newly written test context
around an intentionally reversed bootstrap input; the test was corrected so
the expected public API error is asserted explicitly.

The independent adversarial run exposed two production defects:

1. `calculate_factor_dependence` raises `KeyError` when factor A and factor B
   have asymmetric `(ticker, as_of)` key sets. The implementation computes a
   union of keys but then indexes both dictionaries unconditionally. It must
   pair only shared keys and report union/sample coverage.
2. `adjust_hypotheses` accepts duplicate `hypothesis_id` values in one family.
   Its adjusted-value dictionary is keyed by that ID, so one result overwrites
   the other. It must reject duplicate identities or return a representation
   that preserves both uniquely.

The Program Lead subsequently fixed both identity defects: factor dependence
now intersects shared keys while retaining union-based coverage, and multiple
testing rejects duplicate hypothesis IDs. The final adversarial/full gates are:

```text
Wave E adversarial suite                              PASS
python3 -m pytest -q -p no:cacheprovider             245 passed, 1 skipped
ruff check src tests                                  PASS
mypy src                                               PASS (69 files)
python3 -m compileall -q src                           PASS
git diff --check                                       PASS
```

## Limitations and recommended follow-up

The final integration also exercises the public `robustness` module with
pre-labelled yearly slices and a hand-derived traded-notional cost adjustment.
The original independent turnover checks continue to verify the underlying C6
portfolio economics separately.

These tests do not claim statistical significance, causal efficacy, or
economic validity of any factor. They validate identity preservation,
cohort integrity, deterministic behavior, explicit missing-data handling,
and information-partition mechanics. The next integration layer should wire
these primitives into persisted validation runs and retain the same cohort
identity fields in every derived result.
