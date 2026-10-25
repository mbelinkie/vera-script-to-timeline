# #283 — Resolve scene-cut scripting API evidence

Status: documentation-only investigation. Real proof remains pending an
exclusive Resolve slot.

## Scope and sources

This review read the local DaVinci Resolve scripting reference only. Resolve was
not launched or queried, and no media was inspected. The installed scripting
bundle is at:

`/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/`

Its `README.md` identifies itself as the Scripting API reference, last updated
31 Aug 2026, and says Resolve 21.1 and above includes the bundled Python 3.14
distribution (`README.md:1-3, 94-97`). The adjacent `CHANGELOG.md` describes
versioned API changes and has a 21.1 section (`CHANGELOG.md:1-8`). These
identify the documentation context; they do not independently establish the
version of a running Resolve binary.

## Documented API surface

- `Timeline.DetectSceneCuts() -> bool` is present in the typed API. Its
  description says it “Detects and makes scene cuts along the timeline.” The
  wording supports treating it as an operation that changes the timeline, but
  the reference does not define what the boolean means (for example, whether it
  means accepted, completed, or successful detection).
  (`DaVinciResolveScript.pyi:2342-2344`)
- `Project.GetDetectSceneCutsStatus()` returns the status of the active
  `DetectSceneCuts` operation. Its documented fields are `JobStatus`
  (`Inactive`, `Analyzing`, `Complete`, or `Cancelled`),
  `CompletionPercentage`, `AnalysisSpeed` in fps, and
  `EstimatedTimeRemaining` in seconds. The status type contains no cut list or
  boundary field. (`DaVinciResolveScript.pyi:1208-1215, 1955-1957`)
- `Timeline.DuplicateTimeline(name) -> Timeline` is documented to duplicate the
  timeline and return the created timeline. This gives a documented way to
  direct a potentially mutating detection call at a duplicate, subject to
  verifying the runtime behavior and selected-timeline requirements.
  (`DaVinciResolveScript.pyi:2285-2287`)
- A timeline can enumerate items by track with `GetItemListInTrack(...)`.
  `TimelineItem.GetStart()` and `GetEnd()` report timeline frame positions;
  `GetSourceStartFrame()` and `GetSourceEndFrame()` report the media-pool clip's
  start and end positions in that timeline item. These APIs expose candidate
  segment boundaries after a detection operation, but do not specify whether
  the end is inclusive, how detection boundaries are rounded, or how source
  positions behave for retimes and other nontrivial items.
  (`DaVinciResolveScript.pyi:2201-2203, 2393-2405`)
- Timeline markers are available through `Timeline.AddMarker(frameId, ... )`,
  which returns a boolean, and `Timeline.GetMarkers()`, which returns a map
  keyed by `frameId`. Marker information includes color, duration, note, name,
  and optional custom data. This is a documented way to record a candidate
  timeline-frame boundary; it does not itself validate a source-frame mapping.
  (`DaVinciResolveScript.pyi:337-348, 2216-2228`)

## What the references establish

The typed reference documents an operation to make cuts, a project-level
progress/status getter, a timeline duplication method, timeline-item source
frame getters, and timeline markers. In the inspected `.pyi`, the operation
returns only `bool`; the status object reports job metadata, not detected cut
positions. The documented route to inspect boundaries is therefore to read the
timeline items after detection, rather than to consume a documented scene-cut
result list.

This is enough to justify a controlled runtime spike, but not to claim that
scene-cut results safely yield exact source-frame boundaries. The reference
does not define status lifecycle timing, cut-boundary inclusivity, frame-rate
conversion, detector accuracy, or behavior for retimed, multicam, linked,
transitioned, or multi-track timelines. Those details need observed evidence.

## Runtime proof still needed

When Resolve is available exclusively, use a disposable synthetic project with
a single fixed-rate, constant-speed source and known frame-labeled cuts. On a
uniquely named duplicate, call `DetectSceneCuts`, record the boolean and status
sequence (including how `Inactive` behaves), then enumerate the resulting
items and compare their timeline and source-frame positions with the known
boundaries. Record the source end-point convention and verify marker
readback. Confirm the original timeline remains unchanged. Until that check is
done, source-frame cut boundaries remain unproven.
