# #499 phase 3 — original M4 edited SDK host, code-only

**Scope:** Adopted original draft PR #474, not a new PR or native campaign.
Original historical #473 targets/operation IDs, signed source-sealed pristine
evidence, and both old M4 campaigns remain untouched and ineligible for replay.
This phase did **not** operate Resolve, press a GUI menu, grant OS permissions,
reserve a new sacrificial target, render a real MOV, or assert native acceptance.

## Continuation implementation

`resolve_test_bench_edited_stage.py` is the strictly one-use bridge after the
pre-existing F1 GUI intent was consumed. It has no GUI executor. It reads only
the canonical original M4 journal and signed pristine capture, and verifies:

- Original one-use `edited` M4 stage still awaits its exact operation ID; stage
  0 has a genuine verified signed receipt, stages 2/3 have not started.
- The single fsynced F1 intent pins the initial project/timeline, original
  stage operation ID, source capture SHA, reviewed #495 AppleScript SHA,
  all eleven original item UIDs, M4 plan SHA, and original finite deadline.
- The source/currentness-bound original and newly prepared `edited` v2 output
  sessions refer to the exact same synthetic source package and profile.
- An independent SDK host follows the **edited** action sequence:
  `observe_edited`, `save_reopen` (native save, close, reload and re-query),
  `capture_pre`, `queue_render`, `start_render`, `poll_render`, `capture_post`.
  Every step uses the original signed, source-pinned native carrier; no
  AppleScript return value or client-provided geometry can become proof.
- Before creating any M4 receipt, the full existing `m4._verified_output`
  reauthenticates original native results, first-action timing after the M4
  intent, host effect lineage and *actual decoded MOV/PCM comparison*. Then
  `verify_supported_boundary` requires identical 11 original item IDs, source
  mappings, media, audio, links, six tracks and 1407-frame extent; only the
  adjoining two held-picture items may shift the **327 → 351** frame boundary
  with the supported source-in behavior.
- A second immutable M4 operation/deadline check occurs immediately before
  `runner._submit_original` writes one canonical `receipt-edited.json` and
  hands it to the original M4 verifier. Incomplete, unknown, invalid or
  mismatched host outputs cannot produce that receipt.

## Native owner invariant

The GUI caller releases its held owner descriptor before starting this
independent SDK continuation. The code briefly acquires the original shared
owner during its read-only evidence checkpoint, **releases it**, then delegates
native effects to `campaign.start`/`resolve_test_bench_carrier.start`.
This matters because the carrier's `preflight_selected_disposable` independently
acquires that lock before spawning each inherited-owner SDK worker. Holding the
GUI lock through carrier preflight would self-deadlock. It is explicitly
refused and covered by a regression test.

## Evidence limits

Only mock/injected host tests run in phase 3. Actual Studio 21.1.1.10
save/reopen, same-UID roll, post-render MOV/PCM and signed edited M4 receipt
are **not yet verified**. Phase 4 must integrate the full revised/rebuilt
chain and freeze all Python/contract/lock sources. Phase 5 requires new,
case-specific Producer authorization, entirely new sacrificial targets and
one new source-frozen real four-stage M4 trial before #473 or #312 can advance.

## Local verification

- Focused original M4/GUI/reverse/host suites and new edited host tests:
  **172 passed** (including 28 edited-host cases and owner-lock regression).
- `uv run --frozen mypy` on the edited module and its tests: **clean**.
- `uv run --frozen ruff check` on those files: **clean**.
- Data-integrity mutation: deliberately monkeypatched the 327→351 boundary
  verifier to accept everything in one isolated Python test process. The
  audio-tamper negative test then failed with `DID NOT RAISE`, proving the
  original verification guard is meaningfully asserted. Source was unchanged.
- `VITEST_MAX_WORKERS=1 npm run validate:fast` **FAILED (exit 1)** after
  660.992s: contracts, TypeScript lint/types/tests, Python Ruff and full-tree
  mypy all passed; Python fast tests had **3264 passed, 43 skipped, 22 failed**
  in existing #182 campaign, narration, word timing and #208 target-identity
  clusters. These overlap failures reported in phases 1–2, but an isolated
  `origin/main` comparison was not performed in this phase; do not claim all
  22 failures are independently proved baseline. Full log retained in
  `.pipeline/499/phase3-validate-fast.log`; session exit recorded in
  `.pipeline/499/command-session.json`.

The full 4/4 native M4 proof, independent review and CI are not claimed.
