# Studio render range and preset check (#329)

On Nov 22, 2026, DaVinci Resolve Studio **21.2.0 build 6** on an Intel Mac rendered
an exact continuous section through the public local scripting API. Named preset
loading sometimes reported success while leaving the prior format selected.
Offer the measured explicit settings path. Keep arbitrary saved and last-used
preset restoration gated on independently verified settings.

## Native result

The installed bundle and connected API both identified build 6. The shared
Resolve owner lock, host operation markers and live idle state were checked
before writes. One disposable project contained two 24-frame clips named A and
B, a frame label in every picture, two section markers and the timeline start
timecode `01:00:00:00`. Save, close and reopen preserved the project and timeline
identities, both markers, the video and audio placement, and the frame interval
`[86400, 86448)`. The timeline also matched after rendering.

| Request after reopen | Native queued marks, inclusive | Local output | Decoded video |
| --- | --- | --- | --- |
| Entire timeline, `SelectAllFrames=True` | 86400–86447 | `whole/entire.mp4` | All labels 00–47 in order, 48 frames, 2 s |
| Section B, `SelectAllFrames=False` | 86424–86447 | `range/section-b.mp4` | All labels 24–47 in order, 24 frames, 1 s |

For this 24 fps nonzero-start timeline, the explicit range used absolute
timeline frames and an inclusive out. Convert a verified section's half-open
timeline-relative interval `[start, end)` to
`MarkIn=timelineStart+start`, `MarkOut=timelineStart+end-1`.

The saved preset was listed after reopen. Its export contained MOV/ProRes 422
and 1920x1080. Starting from MP4/H.264, one `LoadRenderPreset` call returned true
and left MP4/H.264 selected. The load before the section render returned true
and changed the format back to MOV/ProRes 422. Both renders then explicitly
selected MP4/H.264 in single-clip mode. Resolve queued each job as `Custom`.
The load return and queued preset label alone cannot establish the effective
preset. Same-name preset edits and host last-used settings were unverified.

Explicit overrides were 1280x720, 24 fps, H.264 High, `VideoQuality=3500`,
AAC 48 kHz, and an exact directory and base filename with unique naming off.
Both job rows agreed on marks, target directory, filename, raster, rate,
profile and codecs. Each named job completed and produced one MP4 (`isom`) in
its own fresh directory. Both files carried H.264 High, stereo AAC-LC at 48
kHz and a `tmcd` timecode track. Video durations matched the frame counts.
The AAC streams reported 2.069333 s and 1.066667 s respectively. Sample-exact
audio boundary behavior remains unverified.

`SetRenderSettings` accepted `VideoQuality=3500`. An exported snapshot of the
section's current settings recorded `h264_datarate=3500`. The job row exposed
the profile but omitted the numeric quality. Observed video averages were
787,484 and 860,456 b/s on this synthetic content. The exported value verifies
setting identity in the current configuration and the bitstream verifies High
profile. A fixed output bitrate and production-grade quality were unverified.

## Refusal and handoff

- A missing preset name was absent from the live list and the native loader
  returned false with zero jobs. If using a saved preset, resolve its exact
  current identity and check the settings the product will rely on.
- The probe refused an out-of-bounds range and an unknown format using the
  target timeline and live format catalog before queueing. It refused an
  existing output path before queueing and verified that the previous MP4's
  bytes and the job inventory were unchanged. These were probe guards.
  The native MP4 setter returned false for `ReplaceExistingFilesInPlace=False`
  in isolation. Keep an independent existence check and separate destinations.
- For #71 and #128, expose this measured Studio format and one continuous
  range with explicit verifiable settings. If preset identity or effective
  settings cannot be verified, use Resolve's Deliver page. Select Entire
  Timeline or In/Out Range in Single Clip mode, confirm the first and last
  pictures and the format, resolution and quality in Render Settings, then
  choose a new local filename and directory before adding the job. Check the
  completed file before marking it ready. The automation gate, existing design
  acceptance and delivery authorization remain separate.

This test used the short #520 save/reopen loop. [RK-20 and RK-22](../RESOLVE_KNOWLEDGE_GUIDE.md#waiting-recovery-and-current-operations)
cover the earlier long wait and bounded native cancellation/retry. There was
no new recovery run. Other rates, codec settings, Resolve releases, Free and
delivery services were outside the probe.

The [fixture helper](../../scripts/issue329_render_fixture.py) generates the
two source clips in an empty scratch directory with FFmpeg and the macOS Menlo
font. Its `check` mode decodes every frame of both outputs and reads the six
binary marks that encode the printed frame number.
