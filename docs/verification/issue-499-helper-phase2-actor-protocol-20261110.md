# #499 — VERA GUI helper actor/protocol Phase 2 verification

**Scope:** Conductor phase **21/31**, helper-document phase **2/12**. Code and simulated tests **only**. Adopted, existing original PR **#474**, branch `zodex/499-adopt-pr474`. Historic phases 1–19 and original signed/UNKNOWN/consumed case roots are excluded from every new submission. This document is evidence, **not a native test receipt or authorization**.

## Required plan and retained identities

- The entire unchanged `.pipeline/499/issue-499-vera-helper-completion.md` was inspected before work. SHA-256: `816b5dd17611d5b8198a453ce6fe687d12c201f2438a2d6d88ed6a8e5617be18` (25,572 bytes).
- Preserve fixture identity `synthetic-312`; fresh trial identity belongs in the new job/operation/request names, **not** in the fixture identifier.
- Preserve the standing Producer instruction by *attribution*: `authorizationBasis=standing-producer-instruction`, `authorityIssuedBy=VERA Conductor`, plus the original approval reference/instruction. It is **not** a forged Producer signature.
- Full-loop authority `vera.test-bench-473-case-specific-authority/v2`, full-loop intent `vera.test-bench-473-complete-loop/v2`, GUI intent `vera.issue473-one-use-f1-gui/v2` reject their old v1 counterparts. Every consumer migrates together: admission, page, GUI journal, edited/native continuation, M4 runner, and old production executor.
- Legacy `scriptSha256` remains only in *historical read-only* #499 calibration/evidence scripts and unrelated manuscript/#326 script-signing paths; none can authorize a new Test Bench M4 GUI case. Historical calibration code/evidence is unchanged.

## Versioned contract and source pins

- Actor `vera.gui-helper-actor/v1`, source `vera.gui-helper-source/v1`, request `vera.gui-helper-request/v1`, reply `vera.gui-helper-reply/v1`; bundle identifier `org.vera.resolve-test-bench.gui`, hidden Agent app (`LSUIElement=true`). Helper source in `macos/vera-gui-helper/`, signed build/install belongs to Phase 3.
- Source manifest SHA-256: `630477c0e7059ec0db7a8014513e0b3ffe3146e4a977550036eb0c36aafad542`; exactly four current source/build/bundle/LaunchAgent inputs, recomputed and verified from actual source bytes. Never hash a manifest into itself.
- Expanded VERA proof-source graph (250 inputs), candidate SHA-256 at this phase: `325c10fd16b052e8d9bc3db0013b7a0f8e25259c3a5fe734ac3b5644635842ce`. **Candidate for this code revision only**, not authority for an old/native case; all earlier frozen graphs are obsolete for a *new* build.
- Executable pin contract requires the **actual** installed `.app/Contents/MacOS/VERAGUIHelper` absolute path, file SHA-256, macOS CodeDirectory CDHash, 10-character team identifier, exact bundle identifier, and designated requirement. Read-only `/usr/bin/codesign --verify --strict`, `-dv`, `-dr` and pre/post executable SHA checks fail closed; helper-reply PID is checked against the real process path. The installed binary does **not exist at this phase**; no real CDHash, team, or installed-binary SHA was invented or approved. The synthetic unit-test pin uses explicit test-only dummy values.

## Client safety and phase boundaries

