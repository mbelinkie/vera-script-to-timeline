# Resolve Text+ Destination-Track Limitation

## Status

**Resolved for the shipped pinned-template path.** The original stock-insertion
limitation remains true, but VERA no longer uses that path for production
Text+. Resolve Studio 21.0.4 build 5 evidence proves caller-selected track and
duration control through the producer-authored, hash-pinned `.drb` plus
`AppendToTimeline`. Stock-title catalog enumeration and arbitrary Fusion titles
remain explicitly open.

## Desired behavior

Using only DaVinci Resolve's supported public scripting API, insert the stock
Fusion title `Text+` at a requested timeline frame on the caller-selected video
track—V4 (`V4 Graphics / titles`) in the accepted VERA track map—and set or
otherwise control its intended timeline duration.

## Observed behavior

Test environment:

- DaVinci Resolve Studio 21.0.4, connected API build 5
- Default-path macOS bundle build 21.0.40005
- macOS 15.1, x86_64

The supported call
`Timeline.InsertFusionTitleIntoTimeline("Text+")` inserted a title at the
frame-zero playhead, returned a timeline item, and allowed the spike to verify
the resulting item's title fingerprint. Resolve placed the item on **V1**, not
the requested **V4**, and gave it the configured/default **120-frame** title
duration.

The installed public API documents a title-name argument but no destination
track or duration argument for `InsertFusionTitleIntoTimeline`. It also exposes
no supported stock Fusion-title catalog enumeration call. Consequently, the
spike can verify the item returned after requesting `Text+`, but it cannot:

1. select V4 during insertion;
2. prove before insertion that `Text+` is present in the stock-title catalog;
3. set the inserted title's duration through that insertion call; or
4. claim a general supported-API solution based only on manually moving or
   trimming the item in Resolve.

No private/undocumented API or Resolve UI automation was used as a workaround.

## Reproduction evidence

- Project: `VERA Slice 0.4 Producer Acceptance 20260825-021704`
- Timeline: `VERA build 00000000-0000-4000-8000-000000000103`
- Requested title: `Text+`
- Requested playhead: frame 0
- Observed destination: V1
- Observed duration: 120 frames
- Expected destination under the VERA default map: V4

## Criteria for a solution

A proposed solution should demonstrate, on a fresh uniquely named test project:

1. use of documented, supported Resolve APIs only;
2. deterministic insertion of the requested title on a caller-selected video
   track without relying on whichever track Resolve chooses by default;
3. deterministic control of the resulting title duration;
4. post-save/reopen verification of title identity, track, start frame, and
   duration through the public API; and
5. safe failure before mutation when the required capability is unavailable.

One question remains worth testing separately: whether a newer Resolve public
API adds supported stock-title catalog enumeration or destination-track and
duration arguments to stock insertion. That would be a different capability
from the accepted pinned-template solution below.

## Accepted pinned-template solution

The shipped path imports `text_plus_template.drb` through the documented
`MediaPool.ImportFolderFromFile` surface and appends its one generator with
`MediaPool.AppendToTimeline`. The asset is pinned by SHA-256, checked for safe
ZIP structure and expected one-bin/one-generator topology before connection,
and retained in each project for provenance. VERA resolves the requested track
ID through the manifest rather than hard-coding V4 and uses the observed
generator rule `endFrame = requested duration + 1`.

Resolve Studio 21.0.4 build 5 evidence:

- Validation project: `VERA TextPlus Template Validation 20260825-230705`.
- Integrated project: `VERA TextPlus Integrated Acceptance 20260825-234847`.
- Timeline: `VERA build 00000000-0000-4000-8000-000000000103`.
- Asset SHA-256:
  `4a984512f1c7eba6f15a4ea8104a6bb4953e50e4f8aa816a53138daf818372ac`.
- Stock and template fingerprints: one Fusion composition, exactly one
  `TextPlus`, registration IDs `MediaOut`, `TextPlus`.
- Candidate end frames 23, 24, and 25 produced durations 22, 23, and 24;
  end frame 73 produced exactly 72 frames.
- The integrated title was appended at absolute frame 0 on manifest track
  `video-graphics` (V4), lasted exactly 72 frames, and was the only title item.
- Both runs saved, closed, reopened, and verified without discrepancy. The
  producer visually inspected and accepted both retained projects on
  2026-08-25.

No private API, UI automation, project deletion, timeline deletion, or stock
insertion fallback is used. The solution is deliberately narrow: only the
shipped `Text+` asset is supported.
