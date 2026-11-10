# #499 helper plan Phase 5/12 — production System Events seam migration

**Conductor phase:** 24/31. **Adopted PR:** original #474 only, branch `zodex/499-adopt-pr474`. **Effect scope:** Python/Swift-source integration and simulated tests only. No real Resolve GUI effects, M4 operations, new target/project, signed receipt or prior-case replay occurred.

## Frozen instructions and recovery

Read the entire unchanged `.pipeline/499/issue-499-vera-helper-completion.md` before implementation and verified its exact SHA-256 `816b5dd17611d5b8198a453ce6fe687d12c201f2438a2d6d88ed6a8e5617be18`. Work continued from completed Phase 23 (`03ac97bc`) and the other recovery thread's shared-worktree `wip: recovered` commit (`4e9f5079`), **not** from `origin/main`. Concurrent edits were halted and reconciled without discarding the recovered changes. No parallel second owner or native action is permitted.

## Four qualified production seams

1. **Roll executor:** `resolve_test_bench_helper_stage.HelperRollExecutor` validates the case-bound actor, immutable authority, journal's one-use digest, original job/operation, exact SDK UID/window/PID and installed helper identity. It publishes one canonical `roll` request through `SignedHelperDesktop` and interprets the OS result only as dispatched/uncertain; independent native verification is still required. The obsolete `SystemEventsRollExecutor` rejects helper-authorized execution and no longer has a reachable `subprocess.run` backend.
2. **Foreground activation:** `SignedHelperDesktop.focus` requests exact PID/window focus from the signed direct-Aqua LaunchAgent; it checks the helper's actual executable process, self-reported Accessibility readiness, bounded freshness, canonical response, matching request digest and exact target.
3. **Read-only UI/menu observation:** the same signed helper's independent `inspect` operation validates frontmost/main window, no modal/sheet, enabled Roll menu and process identity. The owning host rechecks the original SDK target before and after observation. The qualified path does not query System Events.
4. **Dedicated Mac runner probe:** `SignedHelperDesktop.resolve_pid` uses the macOS `libproc` process census with exact executable identity, refusing absent/multiple matches; helper readiness is obtained from the actual signed GUI helper process, not Python's Automation TCC or a desktop AppleScript probe.

The main full-loop entrypoint is now **pristine receipt verified → independently prepared/authenticated edited session → helper Accessibility readiness → owner-held Edit page → playhead 351 → revalidate pre-GUI session → signed focus/menu recheck → one consumed-journal Roll request → bounded SDK-only geometry settle under the same native lock → exact same-session reauthentication → independent edited host**. The helper path has no Automation TCC or keyboard-map gate because it sends no AppleEvents/keystrokes. Legacy System Events/JXA source remains elsewhere for historical standalone probes but is not executed by the qualified M4 path. No fallback to `osascript`/System Events/Hammerspoon is possible on a qualified dispatch failure.

The settled-geometry observer rejects new/missing/duplicate item UIDs, moved clips, wrong track state, wrong project/timeline identity, and unexpected 327→351 item geometry. It never issues a second Roll. An apparently settled edit is **not** an M4 receipt: the separate saved/reopened native host and rendered PCM verifier remain mandatory.

## Negative and end-to-end simulated evidence

- Failures in edited-session preparation or helper admission refuse before Edit page, playhead, or Roll; tampered, symlink-parent, hardlinked, alias and drifted session records cannot authorize Roll.
- In the integrated fake M4 loop, the stage ordering, single owner, one-use dispatch, zero legacy subprocess fallbacks, post-dispatch mismatch, missing/wrong geometry and all later stage interruptions fail closed.
- Fixed Phase-3 regression scope: Phase-4 intentionally added `AXPress` to the *separate one-use Roll actuator*. The prior Phase-3 test globally forbade this source token; it now verifies only the focus/inspection entrypoint remains unable to press a menu, while the Roll actuator remains separately tested.
- **Focused Python:** 135 passed, `.pipeline/499/phase24-after-reconcile-focused.log`.
- **Broader M4 GUI/Test Bench regression:** 687 passed, `.pipeline/499/phase24-broad-final.log`.
- **Ruff:** 8 edited files passed check and format check. **mypy:** 8 source/test files passed, `.pipeline/499/phase24-reconciled-mypy.log`. **git diff --check:** passed.
- A prior exploratory `VITEST_MAX_WORKERS=1 npm run validate:fast` did **not** pass: 13 failures, 3,662 passed and 43 skipped, `.pipeline/499/phase24-validate-fast-final.log`; one failure was the stale Phase-3 assertion corrected above and proved green in the broader suite. The others include older #208, #182, narration, word-timing and #276 tests and were **not** retested in a full repository gate. This red gate is reported, not called green. The helper plan requires the full fast gate in document Phase 8 (Conductor phase27), not this Phase 5.

## Decision and next scope

**Phase 5 explicit criteria PASS on code/simulation evidence only.** Exactly four qualified seams use the helper and required ordering/failure tests pass. This does **not** establish live Roll, 4/4 M4, strict #312, fresh signed helper binary or long-wait/reboot proof. Previous UNKNOWN/native roots, actors, authority, seals and receipts remain ineligible for reuse. No push/merge or independent Conductor advancement by this phase agent.

**Next:** Conductor phase25/31, document Phase 6/12: full four-stage synthetic orchestration, Conductor immutable launch/authority/runner tests, independent code review before live effects, freeze a new helper build, and exactly one *no-edit* launch/focus rehearsal. Do not begin native Roll until a later expressly authorized phase.
