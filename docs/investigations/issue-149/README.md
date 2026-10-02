# Issue 149 — independent Resolve second opinion on Issue 141

Status, 2026-10-02: discovery-tier (Tier 1) evidence is complete for plan phases 0–9. Phase 10, re-confirmation through the shipped Workflow Integration path, is **not done**; see [codex-rerun.md](codex-rerun.md). Producer review of the verdict table is also pending. This issue should stay open until both are done.

## Setup

| Item | Value |
| --- | --- |
| Application | DaVinci Resolve Studio **21.1.1.10** (Issue 141 used 21.1.0 build 14) |
| Host | macOS 15.1, Intel; injected CPython 3.14.7 |
| Scripting boundary | External Scripting **None** throughout. Scripts ran inside Resolve via **Workspace → Console** (Python 3), which supplies the injected `resolve` object. One line, `exec(open(.../runner/run.py).read())`, executes `runner/job.py` and writes `runner/results/<job>.json` |
| Installed docs | `README.md` SHA-256 `5f58c94d…` (same as 141). `DaVinciResolveScript.pyi` SHA-256 `2755259e…` (141 recorded `00078fa1…`, so the stub changed in 21.1.1) |
| Project | Disposable `VERA 141 Second Opinion 20261002-a`. The retained 141 project and `semi1b.mp4` were never opened |
| UI actions | Menu paths and clicks by computer control: Split Clips, Copy/Paste, Cut/Paste, Trim → Nudge, track Mute/Solo buttons, clip selection, Delete |
| Fixtures | `evidence/scripts/gen_fixtures.py` from macOS `say` words (Alex, 180 wpm). A1 speaks NATO words with a 1000 Hz pilot tone; A2 speaks numbers with a 1500 Hz pilot; A3 is a bed with a 2000 Hz pilot. Every video frame carries a 16-block machine-readable code `(src_id<<12)\|frame`. A click track has impulses at non-frame-aligned samples. Manifest: `evidence/fixtures/manifest.json` |

Every word, track and source frame in the output therefore identifies itself. Renders were analysed by normalized cross-correlation per word, pilot-tone level per track, and frame-code decoding (`evidence/scripts/`).

## Verdicts against the 141 handoff

Outcome labels follow the handoff's "useful second opinion" section.

