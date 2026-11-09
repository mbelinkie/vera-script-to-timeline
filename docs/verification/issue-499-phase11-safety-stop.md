# #499 phase 11/14 — actual Qt evidence and pre-effect safety stop

**2026-11-09 | original adopted PR #474 | CODE ONLY.** No real Resolve
edit, project/page mutation, one-use GUI intent, TCC change, source reseal,
receipt, MOV/PCM, strict #312 acceptance or merge was attempted.

## Independently observed, versus not proven

The source is the unchanged phase-10 native census at
`.pipeline/499/phase10-summary.md` (and its JSON artifacts), not injected
test booleans. Real Studio 21.1.1.10 PID/bundle/version, Accessibility/TCC,
frontmost PID, one main window, `AXMain=true`, no sheet, and no-prompt
Automation were measurable. The SDK's actual page was **Deliver**, not an
authorized new disposable Edit target. Qt returned `AXFocused=false`;
`AXFocusedUIElement` was a generic group, and Edit/Normal-mode/Auto-Select
marks and menu accelerator characters were missing. The matching
`AXFocusedWindow` *name* did not prove AX object identity. Roll/Nudge
availability on a newly selected Edit page is not measured.

The historical signed pristine geometry (11 actual UIDs, six tracks
constituted as V1–V5 plus A1, not V1 plus A1–A5) has exactly one
Root/V1 cut at 327 and **no linked left/right item UIDs**. This old
geometry is only a test oracle; it is neither fresh consent nor a new target.
No UI evidence establishes that a menu Roll would affect only this cut on
a **new** instance. In particular, `AXMain` plus OS frontmost and a
post-effect verifier do not independently prove timeline focus, Normal
Edit Mode, V1 Auto Select or linked-edit selection before the first click.

## Accepted code-only safety improvements

- `prepare_owned_f1_inputs` now requires official
  `GetCurrentPage()=="edit"` on both sides of the existing SDK → OS → SDK
  bracket. The SDK already authenticates the same new project/timeline,
  version, eleven UIDs, six tracks, playhead 327, owner and signed pristine
  capture. A missing or drifting page cannot reach the one-use journal.
- `_verify_original_capture` now rejects *fresh* signed pristine
  geometry if any third item begins or ends at 327 or either V1 boundary
  item lacks an explicit empty `linkedItemUids` list. It makes no
  blanket UI auto-selection claim, and keeps the original exact V1
  and UID checks and independent post-edit `verify_supported_boundary`,
  SDK save/reopen, source/media/link, rendered MOV and decoded PCM obligations.
- The fixed PID-bound menu-only actor was reviewed and its six Auto Select
  targets were corrected to match the signed V1–V5/A1 topology; the newly
  pinned script SHA is
  `0ad776430984f35b816c481bd0319e3fd620cb03a603a4253b2df0abd1c6a8fb`.
  The OS observer checks this same topology, and fresh signed tracks must
  match it. Real OS dispatch now requires original owner-attested SDK→OS→SDK
  provenance even through alternate callers/wrapped executors, and SDK
  project/timeline UIDs, page, playhead=327 and deadline are rechecked
  immediately before launch. Late drift after fsync stays UNKNOWN/no replay.
- Every unproven pre-effect focus/mode/track-selection guard remains
  **unchanged**. A code-level revision does **not** make this actor safe for
  the actual Qt application: adding unobserved set-state clicks would
  consume an irreversible intent without proof of resulting selection.
  No unproven Qt field has been set to true or deleted merely because
  a post-edit check might notice damage.

## Tests and required stop

The focused injected suite, Ruff/mypy, full fast gate, one independent
Claude review and five actual reversible guard mutations are recorded
in `.pipeline/499/phase11-*.log` and `progress.md`. Five deliberate
safety mutations (SDK Edit page, boundary links, other cuts, SDK double
read, frontmost PID) each caused targeted tests to fail; original bytes
were restored. These tests do not establish Mac actuator behavior.

One independent Claude Opus review identified **three actual defects**:
direct/wrapped real-executor bypass of the authenticated owner, wrong
V1–V5/A1 six-track Auto Select enumeration, and a late SDK page/playhead
race. All three were repaired and new regressions added for exact actor
provenance, wrong signed topology and post-journal SDK drift. No Mac-native
test has compiled or executed the revised fixed AppleScript; its SHA only
identifies those changed reviewed bytes.

**Status: BLOCKED for production actor v2.** Do not freeze a new approval
graph, bind a new Producer authorization, checkpoint as production-ready,
or advance to phase 12/13 on the strength of these code-only checks.
The existing source-freeze manifest at 7ba02962 is obsolete after code
changes; a newly pinned script SHA is **not** a newly authorized campaign
or reviewed native implementation freeze.
Fresh M4 remains 0/4; #473 → #312 PR #323 → #313 remain blocked.

### One-case human-operated contingency (not auto-authorized)

If the Producer separately chooses the #477 option-3 fallback, an editor
may perform **one** visually verified 327→351 roll **only** on a newly
authorized, newly provisioned sacrificial Studio 21.1.1.10 project.
That is a **different, explicitly approved human-operation protocol**,
not a way to bypass the existing one-use automation journal or reuse an
old M4 operation. Before any action it must establish fresh signed
target/UID/six-track geometry, safe visible Edit/timeline/Normal-mode/V1
selection and no linked item risk, with an independent observer and owner;
after action it must record the single operation, SDK save/close/reopen,
exact geometry/source/media/links, and real rendered MOV/PCM. UNKNOWN,
partial, expired, or missing independent proof stops without retry or
claiming a receipt. The current automated runner does **not** implement or
authorize this protocol; no human action is requested by this phase.

## Final phase-11 code-only verification

- **436/436** broad injected Resolve/Test Bench, M4, page, GUI, edited/revision and full-loop tests passed after the review repairs. No live macOS/Resolve session was exercised.
- Repository Python Ruff lint and formatting passed; strict mypy passed all **405** checked source files.
- All **five** reversible safety mutations were detected again after the review fixes and the source was restored byte-for-byte (SDK Edit page last-moment check; linked V1 boundary; competing frame-327 cut; second SDK inventory pass; OS frontmost PID). The late SDK regression also tests project UID and frame-327 playhead drift after the one-use journal fsync, with no subprocess dispatch and no retry.
- One independent Claude Opus review (phase11-claude-review.log) reported exactly three actionable issues; fixes and focused negatives are in the final code. No second independent review of the fix commit is claimed.
- `VITEST_MAX_WORKERS=1 npm run validate:fast` was **RED** on a single **5-second timeout** in the unchanged `@vera/contracts` `qualification-output-proposals-v2.test.ts` (#215); all 1,245 other contracts tests passed, plus contract generation, TypeScript lint and types and the other executed workspaces. The failed test's git blob `374126dab54f357c260599d83e0567b4560b7a30` is identical at current HEAD, phase-10 frozen 7ba02962 and origin/main. Running the complete test file alone at the same checkout passed **30/30**, including the timed-out test in 1.526 seconds. The full gate exited **1** at TypeScript tests; its Python phase was **not reached**. This is not a green full-gate claim or a complete contemporary main-baseline reproduction.
- Native M4 remains **0/4**, and no distinct new sacrificial project, signed native receipts, strict #312 verification or tested real-Mac actor-v2 readiness exists. The source-script SHA is updated but this is **not** a current-head CI/authorized proof freeze.
