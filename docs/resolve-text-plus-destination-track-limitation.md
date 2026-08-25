# Resolve Text+ Destination-Track Limitation

## Status

**Open capability gap.** The producer accepted this documented limitation for
Slice 0.4 on 2026-08-25 so that the spike could close, but the limitation itself
is not considered solved.

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

Questions worth testing separately include whether a newer Resolve public API
adds destination-track or timeline-item movement support, or whether a
documented composition/template workflow can create an equivalent title on an
explicit track while still satisfying the identity and verification criteria.
