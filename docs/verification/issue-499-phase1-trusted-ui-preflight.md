# #499 phase 1 — read-only trusted UI/SDK preflight

Scope: adopted original draft PR #474 at `daec386bdccd243402dc3d358dbd19b783d1a318`.
No new project, source seal, operation, M4 receipt, GUI interaction, permission
change, or native effect was created. The original pristine 1/4 campaign remains
source-incompatible with changed Python code and MUST NOT be reused or resealed.

The new `resolve_test_bench_ui_readiness.py` has a production factory
`prepare_owned_ui_readiness(store, job_id, resolve)` which requires the shared
native owner and calls `prepare_owned_f1_inputs` to reauthenticate the original
signed pristine M4 capture, actual eleven-item SDK inventory, 327 playhead and
approved Studio SDK version. There is no parameter for a caller to supply OS
`TrustedUiReadiness` booleans. A fixed, read-only `/usr/bin/osascript` JXA
observer samples the running `NSWorkspace` process count/PID/bundle path,
frontmost PID and installed bundle build, then checks existing Accessibility
trust and nonprompting AppleEvents Automation permission **before** reading
`System Events`. It reads the one exact window, its focus and modal state,
named Edit/roll/nudge menus, and V1/A1–A5 targeting. Missing or ambiguous
attributes and all unexpected evidence fields fail closed. It makes no AX
write, keyboard event, menu click, window activation or TCC change.
Production `SystemEventsRollExecutor` calls in `attempt_once` also require
one consumed in-process attestation of the **same** OS/SDK objects from this
factory, issued within five monotonic seconds and still under the native owner;
simply constructing a green readiness dataclass is insufficient. Injected fake
executors remain testable without any actual macOS dispatch.

**Deliberate safety stop:** Resolve's active keyboard mapping cannot be
authenticated merely by knowing the installed default shortcut list or a
past operator observation. The read-only OS observer currently returns `null`
for `keyboardPreset`, `keyboardFocus`, and `keyboardNudge`. The strict validator
rejects these values. No method infers `DaVinci Resolve`/`Command-4`/`.` as
observed facts. Thus **a live Mac dispatch is not yet enabled** by this probe.
Before Phase 2's actual actuator can be reachable, a Mac-tested, independently
readable *active* keyboard-map source must supply all three values, and the
AX observations must be checked against Studio 21.1.1.10 for supported
property names. Existing #495 fixed script hash
`306aa13e1917d58f7006e65c12c105b0bfe4eff8cf912638fc4de4d5832c4de4`
is not modified. Keep unknown permissions/map/track state fail-closed.

The source and OS observer were compiled and exercised with Linux-side injected
fake OS/SDK tests only; the sandbox is Linux, so there is no claim of a real
macOS AX/Automation/keyboard-map acceptance test. Future Mac inspection must
be **read-only** and only on a new eligible, source-pinned target, without
changing the old pristine session or its signed evidence. Phase 2 remains
code-only and must bind this factory to the *original* authorized M4 journal
before any one-use dispatch; no public dataclass supplied by a caller is
sufficient native authority.

## Phase-1 verification (Linux Zodex, not native Mac acceptance)

- `uv run --frozen pytest -q tests/test_resolve_gui_roll.py tests/test_resolve_test_bench_gui_stage.py tests/test_resolve_test_bench_ui_readiness.py`: **161 passed**.
- Scoped Ruff check and format check on all three edited Python paths: **pass**.
- Scoped strict mypy on those three paths: **pass**.
- Reversible critical-guard mutations: disabling the production-executor
  attestation check broke its forged-readiness rejection test; disabling
  frontmost-PID matching broke the mismatched-PID rejection. Source restored.
- `VITEST_MAX_WORKERS=1 npm run validate:fast` (Node 24.19.0,
  npm 11.17.0): **overall FAILED**, after 618.742s. Contracts, TS lint,
  TS types, TS workspace tests, Python Ruff, Python mypy all passed. The
  Python fast stage had **3,221 passed, 43 skipped, 23 failed**. Failures are
  confined to unrelated tests in `test_issue208_*` (clock/identity and
  capability receipt guards), `test_narration_cli`, `test_word_timing_package`,
  and `test_issue182_campaign`; no readiness, GUI-stage, or GUI-roll test
  failed. Earlier original PR evidence also documented these classes of Linux
  timing/media failures; this run did **not** independently compare origin/main
  and must not claim a green full gate.
- `git diff --check`: pass. No native/GUI interaction was executed; no Mac
  permissions were requested or changed.
