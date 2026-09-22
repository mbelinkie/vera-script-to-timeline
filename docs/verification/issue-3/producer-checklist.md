# Issue #3 producer acceptance

The automated and connected evidence is retained in
[`ev24-capability-20260922-030002.json`](ev24-capability-20260922-030002.json).
The dedicated Resolve Studio project is **VERA EV24 Capability
20260922-030002**. It is an audit project, not a production project.

1. Open that project in DaVinci Resolve Studio 21.1.0 build 14 and inspect the
   four timelines named `EV24 standard-auto-fill-120`,
   `EV24 explicit-overrides-120`, `EV24 otis-auto-fill-64`, and
   `EV24 test-badge-64`.
   **Expected:** each contains one lower third at frame 0 on V4, and the
   duration in the timeline name agrees with the clip duration.
2. Play the 64-frame Otis and test-badge timelines, then the 120-frame
   standard and override timelines.
   **Expected:** the authored 48-frame entrance and 16-frame exit remain
   visually acceptable at both lengths.
3. Inspect the text values. **Expected:** standard and Otis preserve empty
   VERA overrides so authored automatic fill supplies the display text;
   the override timeline shows `The Code` / `Nemo`; Otis has no Year in the
   retained semantic snapshot; only the fourth timeline uses the magenta,
   non-production package test badge.
4. Compare the four results with the retained JSON report. **Expected:** every
   graph identity, placement, duration, semantic value, and applicable control
   readback agrees after the recorded save/reopen.

Reply on issue #3 with `Accepted EV24 Fusion capability spike.` if all four
steps pass. Otherwise report the first mismatched timeline, frame, and value.

Producer acceptance was recorded on 2026-09-22.
