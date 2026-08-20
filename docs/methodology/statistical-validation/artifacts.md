# E1J — Hash-pinned dataset artifacts

`load_factor_outcome_csv` is the offline boundary for an externally acquired
historical factor/outcome dataset. It requires:

- a SHA-256 digest;
- a license identifier;
- a source URI;
- a snapshot identity;
- the canonical factor/outcome column schema.

The loader does not download, repair, fill, or reinterpret data. Blank numeric
cells remain `None`, non-finite values are rejected, duplicate security/date
identities are rejected, and rows are returned in deterministic identity order.
The resulting observations still require `StatisticalDatasetManifest` cohort
selection before analysis. `validate_artifact_manifest` additionally requires
the artifact snapshot ID to be named by that manifest before reporting the
artifact as valid.

This enables reproducible ingestion once an authorized PIT source is supplied;
it does not itself provide a source or establish investment performance.
