# Issue 149 — independent Resolve second opinion on Issue 141

Status, updated 2026-10-03: Tier 1 evidence covers plan phases 0–9. Codex ran Phase 10 (W1–W7) through the Workflow Integration path on the same 21.1.1.10 build: **five rows reproduced and two were adverse** (W3 mapping mute, W6 relink); see [Phase 10 outcomes](#phase-10-workflow-integration-outcomes). Rows 4, 7, 9, 10 and 11 below are revised accordingly. Producer review is pending; this issue stays open.

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
| 4 | Mapping mute had no output effect (R2 #1) | **Conflicting results on the same build** | Console run (T6): A2 pilot 0.020 → 0.0002 in the render, all A2 words gone, subtitles agree. Workflow Integration W3, run twice (once from Deliver, once from Edit with the timeline reselected): flag reads back `mute: true`, but all eight numbers remain and the PCM equals baseline | The flag cannot be read as "silent". Verify by render or subtitles. Cause unisolated; see [Open discrepancies](#open-discrepancies-and-discriminating-tests) |
| 5 | Context-dependent getters (R1.4) | **Explained** | Every track reads disabled on any non-current timeline. The installed docs mark the voice-isolation and dialogue-leveler properties "[Active Timeline Only]" — exactly 141's eight keys | Select a timeline before reading track state, or use its OTIO export |
| 6 | Timing calibrated only for integer 100% (R2 #5) | **Resolved for constant retime** | OTIO `LinearTimeWarp.time_scalar` (0.375, 1.5) and FCPXML rational `timeMap` are exact. Rendered clicks landed within ±0.33 samples of source/speed: 5/5 at 37.5%, 14/15 at 150% (the miss is a peak-picker artefact next to speech). Getters round, and at 37.5% the source end time reads 6.01 s against a true 5.985 s | Take timing from OTIO, not getters. 29.97 fps and variable speed curves untested |
| 7 | API retime leaves linked A1 at 100% | **Explained by link topology** (W4) | Embedded audio sharing V1's media follows a V1-only `SetSpeed`. Separately sourced, reciprocally linked audio stays at 100% (#141's setup). The separate V1 also kept `PitchCorrection: true` despite a false request | Retime every linked item explicitly and verify each speed |
| 8 | Lineage unprovable (R1.1–R1.3) | **Still ambiguous in the strict sense; practical rule validated** | See the lineage table below | Use the stamp rule; flag mismatches for review |
| 9 | Four "Out" changes after Copy/Paste (R1.3) | **Not reproduced** | Media-pool `In`/`Out` and `GetMarkInOut` stayed empty through Copy, Paste and Cut | Formally unexplained. Non-reproduction says nothing about their cause |
| 10 | Wrong bytes / displayed replacement (R4.3) | **Metadata limit reproduced; output behaviour depends on how the file was replaced** | Console run (file overwritten in place): render failed before relink, then showed the new bytes after relink. W6 (atomic `os.replace` keeping the old modified time): renders before **and after** relink still showed the original bytes | Hash files yourself, and verify any relink by rendering. Neither the viewer, the API status nor a `True` relink return proves which bytes are in use |
| 11 | Freshness / ABA (R5) | **Partially resolved** | See the freshness section below. Lock guard reproduced in W7 | Guarded apply is possible; a true atomic token is not |
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

- **`SM_Project.LastModTimeInSecs`** went 1790974651 → 657 (edit) → 660 (revert), so it catches ABA. It stayed unchanged while idle, on a playhead move and on page switches. It changed on timeline switches and on marker edits to a non-current timeline. Evidence: `p7-005-db-field-readout.json`, read from the local database copies listed in `local-binaries-sha256.json`. It was missing from the first publication, as Codex noted.
- **`Project.db` file modified time** shows the same pattern, but also moves on page switches.
- **Per-timeline `Sm2Sequence.DbSavedTime`** is not a clean token. It bumps for the timeline being left, and edits to a non-current timeline landed on the current timeline's row.
- **Track locks** (`SetTrackLock`) blocked a UI Delete on a selected clip and refused `SetClipEnabled`. `SetClipColor` still succeeded.

## What is still NOT possible or established

1. **Atomic apply.** No revision token or transaction exists. A change in the instant between the final check and the apply cannot be excluded. The database-timestamp guard is undocumented and depends on Live Save. Locks do not cover every API setter.
2. **Proof of ancestry.** Cut/Paste destroys UIDs, and stamps and signatures can be copied or forged. Only a journal-plus-stamp rule with review on mismatch is available.
3. **Word-exact timing from Resolve.** Transcript words carry frame timecodes. Subtitle items are phrase segments. Sub-frame word edges must come from VERA's own alignment of the source transcript through the OTIO time map.
4. **Non-mutating timeline transcription.** `CreateSubtitlesFromAudio` writes a subtitle track and needs the Edit page. Run it on a duplicate timeline.
5. **Knowing which bytes a clip uses after a file change.** The viewer, stills, API status and a `True` relink return can all keep showing the old file. W6 showed even renders can. Only file hashes plus a render-based source check are trustworthy.
6. **Reading program silence from the mapping-mute flag.** It worked in one run and not in two others on the same build. Verify by render or subtitles.
7. **Visibility for transitions, Fusion and OpenFX.** These still need a render.
8. **Untested, so unknown rather than impossible:** bus mute, sends and routing, volume automation to silence, Fairlight FX, 29.97 fps, variable speed curves, and whether OTIO exports of a *non-current* timeline report Mute and Solo correctly.
9. **Settling the two Console-vs-Workflow-Integration conflicts** (mapping mute, relink) until the discriminating tests below are run.

## Phase 10 (Workflow Integration) outcomes

Codex ran these in project `VERA Issue 149 Workflow Reruns 20261002-kit-01` through the injected Workflow Integration object on Resolve 21.1.1.10 with External Scripting None. Each row links the full record on #149.

| Row | Result | Record |
| --- | --- | --- |
| W1 subtitles follow the edit | **Reproduced**: linked cut drops "charlie", picture-only keeps it, disabled A1 leaves numbers; subtitles and renders agree | [comment](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5963986370) |
| W2 Mute/Solo from OTIO | **Reproduced**: X A2 Mute renders without numbers, Y A2 Solo renders numbers only, OTIO flags agree, Solo-off restores baseline PCM | [comment](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5965021351) |
| W3 mapping mute | **Adverse**: flag set and read back, output unchanged (Deliver run and Edit-page repeat) | [comment](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5963821842), [repeat](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964195014) |
| W4 OTIO retime | **Reproduced** at 37.5%: scalar 0.375, 5/5 clicks within one sample. Link topology explains row 7 | [comment](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964033332) |
| W5 current-timeline getters | **Reproduced** | [comment](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964921838) |
| W6 replaced bytes and relink | **Adverse**: pre-relink render did not fail; relink returned True but output stayed source 1 | [comment](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964191971) |
| W7 lock guard | **Reproduced**: locked Delete Selected and `SetClipEnabled(False)` blocked; identities preserved | [comment](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964227757) |

## Open discrepancies and discriminating tests

Both adverse rows conflict with Console results on the same build, so version is ruled out as the sole cause. Each has a concrete procedural difference that a single test could settle. These are hypotheses, not explanations.

**W6: how the file was replaced.** The Console run overwrote the file in place with `cp`: same inode, new modified time. W6 used atomic `os.replace`: new inode, with the original modified time deliberately kept. If Resolve keeps an open handle to the old inode, it would go on reading the original bytes after an atomic replace, which matches W6. An in-place overwrite changes the bytes under that handle, which matches the Console decode failure. A same-path, same-mtime replacement may also look unchanged to `RelinkClips`.

- **Test:** in one fresh project, run the W6 sequence twice, once with `os.replace` and once with an in-place overwrite, holding the modified-time policy fixed. Render before and after relink each time.
- **Prediction if the hypothesis holds:** atomic replace keeps source 1 throughout; in-place overwrite fails before relink and switches to source 2 after.
- **Why it matters:** real editors and file-sync tools replace files both ways.

**W3: render order.** In the Console run, mapping mute was applied to a freshly built timeline that had never been rendered. In W3 a baseline render came first, both times. A render-side cache, or engine state that a clip-attribute change does not invalidate, would explain W3.

- **Test:** in one fresh project, (a) build a timeline, mute, render; (b) build, render a baseline, mute, render; (c) as (b), then save, close and reopen the project before rendering.
- **Prediction if the hypothesis holds:** (a) silent, (b) unchanged; (c) tells whether a reload clears the stale state.

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
