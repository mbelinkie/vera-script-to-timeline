# Phase 10 handoff: re-run Issue 149 findings through the Workflow Integration path

Issue 149's Tier 1 evidence ran inside Resolve via Workspace → Console with External Scripting None. VERA ships as a Workflow Integration, and #149's acceptance criteria require each finding VERA will rely on to be re-confirmed through that path. This handoff lists the minimum re-runs, written for the existing #141 harness: the injected-object Workflow Integration launcher, one-phase single-dispatch, a complete pair before and after, and the new-result template.

Use a **new disposable project**. Regenerate fixtures with `evidence/scripts/gen_fixtures.py`, using either the recorded `evidence/fixtures/words/*.aiff` or fresh `say -v Alex -r 180` words, and verify against `evidence/fixtures/manifest.json`. Make the same-layout replacement for W6 with `ffmpeg -i cutaway.mov -i a2_numbers.wav -map 0:v -map 1:a -c:v copy -c:a pcm_s16le -shortest relink_alt.mov`. Record the Resolve version; 149 used 21.1.1.10. Everything below is synthetic-only.

## Fixture timeline shape (25 fps, 1920x1080, 48 kHz)

| Track | Item |
| --- | --- |
| V1 + A1 (linked) | `base.mov` frames [0,400): video src_id 1 plus A1 NATO words |
| A2 (mono) | `a2_numbers.wav` [0,400) |
| A3 (mono) | `a3_bed.wav` [0,400) |

Place clips with `MediaPool.AppendToTimeline` and `endFrame = end - 1`. Set the timeline start timecode to `00:00:00:00`.

## Re-runs and pass criteria

| # | Finding | Procedure | Pass |
| --- | --- | --- | --- |
| W1 | Timeline transcript follows the edit | On the **Edit page**: build linked-cut (base [0,100)+[150,400) contiguous), picture-only-cut, and A1-clip-disabled timelines. `DuplicateTimeline` each, then `CreateSubtitlesFromAudio()` on the duplicate. Poll `GetItemListInTrack("subtitle", 1)` until items appear | Linked cut has no "charlie"; picture-only cut keeps it; disabled-A1 timeline has numbers only. Each agrees with a render's word correlation (`scripts/analyze_audio.py`) |
| W2 | Mute and Solo are readable from OTIO | Operator turns on Edit-page **M** on A2 for timeline X and **S** on A2 for timeline Y. With each timeline current, `Export(path, EXPORT_OTIO, EXPORT_NONE)`. Then turn S off and export again | X: A2 track `enabled: false`. Y: A2 `metadata.Resolve_OTIO.SoloOn: true`, then false after S off. Renders: X lacks numbers; Y has only numbers |
| W3 | Mapping mute affects output | `SetSourceAudioChannelMapping` with `track_mapping["1"].mute = true` on the A2 item. Render. Restore | A2 1500 Hz pilot ≤ 0.001 and no number words in the render; getter reads `mute: true`; restored pair equals the original |
| W4 | Exact retime in OTIO | Clicks on A2 plus base on V1/A1; `SetSpeed({Percentage: 37.5, PitchCorrection: False})` on V1 and clicks. Export OTIO; render | OTIO `LinearTimeWarp.time_scalar` = 0.375; rendered impulses within ±1 sample of `source_sample / 0.375` (`scripts/clicks.py`); linked A1 speed recorded either way |
| W5 | Track getters are current-timeline-only | With a muted A2 on timeline X, read `GetIsTrackEnabled("audio", 2)` with X current and with X not current | Correct only when current; all-False otherwise |
| W6 | Replaced bytes vs render | Import `swap.mov` (copy of base). Replace its bytes with a **same-layout** file (`relink_alt.mov` = cutaway video + mono PCM). Render without relink, then `RelinkClips([item], folder)` and render. Restore and relink | Render without relink: job `Failed` with a decode error. After relink: decoded frames are src_id 2. API Online/Date Modified unchanged throughout. **Do not** use a replacement lacking the audio stream (that hung Resolve in 149) |
| W7 | Locks guard UI edits | `SetTrackLock` all tracks; operator or menu attempts Delete on a selected clip; API `SetClipEnabled(False)`; unlock | Clip count unchanged; `SetClipEnabled` returns False |

## Not required for acceptance

- Database-timestamp freshness. It is undocumented and depends on Live Save; it is a design input, not an acceptance claim.
- Lineage stamps. The behaviour reproduced Codex's UID observations; the rule is a design proposal for #131/#139.
- Visibility predictor.

## Reporting

Use the #141 handoff's new-result template for each W row. Classify each row as reproduced, adverse, unknown, or harness failure. Link results from Issue 149 and from #141's report.
