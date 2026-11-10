# #499 Phase 17 — bounded fault tests and adversarial source review

**Scope:** original adopted PR #474 only, local `zodex/499-adopt-pr474`
worktree. Phase 17 began at `57c4dc7a5886a0d5048f50079728e715105c1400`
(phase 16), reviewing the phase 15–16 source delta since `39852e62` and the
existing original M4 tests. This is **not** a new PR, a source freeze, a native
campaign, or authority to perform a Resolve Roll. No original project, receipt,
operator lock, prior one-use operation, or PR head/lease was rewritten.

## Bounded verification

- Initial fourteen-file focused Linux run: **460 passed**, no native host.
  Added three focused negative tests for a *consistently named* non-disposable
  project, a *different but unique* native item UID, and partially applied SDK
  track locks without implicit rollback/retry.
- Exact TypeScript held-source inference regression file
  `packages/contracts/test/qualification-output-proposals-v2.test.ts`:
  **30 passed**. The four original held-still source-in gates are unchanged.
- Source-mutated **13/13** original guard checks: operation/authority scope,
  exact UID/source geometry, frame 351, foreground bundle, expiry, actor SHA,
  held native owner, one-use replay, signed track locks, fresh-case effect
  allowlist, late SDK read, and setter readback. Every changed source byte was
  restored in `finally`; no mutated implementation was committed.
- **3/3** additional source mutations of the new effect argument allowlist
  (exact keys, non-V1 slot and true-only lock) detected by the new negative
  tests. Also mutated original `resolve_test_queue_reverse.py` to ignore
  `sourceMappings` equality; the added source-media drift case killed that
  mutant (**1/1**). Added an explicit foreign `mediaUid` regression.
- A complete bounded rerun after the review fix passed **471/471** Python
  tests, then targeted **97/97** after a test-only mypy annotation correction.
  Final extended fourteen-file suite, including two additional native-media
  guard cases: **473/473 PASSED**. Focused Ruff lint/format on four touched
  Python/test files, strict mypy on those four files, and `git diff --check`
  all **PASSED**. Logs reside in `.pipeline/499/phase17-*` (Conductor ticket,
  not the source-sealed original native case).

## Independent review and disposition

The CLI's two large **Claude Opus/high** diff reviews reached bounded timeouts
with **no verdict**. A compact Sonnet run with tools disabled initially
returned tool-call markup rather than a review; it is **not** counted. Two
subsequent independent, bounded **Claude Sonnet/low** source-diff reviews
returned results for all seven changed production modules in phases 15–16:

1. `resolve_gui_roll.py` and `resolve_test_queue_m4.py`: **NO FINDINGS**.
2. Remaining five source files: three findings. **Fixed** one legitimate
   defense-in-depth issue: `qualification_output_native_v2._private_effect`
   previously admitted any `Timeline.SetTrackLock` arguments under a synthetic
   constructor request. It now strictly allows only the exact keys
   `{kind,index,locked}`, original V2–V5/A1 slots, exact primitive types,
   and `locked is True`. Eight regression inputs failed *before* the fix,
   then passed; three guard mutants were killed.
3. **Rejected after reading full code:** suggested requirement that
   pre-setup `Deselect All` and `Roll > Start to Playhead` both already be
   enabled. The SDK requires *no whole clips selected*, so `Deselect All`
   may correctly be disabled; the fixed actor clicks it only if enabled.
   The named Roll command is explicitly checked for `enabled` **after** its
   deterministic V1/normal-mode setup and **before** the sole effect. A
   pre-setup enabled requirement would reject a legitimate harmless state,
   not prevent an unsafe dispatch.
4. **Rejected after reading full code:** claim that the JXA's `AXMain` check
   permits a nonfrontmost Resolve app. The *same observer invocation* first
   compares `NSWorkspace.frontmostApplication.processIdentifier` against the
   one installed Resolve PID and then requires the matching System Events
   process's `unixId` **and `proc.frontmost()`**, before inspecting one AXMain
   window. The actor repeats PID/bundle/window/frontmost/no-sheet checks.

This was review of the current **high-risk phase 15–16 source delta**, not a
fresh independent review of every historical line in the entire >10K-line
adopted PR. Phase 21 must independently review the **final exact source** again
after native acceptance and Conductor's source-pinned CI gate.

## Safety interpretation / freeze gate

No test assumes that a partial native `SetTrackLock` has been undone. The
partial-failure fixture retains the first actual mock lock; the subsequent
attempt fails before any new setter because a prior lock is present. The
original immutable native effects ledger and F1 `gui-intent.json` remain
single-use, fsynced **UNKNOWN/no-retry** boundaries. OS exit zero never
produces an M4 receipt; only the original independent SDK capture,
save/close/reopen, genuine MOV/PCM and strict reverse-verification chain can.

**Code is a candidate for the future freeze, not physically accepted.** The
successful one-use calibration was synthetic **moving H.264** only; original
M4 is **0/4**, strict #312 **NOT RUN**. The real held-still `sourceStart`
normalization, actual Mac menu/SDK targeting under Studio 21.1.1.10, internal
media/space feasibility while external storage is unplugged, and a distinct
**fresh case-specific Producer one-use authorization** remain unproven.
Phase 18 must test storage feasibility first. Phase 19 may freeze/rebind a
*new* source graph only after those requirements are met; any unknown stops
before a native effect. Do not reuse older source seals, journals or consent.

No `npm run validate:fast`, Linux #208/PID1/zombie suites, full CI or actual
Resolve execution were run in this phase, as explicitly directed. Historical
Linux local full-fast baseline at `bbe5c64b` was red (11 unrelated-domain
failures: 8/11 serially passed, 3/11 serially failed); prior CI success was at
an **older** source head and is not current-head green evidence. Phase 21 owns
broad validation, current required CI, exact-head independent review, and
Conductor-only original PR #474 verification/merge after *real* native success.
