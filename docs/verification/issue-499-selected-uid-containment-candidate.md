# #499 — SDK-backed selection containment candidate, not native acceptance

**Status (2026-11-09): CODE ONLY / NATIVE ROLL STILL BLOCKED.** This is a
bounded alternative investigated on the *original adopted PR #474 branch*;
there is no new PR, producer-project navigation, source-bound native consent,
one-use journal consumption, GUI action, or M4 receipt.

## Why this candidate exists

The real Studio 21.1.1.10 Qt app reports `AXFocused=false` and omits the AX
menu marks for selected Normal Edit Mode and track Auto Select. Phase 10's
actual Mac observer therefore cannot truthfully assert the production
pre-effect `timelineFocused`, `normalEditMode` or `v1Only` booleans. Phase 11
intentionally preserved those fail-closed requirements.

The **installed 21.1.1.10 SDK** was checked independently on the physical
Mac at `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/DaVinciResolveScript.pyi`:
`Timeline.GetSelectedClips()` (line 2204),
`Timeline.SetTrackLock(...)` (2258), and
`Timeline.GetIsTrackLocked(...)` (2261) all exist. Method presence alone
does not establish live selection behavior or edit safety.

Issue #141's prior real-Resolve investigations demonstrated that locking
other tracks does **not** by itself exclude them from selection. The prior
editorial protocol first configured Auto Select explicitly, then required
exact SDK `GetSelectedClips()` native UIDs *after* selection and *before*
irreversible edits. See
`docs/investigations/issue-141/second-opinion-handoff.md` and
`docs/investigations/issue-141/editorial-macro-plan.md`. Those findings
involved clip selection and blade/trim commands, **not** a proven menu Roll
edit-point selection on our new V1 327 boundary.

## Implemented read-only candidate probe

`resolve_test_bench_selection_probe.inspect_selected_boundary` checks,
under the already-held native owner: exact synthetic project/timeline UIDs
and names, SDK Edit page and no rendering, signed 11 UID / exact V1–V5+A1
track topology, physical V1 unlocked plus all other five tracks locked,
SDK playhead frame 327, and `GetSelectedClips()` returning **exactly the
two original signed V1 boundary UIDs and nothing else**. It rereads the
SDK project, timeline, page, and playhead afterward to reject drift.
Missing locks, extra selections, a different item, a non-list/empty result,
unknown API response, or a different project *refuse*. The helper has **no
SDK setter, GUI command, journal or native operation**. Its caller must
first authenticate the pristine signed geometry and new case authority;
passing caller-controlled objects cannot mint native evidence.

This probe is **not wired into the production F1 dispatch**. It is a
candidate instrument for a future separately approved, selection-only
experiment on a **fresh disposable project**. Crucially, Resolve may select
an *edit point* without having its two adjacent clips appear in
`GetSelectedClips()`. If that happens, this candidate fails closed and
cannot substitute for the unknown Qt focus/mode/Auto Select checks. Even a
two-UID result cannot alone prove Normal Edit Mode or that the next Roll
command targets this edit point; a reviewed, narrowly bounded menu-setup
protocol and actual Mac evidence are additionally required.

## Next acceptance hinge

1. On a newly authorized, source-matched disposable target only, capture
   exact signed pristine/UID/track states and verify no historical or
   Producer target is selected. An intentional V2–V5/A1 locked state must
   be part of the **new** signed baseline; locking after baseline would
   invalidate the recorded geometry.
2. Separately review and authorize an explicitly fixed **selection-only**
   menu setup, never the current F1 roll. Establish the outcome in the real
   Studio SDK with `GetSelectedClips` and exact selected UIDs, and separately
   reason about edit-point/active mode state; no guessing from Qt nulls.
3. Only if actual Mac evidence shows a truthful pre-effect safety substitute,
   integrate it under the existing one-owner/one-start GUI actor, new frozen
   source/actor SHA, fresh case-specific authorization, one-use journal and
   unchanged native full M4 4/4 + strict #312 requirements. Otherwise keep
   #499 blocked and use the separately approved one-case human-operated
   fallback or await a supported API.

**No existing approval or receipt is reusable.** The historical phase-10
pristine 11/6 capture is only a geometry test oracle. New candidate source
code changes the source graph and invalidates earlier freezes even when its
function is not invoked.

## Independent Claude review and repairs (same adopted branch)

The first candidate commit `7028c460` underwent one independent Claude Opus
code review. The review returned four actionable findings, all repaired in
the subsequent local implementation without a second review claim:

1. **Live native geometry:** re-enumerate all 11 actual SDK native item UIDs,
   track membership, record start/duration and links against signed pristine
   geometry, before *and* after SDK selection readback. An UNKNOWN/partially
   completed earlier roll at 351, 12th inserted item or missing item cannot
   produce a passing candidate result.
2. **True V1:** bind both inventory boundary track IDs/kind/index to the
   signed `(video,1)` track ID, not merely to each other.
3. **Last-moment drift:** recheck native owner, exact project/timeline
   names/UIDs, render-idle, counts for video/audio/subtitle tracks, locks,
   playhead, page and 11 native item geometry again after selected clips.
4. **Closed input parsing:** validate native track/item types before building
   hash maps or sets, so unhashable corrupted values yield the deliberate
   fail-closed `GuiRollRefused`, not an uncaught `TypeError`.

Regression cases cover moved 327→351 boundary before selection, extra,
missing or wrong-track native item, stale selected clip position, missing
owner after readback, post-readback track/item/link drift, wrong V1 and
malformed list-valued UIDs. The larger test run across thirteen related
Test Bench / F1 / M4 files passed **516/516**, and repository-wide Ruff,
Ruff format and strict mypy passed (**407** source files). These are all
injected tests; **no actual Mac selected Roll edit-point behavior was tested**.
The production actor remains unchanged and blocked; this commit does not
replace phase 12 source freeze, native qualification or case authorization.
