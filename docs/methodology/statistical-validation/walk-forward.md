# Walk-forward validation

E1F defines the chronology boundary for out-of-sample validation. A
`WalkForwardWindow` has three inclusive date ranges:

1. `development`: methodology-definition data;
2. `validation`: optional methodology-check data;
3. `out_of_sample`: data used only after the methodology boundary is frozen.

## Schedule rules

`validate_walk_forward_windows` requires unique window IDs and one
`methodology_version` for the complete schedule. Windows must be supplied in
chronological order. The next development period must begin strictly after the
previous out-of-sample period ends. This strict gap is deliberate because
`DateWindow` endpoints are inclusive; sharing an endpoint would assign one
observation to two windows.

The validator returns `VALID` or an explicit `INCOMPATIBLE_COHORT` result with
diagnostic errors. It never silently sorts an invalid schedule into a valid
one: order is part of the declared walk-forward methodology.

## Evidence assignment

`assign_evidence_to_partitions` consumes immutable records exposing a
date-valued `as_of` attribute. Each record is assigned to at most one
`(window_id, DataPartition)` pair. Records outside the declared schedule are
returned as explicit exclusions. Missing dates fail in strict mode.

An OOS record can only receive `OUT_OF_SAMPLE`; it is never copied into
development or validation. This protects methodology-definition partitions
from future information. Assignments and exclusions are tuples and are sorted
by date and stable evidence identity, so the result does not depend on input
iteration order.

## Limitations

This module does not choose strategies, tune parameters, query storage, or
calculate returns. It validates the date/partition boundary only. A caller
must separately ensure that the evidence itself has canonical point-in-time
availability metadata and that any strategy implementation consumes only the
assigned development/validation records when defining methodology.
