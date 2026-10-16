# R4 in-range repair proposal

## Finding

The retained Resolve 21.1.0.14 reads identify `VERA 141 R4 availability` by UID `64de8a4c-86bd-4f19-9d20-47b8940f610b`. In both the 01:45 recovery preflight and postflight, its start timecode is `01:00:00:00`, its start and end frames are both `90000`, and its sole V1 occurrence, `base.mov`, remains at record frames `0–199` (duration 199); A1 is empty. The timeline therefore does not cover the existing occurrence at its current program range. Recovery only relinked media: the retained before/after timeline reads match on these values.

The installed scripting stub documents `Timeline.SetStartTimecode(timecode: str) -> bool` as setting the timeline start timecode. It documents no separate setter for timeline frame bounds, and says nothing about how this call affects the end frame or existing occurrence record positions. The setter is the smallest documented native candidate, not a proven fix.

## Proposed bounded correction

On the existing R4 timeline only, after the usual exact project/timeline identity and consistent-read preflight, request `timeline.SetStartTimecode("00:00:00:00")` through the probe's existing mutation journal. Do not create a replacement timeline, append an item, move or trim the occurrence, change tracks, or alter the media locator. This requests a zero-based timeline start at the project's verified 25 fps; it does not assume how Resolve will recompute the range.

Before the call, retain a complete timeline snapshot and pin at minimum: project identity; R4 UID/name; start timecode and start/end frames; track types, indices, names and counts; V1's single item's source identity, enabled state, record start/end and duration; A1's empty item list; and marker/settings reads already included in the standard capture. Require two equal adjacent reads. Stop before mutation on identity mismatch, missing/failed getters, inconsistent captures, or any unexpected track/item state.

After a true return, take two equal adjacent reads and require all of the following:

- The same project and R4 UID/name remain selected and present.
- `GetStartTimecode()` reads `00:00:00:00`; `GetStartFrame()` reads `0`; and `GetEndFrame()` is greater than frame `50` and no greater than `200`. Accept an observed end value of `199` or `200`; the API's inclusive/exclusive convention is not established here. This range covers the existing 0–199 occurrence and the selected in-range samples at frames `0` and `50`. Frame `200` is not a required sample for this repair.
- The only V1 item is still the same `base.mov` source occurrence, with its preflight record start/end and duration unchanged at `0–199`/199; A1 remains empty. Track layout, markers, settings, and other captured timeline state match the preflight.
- No additional timeline or occurrence appears, and both postflight reads agree.

The end-frame threshold is deliberately a readback condition, not a claim about inclusive/exclusive semantics or the setter's behavior. If Resolve changes record positions, source identity, track contents, unrelated captured state, or fails to produce an in-range end frame, stop and retain the evidence. Output evaluation is a separate action and is not part of this repair.

## Failure and rollback

If the setter returns false, throws, or returns true without satisfying every postcondition, journal the failure and immediately capture state. Request restoration with `SetStartTimecode("01:00:00:00")` only when a changed start timecode is observed; then verify against the full saved preflight, including frame bounds and occurrence positions, with two equal reads. Do not retry the proposed correction. If restoration is refused or any preflight value remains changed, retain the partial evidence and stop for operator review; do not attempt compensating edits to items or tracks.

## Focused fake coverage and acceptance

Add focused fake cases for (1) the normal setter/readback path; (2) a false or raising setter; (3) a true return with unchanged out-of-range bounds; (4) a true return with a shifted V1 record position; and (5) a failed or incomplete rollback. Assert that only the first case reaches output evaluation, that failure paths do not append or reposition items, and that the journal records request, return, and both readbacks. This coverage should use the existing R4 occurrence; do not append substitute editorial items to manufacture an in-range result.

The future implementation slice should state its exact files and contracts before editing. No contract, fixture, golden, or previously accepted acceptance-test changes are proposed here. Validate with the focused fake tests and the repository's required checks. Producer acceptance must inspect retained native pre/post evidence in Resolve and confirm the existing R4 occurrence remains in place, the start is zero, and the observed end frame is within the accepted `51–200` range (including `199` and `200`). Program-output evaluation at frames `0` and `50` belongs to a separate acceptance action. Automated tests alone cannot establish the native setter's undocumented side effects.
