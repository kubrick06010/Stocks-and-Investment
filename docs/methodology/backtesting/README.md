# Backtesting foundation

The first simulator is deliberately low-frequency and cross-sectional. It
accepts scores already evaluated against a `PointInTimeDataView`; it never
queries latest fundamentals. Universe snapshots are dated/versioned and any
survivorship limitation remains visible in the result. Transaction costs are
explicit fractions applied at formation.
