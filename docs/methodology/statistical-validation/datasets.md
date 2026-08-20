# E1A — Statistical dataset manifests

E1A provides pure boundary logic for statistical validation datasets. It
accepts a frozen `StatisticalDatasetManifest` and already-persisted
`FactorOutcomeObservation` values. It does not access providers, HTTP, SQLite,
or current data.

## Manifest validation

`validate_manifest` checks the additional dataset-boundary invariants that are
not guaranteed by the frozen domain constructor:

- non-blank identity fields;
- uppercase base currency;
- non-blank and unique factor, universe, benchmark, and source snapshot IDs;
- deterministic observation counts and coverage.

Coverage is selected observations divided by the supplied population size. An
empty population has coverage `0.0`; it is reported rather than converted into
a valid sample.

## Observation selection

`select_observations` uses an inclusive manifest date window and requires:

- a factor version named by the manifest;
- a universe version named by the manifest;
- a benchmark named by the manifest;
- the manifest base currency;
- a non-missing factor score;
- complete security, benchmark, and excess returns;
- a measured/available/valid outcome status.

Rejected records are retained as `ExcludedObservation` values with explicit
`ExclusionReason` values. Selection is deterministic and sorted by as-of date,
ticker, factor name, factor version, horizon, and research-run ID. Inputs are
never mutated.

The current frozen observation contract does not carry a source snapshot ID or
an explicit filing-availability date. E1A therefore validates the identities
available on `FactorOutcomeObservation`; point-in-time availability remains the
responsibility of the persisted observation pipeline that produced those
records.
