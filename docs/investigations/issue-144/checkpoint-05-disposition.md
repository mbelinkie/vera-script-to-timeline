# Checkpoint 5 disposition

Authenticated Claude CLI2.1.289 completed 19 read-only turns on configured
`claude-sonnet-5`/high, with no permission denials. Full response is retained
in `claude-checkpoint-05-verbatim.md`. This is independent static review, not
test execution or acceptance.

| Finding | Disposition |
| --- | --- |
| Replay trusts SQLite stage path before #35 integrity check | Fixed. Run the unchanged store's completed-artifact verifier before custom reconciliation, and derive each replay path through its canonical path method. A new corrupted-path test was red, then passes without invoking the fresh inspector or another native creation. |
| Full manifest event fields cannot be read from a native clip | Narrowed the injected inspector to source path/hash, track kind/index and record/source ranges, plus native UIDs, enabled state and speed. A unique pristine package/path/geometry candidate establishes the sidecar event binding. No authoring ID, provenance, alignment version or precision is claimed as a native property. The fake now emits only those measured fields. Ambiguous candidates refuse; later UIDs must match the immutable first map. |
| UID-returning calls unverified in #34 adapter | The #34 adapter does not use them, but #141's accepted WI collector and retained native captures do. `retained-uid-evidence.json` extracts one project/timeline/item/media UID set after verifying the compressed and decoded published hashes against the publication manifest. #141 report lines416–417 and probe's `observe`/`item_evidence` document the boundary. No accepted adapter/preflight modification is needed or authorized. New WI capture must still check every required callable/result and qualify its current target/build in #145. |
| Cosmetic non-verified result replay | Deferred: it already waits with no duplicate effect. No extra implementation needed. |
| Intent/crash/parser guarantees | Independent code trace found no duplicate-effect or false-complete path. Retain uncertainty waits and exclusive/fsynced intent. |

Verification: the first correction run accidentally used default Node26 and
refused at runtime preflight. Re-run with pinned Node24.19.0 exposed five expected
failures from the narrowed inspector. After that correction, the isolated
corrupted-path test remained red; the path fix made all **27** focused prepared/
native cases pass. Command:
`npm exec --yes --package=node@24.19.0 -- uv run --frozen pytest tests/test_issue144_native_build.py tests/test_issue144_prepared_build.py -q --tb=short`,
wrapped by `ctx-wire run rtk proxy`. No accepted test/source changed.

Full `npm run validate` passed on prior pinned `97e9f9d`: generated contracts,
TypeScript lint/typecheck and 152 contract tests; tooling1, progress6, roadmap23;
Python Ruff, strict mypy and **218 pytest cases**. The corrections above require
updated full validation before final handoff. No native Resolve action, positive
omission rebuild or baseline promotion occurred.

Next bounded segment: compiler-backed visual range proposals and explicit local
accept/reject decisions, including fresh canonical revision/build IDs. Retain
normal-speed linked +25 move and -25 end trim, unchanged source bounds for moves,
exact compiler reproduction for trims, unique normalized token candidates and
clearance on video/source-audio tracks. Synthetic inputs remain labeled honestly.
The pending narration route/wording choice still gates omission rebuild.
