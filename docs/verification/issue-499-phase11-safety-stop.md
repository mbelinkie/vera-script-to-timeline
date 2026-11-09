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
- The current fixed PID-bound menu-only actor SHA
  `9469ed9b14a290663381395a5c857330c0ebc85c20e9cfbaa777ca3eba352ed5`
  and every unproven pre-effect focus/mode/track guard are **unchanged**.
  No proposed v2 actor replaces them: adding unobserved set-state clicks
  would consume an irreversible intent without proof of the selection.
  No unproven Qt field has been set to true or deleted merely because
  a post-edit check might notice damage.

## Tests and required stop

The focused injected suite, Ruff/mypy, full fast gate, one independent
Claude review and five actual reversible guard mutations are recorded
in `.pipeline/499/phase11-*.log` and `progress.md`. Five deliberate
safety mutations (SDK Edit page, boundary links, other cuts, SDK double
read, frontmost PID) each caused targeted tests to fail; original bytes
were restored. These tests do not establish Mac actuator behavior.

**Status: BLOCKED for production actor v2.** Do not freeze a new approval
graph, bind a new Producer authorization, checkpoint as production-ready,
or advance to phase 12/13 on the strength of these code-only checks.
The existing source-freeze manifest at 7ba02962 is obsolete after code
changes; script SHA has *not* been re-pinned because the actor is unchanged.
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
