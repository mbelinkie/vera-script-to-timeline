# Implementation checkpoint — not qualification or acceptance

Source prerequisite `72aac8a` adopts only approved #204/#207 inputs onto accepted
main `017e7cf`; its byte pins and #192 disjointness are retained in
`source-adoption.json`. Implementation is confined to the owned identity,
dispatch/bootstrap/inventory and receipt-backed capability seams.

Incremental synthetic checks before the latest clock-lineage addition:
23 parser/path/time tests passed; expanded identity coverage passed 40 tests;
receipt consumption/current-UID coverage passed 57 tests in 41.99 seconds;
23 additional bootstrap/concurrency/crash/path cases passed in 12.42 seconds;
five descriptor/alias/expiry cases passed in 1.22 seconds. These are iteration
results, not claimed equivalent final evidence after subsequent source changes.
The next pinned combined run covers the whole new file and unchanged connected
#204/#177/#109 release/bootstrap and ordinary-v2 regressions without media work.

Retained test-first failure: module absent, collection exit 2 in 0.21 seconds.
The first expanded run had 38 passing and two failing tests: separate clock
sampling falsely reported rollback before the intended target/drift boundary.
Bracketing monotonic samples corrected the production logic; assertions and
required refusal reasons were preserved. Failed scrubbed logs and lint/type
iteration failures are indexed under `iterations/index.json`.

Frozen environment setup completed: uv 0.12.5, CPython 3.12.14, Node 24.19.0,
npm 11.17.0, macOS 15.1 Intel. `uv sync --frozen` exited 0; pinned
`npm ci --ignore-scripts` exited 0 (148 installed/152 audited). No manifests,
lockfiles or accepted tests changed. Focused lint and strict types passed after
the last test-seam correction; complete fast/review evidence remains pending.

No app has been launched, plugin installed, real getter called, authority issued
on the operator's behalf, target chosen/saved/created, provider called or full
gate run. Actual installed identity and #204 capability evidence, runtime
fix/delta review and final full evidence remain held. Fake success and CLI
exit zero do not supply External acceptance. The operator checklist is a draft
until exact reviewed source/release pins and the coordinator grant are supplied.