| # | 141 limitation | Outcome | What was observed | VERA consequence |
| --- | --- | --- | --- | --- |
| 1 | No timeline transcript (R2 #6) | **Resolved by a different method** | `Timeline.CreateSubtitlesFromAudio()` transcribed the edited mix on 8 timelines. The linked cut dropped "charlie"; the picture-only cut kept it (control). Clip disable, track disable, mapping mute, Mute and Solo each removed exactly the affected track's words. Rendered PCM agreed word for word in every case | A transcript of what the edit actually says is available from Resolve. Caveats: asynchronous (~30 s for a 16 s timeline); returns **False on the Deliver page**; **adds a subtitle track to the timeline** (run it on a `DuplicateTimeline` copy); subtitle items are phrase segments with frame positions, not per-word timing |
| 1b | Nested-clip transcript | Reproduced | `TranscribeAudio(None, True)` on a timeline's pool item returned None; `GetTranscription` stayed None | Not a usable route |
| 2 | Mute state unreadable | **Resolved** | The Edit-page Mute button equals `GetIsTrackEnabled("audio", n)` = False (current timeline), OTIO track `enabled: false`, and DRT track Flags bit 2. The render was silenced | Mute is readable |
| 3 | Solo / routing unreadable (R2 #2) | **Resolved for Solo** by export | No getter changes. OTIO track metadata `Resolve_OTIO.SoloOn: true`; DRT track Flags 32. Turning Solo off on the same timeline flips both back. The render honours Solo | Read Solo from an OTIO export. Bus routing and sends were **not tested** |
| 4 | Mapping mute had no output effect (R2 #1) | **Contradicted on 21.1.1** | `SetSourceAudioChannelMapping` mute on A2: A2 pilot 0.020 → 0.0002 in the render; all A2 words gone; subtitles agree | Effective here. Readable only via `GetSourceAudioChannelMapping` (absent from OTIO and FCPXML). Cause of the difference from 141 unknown: version, or 141's harness or clip state |
| 5 | Context-dependent getters (R1.4) | **Explained** | Every track reads disabled on any non-current timeline. The installed docs mark the voice-isolation and dialogue-leveler properties "[Active Timeline Only]" — exactly 141's eight keys | Select a timeline before reading track state, or use its OTIO export |
| 6 | Timing calibrated only for integer 100% (R2 #5) | **Resolved for constant retime** | OTIO `LinearTimeWarp.time_scalar` (0.375, 1.5) and FCPXML rational `timeMap` are exact. Rendered clicks landed within ±0.33 samples of source/speed: 5/5 at 37.5%, 14/15 at 150% (the miss is a peak-picker artefact next to speech). Getters round, and at 37.5% the source end time reads 6.01 s against a true 5.985 s | Take timing from OTIO, not getters. 29.97 fps and variable speed curves untested |
| 7 | API retime leaves linked A1 at 100% | **Not reproduced** | `SetSpeed` on V1 only; linked A1 reported the same speed | Linked audio follows an API retime on 21.1.1 |
| 8 | Lineage unprovable (R1.1–R1.3) | **Still ambiguous in the strict sense; practical rule validated** | See the lineage table below | Use the stamp rule; flag mismatches for review |
| 9 | Four "Out" changes after Copy/Paste (R1.3) | **Not reproduced** | Media-pool `In`/`Out` and `GetMarkInOut` stayed empty through Copy, Paste and Cut | Most likely source-viewer marks. Still formally unexplained |
| 10 | Wrong bytes / displayed replacement (R4.3) | **Reproduced and extended** | See the media-replacement table below | Hash files yourself. Trust renders after `RelinkClips`, never the viewer or `ExportCurrentFrameAsStill` |
| 11 | Freshness / ABA (R5) | **Partially resolved** | See the freshness section below | Guarded apply is possible; a true atomic token is not |
| 12 | Picture visibility (R3) | **Resolved for a supported subset** | 399-frame timeline with opaque, 50% opacity, 0.5 zoom and disabled cutaways plus a 50%-alpha overlay. The structural predictor named 301 frames, all 301 matched decoded output, and it flagged the 98 opacity and zoom frames as "needs render" | Predict on-screen shot for simple stacks; render or review the rest. Transitions and Fusion untested |
| 13 | Nudge did nothing (R5.2) | **Harness explanation** | Trim → Nudge → One Frame Right moved the selected clip 100→101, UID kept, with selection verified via `GetSelectedClips`. The "." key did nothing | Not a Resolve limitation |

Also reproduced from 141: a 40-frame still request produced a 125-frame item; `endFrame` 399 gives duration 399; `perfCacheClipsLocation` reads `CacheClip` after a reopen.

### Lineage (real UI edits)

Clips were stamped with marker `customData` (`vera:el-001`), clip color, flags, and head and tail markers. A cutaway was forged with el-001's stamp as a counterexample.

| Edit | Original UID | New piece | Stamps on new piece | Distinguishing fact |
| --- | --- | --- | --- | --- |
| Split Clips at 100 | kept by left half | right half, new UID | all copied | right half's source range continues the original's |
| Copy/Paste | kept | new UID | all copied | source range identical to the copied clip's |
| Cut/Paste (move) | **gone** | new UID | all copied | same media and source range as the vanished original |
| DuplicateTimeline | kept in original | all new UIDs | all copied | belongs to the other timeline |
| Menu nudge | kept | — | — | record +1 |

Flags are shared by every clip of the same source media, so they cannot stamp individual occurrences. Markers are keyed in source frames, so both split halves carry both markers.

The rule:

1. A journaled UID still present is the original.
2. A new UID whose stamp matches a journaled element **and** whose media matches that element's journaled source is a derived piece. Its source range classifies it as a split, copy or move.
3. A stamp on the wrong media (the forged cutaway) is flagged for review.

### Media replacement at the same path

| Step | Viewer / still | Render | API |
| --- | --- | --- | --- |
| Bytes replaced, no action | old frame (once) or "Media Offline" (twice); no warning in the API | empty file; job `Failed`: "Error decoding full resolution media" | still Online, old Date Modified |
| After `RelinkClips` (True) | still the **old** frame | **new bytes** | unchanged |
| Replacement lacking audio, then relink, then render | — | **Resolve hung; force-quit** | — |

### Freshness

There is no public revision token: `GetProjectLastModifiedTime` returned None. After A→B→A (marker add, then delete), the OTIO hash and full getter fingerprint return exactly to A. The live-saved project database `…/Resolve Project Library/Resolve Projects/Users/guest/Projects/<project>/Project.db` (SQLite) leaves a trail:

- **`Project.db` modified time and `SM_Project.LastModTimeInSecs`** advance on every edit, including the revert. They catch ABA. They do not move while idle or on playhead moves. The file timestamp also moves on page and timeline switches.
- **Per-timeline `Sm2Sequence.DbSavedTime`** is not a clean token. It bumps for the timeline being left, and edits to a non-current timeline landed on the current timeline's row.
- **Track locks** (`SetTrackLock`) blocked a UI Delete on a selected clip and refused `SetClipEnabled`. `SetClipColor` still succeeded.

## What is still NOT possible or established

1. **Atomic apply.** No revision token or transaction exists. A change in the instant between the final check and the apply cannot be excluded. The database-timestamp guard is undocumented and depends on Live Save. Locks do not cover every API setter.
2. **Proof of ancestry.** Cut/Paste destroys UIDs, and stamps and signatures can be copied or forged. Only a journal-plus-stamp rule with review on mismatch is available.
3. **Word-exact timing from Resolve.** Transcript words carry frame timecodes. Subtitle items are phrase segments. Sub-frame word edges must come from VERA's own alignment of the source transcript through the OTIO time map.
4. **Non-mutating timeline transcription.** `CreateSubtitlesFromAudio` writes a subtitle track and needs the Edit page. Run it on a duplicate timeline.
5. **Trustworthy on-screen state after media changes.** The viewer and stills can show stale frames. Only renders and file hashes are trustworthy.
6. **Visibility for transitions, Fusion and OpenFX.** These still need a render.
7. **Untested, so unknown rather than impossible:** bus mute, sends and routing, volume automation to silence, Fairlight FX, 29.97 fps, variable speed curves, and whether OTIO exports of a *non-current* timeline report Mute and Solo correctly.
8. **Acceptance through the shipped path.** Everything above ran via the Console under External Scripting None. Phase 10 re-runs it through the Workflow Integration.

## Harness incidents (not Resolve findings)

- One Console command was typed into the viewer after the Console window moved. A full integrity snapshot afterwards found no timeline or pool change (`integrity-after-stray-keys.json`).
- The first `CreateSubtitlesFromAudio` on T6 returned False because Resolve was on the Deliver page. It succeeded from the Edit page.
- Force-quit after the layout-mismatch render hang. Live Save preserved all 11 timelines (`restart-integrity.json`).
- Background clicks did not select timeline clips; foreground clicks did. Every selection was verified with `GetSelectedClips` before edits.

## Evidence index

- `evidence/runner/` — the runner, helper libraries (`lib_*.py`) and the last job script. `runner/results/*.json` holds every job's raw output: snapshots, journals of each call and its return value, and errors.
- `evidence/scripts/` — fixture generator, frame-code decoder, word/pilot analysis, click timing, visibility predictor.
- `evidence/exports/` — OTIO, FCPXML, EDL and CSV exports; DRT exports unpacked to XML.
- `evidence/fixtures/manifest.json` and `words/` — fixture definitions and the recorded `say` words.
- `evidence/raw-sha256-before-redaction.json` — hashes of every evidence file before home-folder paths were replaced with `~`. AAF exports were withheld and are hashed there.
- `evidence/local-binaries-sha256.json` — hashes of renders, stills, generated media and database copies kept on the producer's Mac under `out/issue-141-second-opinion/`.
