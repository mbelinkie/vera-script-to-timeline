# #283 — Resolve scene-cut scripting API evidence

Status: external runtime check complete on DaVinci Resolve Studio 21.1.1.

Recommendation: **defer automatic source-range correction.** Resolve's native
detector is viable as an isolated diagnostic input, but this investigation did
not establish the frame-exact source-range write path required for safe
automatic correction. A future bounded implementation spike must prove that
path through VERA's actual compiler/package-to-Resolve flow before it changes
any selected source range.

## Scope and sources

The API review used the local DaVinci Resolve scripting reference. The runtime
proof below used Resolve Studio 21.1.1, a newly created disposable project, and
only privately retained, authorized local media. The installed scripting bundle
is at:

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

## Runtime evidence

All runtime work used uniquely named disposable projects. Before each proof,
the open timeline was fingerprinted by track/item record and source fields; it
was reloaded after the proof and matched the original fingerprint. The analysis
timeline was a duplicate, not the original. No source asset was altered.

### Synthetic fixed-rate proof

The synthetic source was 144 frames at 24 fps: three 48-frame solid-color
shots, with known hard cuts at source frames 48 and 96. `DetectSceneCuts()`
returned true and the project status completed. Its duplicate analysis timeline
contained four segments with source starts 0, 48, 93, and 96.

- Both known cuts were recovered at their expected source positions.
- Resolve also created an unexpected three-frame segment from 93 to 96. This
  is a false positive in an intentionally simple clip, not an error that VERA
  can safely auto-correct around.
- The source timeline itself retained its original single item. The external
  timeline fingerprint and selected project/timeline were restored unchanged.
- A marker written only to the duplicate analysis timeline was readable again
  by its VERA custom-data identity.

This proves the safe detector pattern for eligible simple media: duplicate,
detect, enumerate resulting boundaries, then discard the analysis timeline. It
also proves why multiple or ambiguous nearby boundaries must require editor
review rather than automation.

### Authorized motivating occurrence

The retained #145 Sweden b-roll occurrence described in the issue was located
through its private preparation manifest. Its selected source range is 143
frames long. A matching retained local derivative, used only in a disposable
project, yielded one internal detection four frames before the selected
out-point.

With the proposed *default* settings (`warningWindowFrames = 12`,
`autoAdjustWindowFrames = 3`), that is a standard warning, not an automatic
change: it is within the warning window but outside the automatic window. This
is the expected result; the numbers remain settings defaults, not hard-coded
behavior. Raising the automatic setting to four frames would make the proposed
trailing-edge slide eligible, subject to verified handles and an exact range
write path.

The diagnostic transformation model changed no other primary-visual occurrence:
the five non-target source ranges were retained exactly. Only the qualifying
occurrence is ever a candidate for a source-window slide; all non-qualifying
b-roll remains visually and temporally untouched.

The retained derivative could not be re-verified against the historical
manifest's original/delivered content hashes because those referenced artifacts
are no longer present at their recorded locations. This evidence is therefore
strong enough to reproduce the reported boundary behavior privately, but not
to assert a cryptographic identity for the historical file.

### Correction-path limitation

The direct scripting probe attempted to build equal-duration timeline clips
from adjacent source ranges around the detected boundary. Resolve preserved the
record duration, but its reported source start/end positions varied
non-uniformly for neighbouring requested ranges. For example, nearby requests
produced source-range reports that were not a consistent inclusive/exclusive
translation of the inputs. The reference does not specify this convention.

That discrepancy means this investigation cannot prove a frame-exact four-frame
source slide through the scripting API alone. It must not be papered over with
an offset assumption: doing so could trade the reported flash frame for a
different unintended frame.

## Decision and bounded follow-up

The native Resolve detector is feasible for a read-on-duplicate diagnostic
workflow and VERA-owned markers. It is **not yet feasible evidence for the
automatic correction described in the issue**, because the exact source-range
write/read convention has not been established on the real VERA assembly path.

Do not add production settings, marker management, caching, or automatic
source edits from this result. If the work is resumed, start a bounded
successor that:

1. uses a cryptographically retained source fixture with the actual
   compiler/package import path;
2. demonstrates a source-window slide whose before/after rendered frames and
   record geometry are exact; and
3. proves that a correction changes only the eligible occurrence while all
   other b-roll source ranges and rendered output stay identical.

Until then, the safe conclusion is diagnostic-only feasibility and a defer for
automatic compensation.
