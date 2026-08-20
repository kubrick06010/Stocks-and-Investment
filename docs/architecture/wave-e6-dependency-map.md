# Wave E6 dependency map

E6 depends on the frozen domain report and the read-only interactive service.
It may depend on renderable structured reports, but it must not depend on
providers, HTTP clients, storage writes, current-data lookups, or strategy
implementations.

The CLI is an edge adapter. The narrative renderer remains independently
testable and deterministic.