- Canonical, closed, bounded request/reply JSON with duplicate-field refusal, UTC expiration within 120 seconds, fixed `M4.edited.roll-start-to-playhead` operation, known synthetic fixture, precise job/edited operation/trial/request ID, Resolve PID, exact window/project/timeline, source graph, actor manifest/binary pin, pristine capture, immutable one-use intent and standing-authority digests.
- The caller must supply the entire same-case `OWNER_KEYS` map (including actor pin, PID, request ID and short deadline); *any* altered field refuses publication. Production publish has **no caller-supplied signing-verifier override**; reply consumption has **no caller-supplied PID-verifier override**.
- Private owner-only spool, no-follow reads, exclusive/fsynced once-only publication. Alias/symlink, duplicate request/replay and mismatched/spoofed reply are refused. Reply `ready`, `refused` or `dispatched-unknown` **never** counts as native verification.
- A new case actor pin is sealed once in `f1-gui-edit/actor-authority.json`, bound to original job and plan digest, before any edited request. Post-Roll native edited admission compares **the same** actor identity, including installed binary pin. Legacy AppleScript authority is denied; the old System Events executor unconditionally refuses GUI execution and cannot launch `osascript` under the new pin.
- The Swift app and build script are intentionally fail-closed *non-operational placeholders*: this phase does not build, sign, launch, grant permissions to, focus, click, or invoke Resolve. The follow-up phase implements and qualifies the real GUI app.

## Simulated verification

- `uv run --frozen pytest -q -n 4 tests/test_resolve_gui_helper_protocol.py tests/test_resolve_gui_roll.py tests/test_resolve_test_bench_full_loop.py tests/test_resolve_test_bench_edited_stage.py tests/test_resolve_test_bench_page_stage.py tests/test_resolve_test_bench_m4_runner.py tests/test_resolve_test_bench_gui_stage.py tests/test_resolve_test_bench_ui_readiness.py --tb=short`: **422 passed**; no real GUI/SDK native action.
- Request/response rejection cases include malformed/noncanonical/duplicate/extra fields; invalid operations; expired or excessive deadline; altered source or actor/binary authority; wrong job/stage/request/PID/trial/window/project/timeline/fixture; altered pristine/one-use/authority SHA; spoofed helper PID, unsigned or changed codesign, source/hash drift, symlinks/aliases/replay; pre- and post-Roll actor equality and legacy journal/schema refusal.
- `uv run --frozen mypy python tests`: **412 files**, no issues.
- `uv run --frozen ruff check .` and `uv run --frozen ruff format --check .`: PASS, **1,102 files formatted**. Two **byte-unchanged historical** #499 calibration/replan evidence scripts are excluded from Ruff to prevent automatic rewriting of spent-case history. They remain tracked unchanged; historical file Git blob hashes are `b30ea94e687caab2394d77ebf3e8df4a69d5dc96` and `2c34956b4c507a3bd28cd2359e59b71e35ddb420`.
- `git diff --check` and import/compile checks: PASS.
- Full `VITEST_MAX_WORKERS=1 npm run validate:fast` **EXIT 1 / RED** (ticket `.pipeline/499/phase21-validate-fast-final.log`): contracts PASS, TS lint PASS, TS types PASS, TS tests PASS, Python Ruff lint/format PASS, Python mypy PASS; Python fast pytest **3,598 passed, 43 skipped, 30 failed**. Failures: #208 gate coverage (5), #208 review fixes (12), #208 target identity (8), #182 campaign (1), narration CLI (2), word timing (2). These selectors have **no phase-21 helper tests**; source and test files for these failing areas were unchanged by this phase. They are a **separate existing repo-wide blocker**, not a green full gate. The older interrupted first full-gate run stopped at historical calibration-script Ruff failures (recorded in `.pipeline/499/phase21-validate-fast.log`); this was addressed by exclusion of **byte-unchanged** historic #499 one-shot calibration/replan scripts, not by rewriting them.
- Phase-21 local acceptance is specifically the closed protocol/pin tests and zero native effects. Later Phase 8 and CI delivery gates must still be green; this evidence does not waive them.

## PASS boundary and next action

**Phase 2** is code-only: PASS requires all helper protocol/pin tests, consistent new actor identity and legacy-authority rejection, and no native action. It does **not** qualify the macOS signed binary or native Roll. Follow with phase 3/12 (Conductor phase 22/31): build/sign and install the dedicated Mac Aqua-session GUI helper and qualify its own persistent, fully observed identity with **no edit action**. The future actual installed binary and source hashes must be bound to a fresh, independent case authority before any native request; no old/UNKNOWN journal can be replayed.
