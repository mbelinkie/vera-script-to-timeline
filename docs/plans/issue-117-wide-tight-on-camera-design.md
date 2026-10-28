# Issue 117 plan — Wide/Tight On Camera design amendment

## Outcome and authority

Create a versioned successor to the Producer-accepted S01–S03 Claude Design
artifact that lets the author choose exactly **Wide** or **Tight** for every
On Camera appearance. VERA authors when each treatment appears; Resolve owns
the project-specific zoom and position values in later contract and integration
slices.

The accepted artifact
`Script to Timeline - Two-Column Authoring S01-S03 v2.dc.html` remains
immutable comparison evidence. The successor is named
`Script to Timeline - Two-Column Authoring S01-S03 v3.dc.html`.

## Slice ritual

Scope: the S01–S03 successor, its exact Claude prompt, interaction and viewport
evidence, and Producer acceptance.

Exclusions: production UI or persistence; shared-contract, fixture, golden, or
generated-type changes; compiler behavior; Resolve mutation; color and audio
processing; numeric framing-profile controls; multicamera support; automatic
camera switching; and changes to S04–S19.

Touched contracts and fixtures: none. Issues #118 and #119 own the successor
contract and Resolve proof after this design is accepted.

Dependencies: accepted issues #14, #55, and #56. No new software dependency.

Automated checks: repository validation, whitespace checks, and a focused diff
review of the local plan, prompt, checklist, and Deferred Register wording.

Design checks: pointer and keyboard treatment selection; visible and accessible
state; preview treatment; carry-forward seeding with explicit stored state;
Undo/Redo; responsive layout; and the required continuity examples at 1280×800
and 1024×768.

Producer acceptance: the Producer reviewed and explicitly authorized the exact
Claude prompt in #117 comment 5628742071. After implementation, the Producer
walks the exact v3 artifact and either explicitly accepts #117 or names the
first failed state. The issue remains In progress or In review until that
response is retained.

## Design semantics

- `Wide` and `Tight` are the only authoring terms in this release. Numeric zoom
  and X/Y position are not exposed in S01–S03.
- An On Camera appearance is either an ordinary On Camera card or an automatic
  `↩ ON CAMERA RESUMES` return. Every appearance visibly and accessibly owns one
  treatment selection.
- Creating an appearance seeds its treatment from the most recently authored
  On Camera appearance, then immediately stores an independent explicit choice.
  Later edits to the earlier appearance do not cascade.
- Treatment changes affect picture only. They never imply a cut, restart,
  skipped frame, repeated frame, or audio edit in the presenter source.
- A row boundary is not itself a framing boundary. Consecutive appearances with
  the same treatment remain visually continuous; a boundary exists only when
  the authored treatment changes.
- A cutaway hides the continuous presenter picture temporarily. Its owned
  return may choose a different treatment while the parent presenter source and
  processed dialogue continue underneath.
- With a configured presenter still, both treatments use that same image with
  visibly different crops. Without one, Wide and Tight use distinct neutral
  full-body/torso and close head-and-shoulders silhouette treatments. The
  difference must not rely on color.
- Non-presenter visuals, including placeholders, B-roll, stills, and
  `Visual Undefined`, never expose or retain a framing treatment.

## Bounded sample amendments

Keep the accepted 22-row document and all unrelated sample behavior intact.
Use these existing rows:

- Row 2: `Wide` for the opening On Camera card and its return after the future
  lower-third placeholder. This demonstrates an unchanged treatment across a
  temporary overlay/cutaway.
- Row 6: `Wide` for the parent On Camera card and `Tight` for the return after
  the exact B-roll cutaway. Replace only the contradictory phrase
  `When we return to the wider view` with `When we return to me`.
- Row 7: `Tight` for the parent and return around the backward-derived cutaway,
  proving that a cutaway does not force a framing change.
- Row 18: `Wide` for the notebook demonstration.
- Row 19: `Tight` for the adjacent closing On Camera row. Rows 18–19 therefore
  demonstrate a direct `Wide → Tight` treatment change at a row boundary while
  the underlying presenter recording and dialogue remain continuous.

The interaction harness must also prove carry-forward behavior by adding an On
Camera appearance after a `Tight` appearance, observing an explicit `Tight`
selection, editing it independently, and Undoing/Redoing that edit.

## Downstream handoff

Issue #118 defines the versioned framing-profile and compiler/manifest
contracts, including source continuity and independent processed audio. Issue
#119 proves Studio and Free delivery in disposable Resolve projects. Issue
#120 retains future multiple-camera sources and authored per-appearance angle
selection; automatic switching remains separately deferred.
