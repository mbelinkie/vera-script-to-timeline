# FAST-R1 failed evidence and bounded correction

Candidate7c578db13bd42b85bd599120c2ecee258579f2e8; sourceUnchangedtrue.
Command: `npm run validate:fast` with pinned Node/npm/uv/Python.
Durable start2026-10-13T06:27:57.857212Z, exit1 at06:30:04.302628Z.
Log SHA25640164a903b846c6bed5afa78a72a7218affc21866e960c1e38c1b22f4bbb9fbd.
Original source snapshots, start/exit and log retained at `out/issue177/fast-r1`.
This run is failed, not full or fast passing evidence.

Generated currentness and TypeScript lint/types completed before Vitest failure.
Contract Vitest426passed3failed (20files:18passed2failed); tooling-smoke1passed.
Failures are unchanged #144 CLI tests: proof-cli deterministic replay and
omission-bridge transformation/finalization. Every failure reports the existing
5000ms timeout; no assertion mismatch was reported. The parallel file runs
consumed83.70s import time and129.43s test time over38.34s wall time.
No #177 source, frozen test, timeout or gate config changed.

Bounded execution correction: rerun fast validation with VITEST_MAX_WORKERS=1,
the standing accepted full-validation worker setting. Installed Vitest4.1.11
actually honors this variable in
node_modules/vitest/dist/chunks/coverage.DM_a_rWm.js:380, setting maxWorkers.
This reduces host contention while preserving every test, assertion and timeout.
Python fast testing retains its accepted2workers. Actual process inspection
found no competing validation/media run (only unrelated idle Claude spares).
This is a changed execution profile, not an unchanged retry until green.
If it still fails, diagnose the specific result rather than weakening a gate.
