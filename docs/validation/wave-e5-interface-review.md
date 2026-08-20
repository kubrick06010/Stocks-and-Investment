# Wave E5 adversarial interface review

The independent agent slot was unavailable during this closure attempt, so the
Program Lead executed the adversarial review directly. This is explicitly
recorded rather than represented as an agent result.

Attacks covered by `tests/integration/test_wave_e5_adversarial.py` and focused
tests:

- a later +500% outcome cannot change a T0 research view;
- post-hoc outcomes appear only when explicitly requested and remain separate;
- future watchlist entries/events are excluded from an earlier `as_of` view;
- mixed factor cohorts are reported incompatible, not averaged;
- read-only SQLite rejects inherited writes and preserves file bytes;
- provider/network fallback is blocked by a socket kill switch;
- stored control characters, ANSI/OSC sequences, HTML, dangerous Markdown
  schemes, mapping collisions, non-finite numbers and oversized output are
  handled by the safe renderer tests;
- terminal mutation/shell-escape commands never reach the service;
- query/render replay is deterministic and identity-keyed.

No HTTP server, browser, provider refresh, telemetry, or write endpoint exists
in E5 V1. The remaining HTTP/browser threat model is documented separately and
requires a future security gate.
