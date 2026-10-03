# Resolve 21.1 observation: limitations, failures and replication handoff

## Publication and control correction — acceptance remains pending

This PR publishes the retained native evidence and WI confirmations, with consistently aliased private paths, remapped links and lossless compression. See [publication guide](PUBLICATION.md) and [manifest](publication-manifest.json). The original local evidence is preserved; no new Resolve test was run. #149 remains accepted/Done. **#141 remains open for producer review of this published report.**

## Correction: automated and manual audio controls

**Plugin-proven automated silence control:** `TimelineItem.SetClipEnabled(False)` on the tested audio occurrence. On Studio **21.1.1.10**, Workflow Integration W1 disabled A1, read back disabled state, and generated subtitles/rendered output containing the A2 numbers without A1 NATO words ([W1 result](../issue-149/workflow-reruns/w1-result.md)). This is the bounded automation alternative to mapping mute.

**Manual controls:** W2's track Mute and Solo were set by the producer in Resolve's interface. Current-timeline OTIO flags and rendered output verified their effects, but this does not prove an automated setter ([W2 result](../issue-149/workflow-reruns/w2-result.md)). No documented `SetTrackMute` or `SetTrackSolo` setter was found in the installed scripting reference.

**Unverified through the plugin with output:** `Timeline.SetTrackEnable(trackType, trackIndex, enabled)` exists in the installed reference. Older #141 calls/readback are state evidence only; no retained WI setter→render test proves it silences the program. Do not assume equivalence to a person's Mute click or to Console behavior. VERA cannot currently offer it as a proven automated silence control. **No additional test was run for this correction.**

**Excluded control:** `SetSourceAudioChannelMapping` mute is unavailable as a VERA WI output control in the tested **21.1.1.10** contexts. It read back true without reducing the A2 pilot or removing number words; Claude's Console setter worked on the same-project comparisons. Internal cause remains unknown.

The [report’s supported operations, build lanes and individual #101–#104 mapping](report.md#positive-supported-envelope-for-144-and-145) supply the complete current envelope. Historical claims below apply only to their named test/build.

## Accepted #149 product decisions

The producer has accepted #149 and directed it to Done. Read the [current adopted decisions and complete owner/safe-behavior matrix](accepted-149-design-inputs.md) before interpreting the historical limitations below. File reload uses hash → changed modified time → relink → render verification. Mapping mute is excluded as a WI output control; use plugin-proven clip disable; Mute/Solo are manual and plugin track-enable output is unverified. Program words come from edited-mix transcription on a duplicate or verified render, with #146 coverage/freshness gates. #141 remains open for its separate producer sign-off. Historical #149 pending-review statements below describe earlier checkpoints.

Prepared for independent second-opinion testing of VERA Issue #141, 2026-10-02.

## Purpose and evidence status

This document gives another investigator the setup, operations, observed results, limitations, success requirements and focused follow-up experiments needed to challenge or reproduce this investigation. It describes **observing and reconciling human-edited timelines**, not a failure of Resolve's core timeline-authoring functions.

All 39 planned preparation/Resolve evidence checks were performed and independently reviewed. Report consolidation is complete; the final human External evidence review is still pending (40/41 dashboard entries). The producer-authored transcription experiment is supplemental and outside that denominator. No new Resolve test was performed to write this handoff. Proposed experiments below are **not yet run**. A completed observation may have an ambiguous result; “done” never means universal support.

### Classification to use when reviewing claims

| Classification | Meaning |
|---|---|
| Bounded support | The named operation was exercised and its retained result supports the stated narrow behavior. |
| Reproduced adverse behavior | The actual test returned an unexpected or insufficient result; identify the exact method, object and conditions. This does not establish a global capability absence. |
| Insufficient evidence / unproved | The observations do not establish the proposed inference. Missing tests must not be described as failed capabilities. |
| Unavailable in this collector | This collector/setup did not supply the requested evidence. Another API, different object, export or output experiment may resolve it. |
| Harness / launcher failure | Our code, assumptions, dispatch, selection, polling or restoration procedure failed/refused. Keep it separate from Resolve product behavior. |

**Main result:** the investigation did not reproduce a failure of core script-to-timeline authoring. It did establish reasons that a reconciler must not infer ancestry, audible speech deletion, general picture visibility, media byte identity or atomic freshness from incomplete metadata.

This handoff is self-contained for experiment design. Evidence links resolve in the original worktree and are necessary for auditing raw captures, exact metrics and source versions. If another AI receives only this Markdown file, it can construct fresh experiments from the procedures, but it cannot independently authenticate unavailable raw evidence. Do not pretend the linked files were read unless they are provided.

## Second-opinion update: Issue #149 (2026-10-02)

The independent [#149 verdicts](https://github.com/mbelinkie/vera-script-to-timeline/blob/claude/149-resolve-second-opinion/docs/investigations/issue-149/README.md), retained in [PR #150](https://github.com/mbelinkie/vera-script-to-timeline/pull/150), used Studio **21.1.1.10**, External Scripting None, and the Console-injected object. Its scripting stub hash is `2755259ef5f57b5d477786f799892e5b86ed3945db84bf88fb69bf751b36e651`, different from the original run. Historical #141 observations below remain evidence of their named build and setup; they are not a current capability catalogue. Producer-requested [W1–W7 Workflow Integration confirmation](https://github.com/mbelinkie/vera-script-to-timeline/blob/claude/149-resolve-second-opinion/docs/investigations/issue-149/codex-rerun.md) now has outcomes for all seven required rows. W1, W2, W4, W5 and W7 reproduce their named gates; W3 and W6 are adverse. Later TC/Out-mark drift stopped an extra neutral-X render, which remains unrun; that extension was not a required W2 pass criterion. The prior saved checkpoint and earlier output evidence are preserved. The [final seven-row summary](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5965027605) and [complete row-by-row reconciliation](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964283820) is posted on both issues. Neither issue is closed or accepted by this update.

| Earlier limitation | Updated interpretation from #149 |
|---|---|
| Timeline proxy `GetTranscription` returned `None` | **Superseded as a general edited-speech access limit.** `Timeline.CreateSubtitlesFromAudio()` on disposable duplicates supplied edited timeline words agreeing with named renders. It generates subtitles; it does not make the historical proxy getter return text. Workflow Integration W1 now confirms linked-cut, picture-only-cut and disabled-A1 cases with subtitle/render agreement ([posted result](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5963986370)). |
| Mute/Solo not available in the #141 collector | **Superseded for the tested track controls.** Current-timeline OTIO exports contain track `enabled` and `Resolve_OTIO.SoloOn`, supported by rendered controls. Bus routing and sends remain unproved. [Workflow Integration W2](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5965021351) confirms X Mute/no numbers, Y Solo/numbers only, then Y Solo-off/neutral export and baseline-equivalent output. [W5](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964921838) confirms the current/inactive getter context; select and verify the intended timeline before reading these controls. Extra neutral-X output remains unrun. |
| Active/inactive getter differences could look like changed stored audio state | **Explained and reproduced by W5.** X current reads [true,false,true]; querying X while Y is current reads allfalse without changing X’s stored state. The installed eight dialogue/voice keys are marked [Active Timeline Only]. Use verified current context; do not interpret inactive false as global silence. [W5 record](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964921838). |
| Getter rounding prevented exact fractional retime inference | **Superseded for tested constant speeds.** OTIO `LinearTimeWarp` and rendered clicks supplied exact constant timing. Workflow Integration W4 confirms scalar 0.375 and 5/5 rendered clicks within ±1 sample ([record](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964033332)). Arbitrary curves and other rates remain unproved. |
| Mapping mute getter changed but rendered PCM did not | **Unavailable as a VERA WI output control on the tested 21.1.1.10 setup.** Both the fresh never-rendered WI render and the [WI-mute/operator Console-render discriminator](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5970434832) retained all eight number words and 1500 Hz pilot 0.01986 despite mute:true. Prior baseline rendering is not necessary; moving only rendering to Console did not fix WI-applied mute. Claude’s [same-project Console-applied setter](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5971577666) was silent on a duplicate of Codex’s timeline and on a fresh timeline using Codex’s media. Use plugin-proven clip disable for automated silence; W2 Mute/Solo were manual, and SetTrackEnable output is unverified through WI. Do not use WI mapping mute to control program silence. The [Fairlight page-only variant](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5970657049) also retained pilot 0.01986 and all eight number words. All three requested WI-applied mute variants are adverse; each original mapping and restored output is verified. Moving rendering to Console or opening Fairlight alone did not remedy the flag/output discrepancy. No universal muting failure or internal deferred-update mechanism is established. |
| Speed change did not propagate to separately sourced linked audio | **Setup difference reproduced.** On 21.1.1.10 Workflow Integration, embedded linked A1 followed V1 to 37.5%; separately sourced, reciprocally linked A1 remained 100% after the V1-only setter. This supports separate source/link handling as the discriminator for these cases; no general version-causality claim. [W4 record](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964033332). |
| One nudge attempt had no effect | **No general capability limitation.** #141 already retained a successful +25 menu nudge; #149 retained a successful +1 menu nudge. The particular earlier no-op cause remains unknown. |
| Online/path/UID could not establish displayed byte replacement | **Still true as a metadata inference limit; prior reload discrepancy now explained for tested setups.** Both [October 3 Workflow Integration W6 discriminators](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5966033331) reproduced: atomic replacement with kept modified time rendered original source ID 1, while atomic replacement with modified time +1 second and `RelinkClips=True` rendered replacement source ID 2. Both original files/times and restored renders were verified. Bounded design input: content hash → changed modified time → relink → render verification. The old W6 adverse result remains a correct kept-time observation; no universal codec/cache guarantee is inferred. |
| Equal captures did not exclude ABA or establish atomic freshness | **Still a limitation.** #149 database-file modification time has false positives. Its retained `lmt: null` does not substantiate the proposed database field. Atomicity is not established. Workflow Integration [W7](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964227757) confirms the selected all-track lock guard for Delete Selected and SetClipEnabled(False), with exact structural preservation and restored locks; this is narrower than an atomic apply or protection from every API. |

All five later October 3 discriminators are now reviewed: two replacement cases reproduced and three WI mapping-mute variants adverse. See the [final complete result](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5970657049) and [#141 summary](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5970661013). The direct restored-output closeout and saved idle checkpoint are verified. No further native action is requested; #149 remains open for producer review.

## Navigation

- [Environment and original identities](#environment-original-identities-and-artifact-locations)
- [Independent reproduction setup and API protocol](#build-an-independent-disposable-reproduction)
- [R1: identity, lineage and copied metadata](#r1--identity-lineage-context-and-copypaste-metadata)
- [R2: audio, mute, Solo and transcripts](#r2--audio-timing-mute-solo-and-supplemental-transcripts)
- [R3: sampled picture visibility and structure](#r3-evidence-that-bounds-the-interpretation)
- [R4: availability, byte identity and occurrence removal](#r4--asset-availability-bytes-and-occurrence-removal)
- [R5: freshness and atomicity limits](#r5--freshness-stable-reads-and-aba)
- [Harness, launcher and recovery failures](#harness-launcher-and-recovery-failure-inventory)
- [What would count as a useful second opinion](#what-would-count-as-a-useful-second-opinion)
- [Complete original check inventory](#complete-original-check-inventory)

## Environment, original identities and artifact locations

| Item | Original run |
|---|---|
| Application | DaVinci Resolve **Studio 21.1.0 build 14** |
| Runtime | Injected CPython **3.14.7** |
| Host | macOS on an Intel Mac (producer-reported); this handoff does not claim an exact recorded OS/hardware revision |
| Scripting boundary | Operator-launched Workflow Integration with an injected `resolve` object; **External Scripting remained None**, supported by operator attestation, not a getter |
| Fixed menu automation | Hammerspoon with macOS Accessibility permission; exact app bundle, main-window title and named-menu guards |
| Resolve app bundle | `com.blackmagic-design.DaVinciResolve` |
| Branch | `codex/issue-141-resolve-observation` |
| Starting code baseline | `817d0e5ab76219fdc3df95b196f84fbad0382f0a` |
| Accepted injection reference | Issue #110, commit `22d86fa783c141b59f8631ba3020338c3368aa3e`; read without merging |
| Worktree | `REPOSITORY` |
| Original generated output | `out/issue-141-observation-20260930-01a0f318` relative to that worktree |
| Historical input manifest | `docs/investigations/issue-141/inputs/manifest.json` |
| Installed scripting docs | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/README.md` and `DaVinciResolveScript.pyi` |
| Installed-doc hashes recorded in manifest | README `5f58c94da8ec3c1f390d77ad9c60675263591dc101159b302e50b5774513830b`; stub `00078fa1256851b9807621a4eea5e670f4266b0e7003763cba4a62655543f0ec` |
| Synthetic tools | FFmpeg/FFprobe 8.1.2; macOS `say`, Alex voice at 200 words/minute; Python standard library and existing VERA slate writer; no new dependency |

Original object IDs identify retained evidence; a new project will produce different IDs. Discover and bind new IDs rather than copying them into a new experiment's assertions.

| Original object | UID |
|---|---|
| Project `VERA Issue 141 Synthetic Probe 20260930-01a0f318` | `97037b5a-aab6-48a9-b7e4-4c5697ae10a0` |
| `VERA 141 Baseline` | `88f7923d-55a7-471f-b09b-cf10f9fae8ad` |
| `VERA 141 R1 identity` | `aa2b8e36-83bd-4292-9e33-217c00ca192f` |
| `VERA 141 Batched Matrix` | `29ae8331-b86e-4041-a548-960695cc7b24` |
| `VERA 141 R4 availability` | `64de8a4c-86bd-4f19-9d20-47b8940f610b` |
| `transcription test 1` | `21436b8f-057c-49e6-80ba-5f733abe87b2` |
| `transcription test 2` | `2db0b2d1-6d81-48d4-b49c-360f56e012cd` |
| Final `VERA 141 R1 identity repeat` | `1835476c-8bc1-48fc-bb78-99906490480a` |
| Protected producer source `semi1b.mp4` | `be5f1584-f0c4-4dd9-988b-73f3167e77d1` |

The retained project now has **seven timelines**. The shared historical collector is configured for six and must not be replayed against this final state. No additional launch, save, render, cleanup, rename, deletion or native mutation is part of this handoff. Preserve baseline, stopped Copy/Paste content/metadata and producer transcript timelines. Original `semi1b.mp4` authorization covered metadata/transcription reads only: no byte reads/hash, export, retranscription or media edit.

Primary setup sources: [plan](../../plans/issue-141-resolve-observation.md), [successful baseline](evidence/baseline-preparation/summary.json), [collector](probe.py), [Workflow Integration entry](VERA%20Issue%20141%20Observation.py), [fixed launch helper](hammerspoon-launch.lua), [final seven-timeline review](../../../output/r1-final-seven-independent-review.json).

## Build an independent disposable reproduction

### Generated inputs and exact known support

Use a new disposable project and new generated inputs. Keep its identity, sources, outputs and controls separate from the retained project. To reproduce the original signal exactly, use the retained allowlisted generated files and verify their manifest hashes. Regenerating with a different speech voice or FFmpeg version can produce different bytes; measure a new manifest and waveform support rather than using the historical hashes or word endpoints.

The generator is [prepare-media.py](prepare-media.py). It accepts a **new absolute** repository `out/issue-141-media-*` directory and refuses an existing directory. It does not operate Resolve. Example for a new reproduction, **not executed for this handoff**:

```sh
cd 'REPOSITORY'
ctx-wire run rtk proxy /usr/local/bin/python3.14 -S \
  docs/investigations/issue-141/prepare-media.py \
  'REPOSITORY/out/issue-141-media-second-opinion-NEW-RUN-ID'
```

The generator synthesizes “echo,” converts it to mono signed 16-bit PCM at 48,000 Hz, and copies the same kernel four times into an eight-second file. Kernel starts are 19,200, 115,200, 211,200 and 307,200 samples. The actual nonzero support is measured after synthesis; it is a signal measurement, not ASR word alignment. It also generates a 110 Hz bed of amplitude 500 in signed 16-bit units, two different 640×360 slates, eight-second H.264/PCM MOVs at 25 fps, and a green RGBA PNG with alpha 0.5. `relink/base.mov` is a same-byte copy of `base.mov`; `wrong/base.mov` is a differently labeled `cutaway.mov` renamed to the same basename.

| Historical input | SHA-256 |
|---|---|
| `base.mov` / `relink/base.mov` | `c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942` |
| `cutaway.mov` / `wrong/base.mov` | `771b4bbbe771b980831e0a7b6d93ef11e1315cd995df22c5c7fbf7c2bf62c88b` |
| `repeated.wav` | `832dd31cc46b9f4b4fdb7cbde18b4edc09ec249885634fba43da2a7b87dc768e` |
| `bed.wav` | `f6da7ab4ffb4cc549e4b41e19da714097877b035abfb0235ac9bf94ea4860c02` |
| `overlay.png` | `071eb12b64238770244dead14fda01a0aeca3623f7962aab9edefa93b68d3140` |

Historical signal support, using half-open sample intervals:

| Word | Kernel interval | Nonzero interval |
|---|---|---|
| `echo-1` | `[19200, 36476)` | `[19210, 36258)` |
| `echo-2` | `[115200, 132476)` | `[115210, 132258)` |
| `echo-3` | `[211200, 228476)` | `[211210, 228258)` |
| `echo-4` | `[307200, 324476)` | `[307210, 324258)` |

At 25 fps and 48 kHz, one frame is 1,920 samples. Four copies of identical word bytes make correlation useful but do not establish their track/bus origin. Source manifest: [inputs/manifest.json](inputs/manifest.json).

### Baseline and 19-section Matrix

Use 25 fps timeline **and playback**, timecode `00:00:00:00`, 1920×1080 timeline resolution, 48 kHz audio, three video tracks and three mono audio tracks. The media slates themselves are 640×360. Journal actual supported setters/imports/append/link/marker requests, then inspect their readbacks. Playback frame rate was read-only in this setup and required operator preparation. Do not assume a requested append duration is the reported duration.

Each section has these six placements relative to its start `S`. These are **actual captured getter values**, not the original requested inclusive source ends:

| Track | Source | `GetStart` | `GetEnd` | `GetDuration` | Initial clip enabled | Initial link |
|---|---|---:|---:|---:|---|---|
| V1 | `base.mov` | S | S+199 | 199 | true | A1 |
| A1 | `repeated.wav` | S | S+199 | 199 | true | V1 |
| A2 | `repeated.wav` | S | S+199 | 199 | false | none |
| A3 | `bed.wav` | S | S+199 | 199 | true | none |
| V2 | `cutaway.mov` | S+50 | S+99 | 49 | false | none |
| V3 | `overlay.png` | S+75 | S+200 | 125 | false | none |

The V1/A1/A2/A3 requests asked for 200 frames; V2 asked for 50; V3 asked for 50 but the still image read back as 125. Preserve those differences before calibration. Later output calibration supports exclusive getter ends for the **named 100% speed integer cases**, not every timing mode or every input request convention.

| Section | S | Main tested action / sample coordinates |
|---|---:|---|
| calibration | 0 | marker note and linked one-frame move; initial endpoint/overlay calibration |
| R1-trim | 500 | linked end trim by 25 |
| R1-move | 1000 | linked record move +25 |
| R1-razor | 1500 | split linked pair at 1600 |
| R1-copy | 2000 | copy linked pair, paste at 2250 |
| R2-linked | 2500 | cuts at 2560/2570; non-ripple middle removal |
| R2-unlinked | 3000 | A1 cuts at 3060/3070; V1 retained |
| R2-picture-only | 3500 | V1 cuts at 3560/3570; A1 retained |
| R2-partial | 4000 | A1 cuts at 4065/4070 |
| R2-residual | 4500 | primary linked middle removal at 4560/4570; enable repeated-speech A2 |
| R2-offset | 5000 | unlinked A1 record move +1 |
| R2-retime | 5500 | linked V1 speed set to 50%; observe A1 separately |
| R3-opaque | 6000 | V2 sample local 49/50/98/99/100 |
| R3-transparent | 6500 | V3 sample local 75/198/199/200 |
| R3-effect | 7000 | Inspector Opacity 25; local 75/100 samples |
| R3-disabled-cutaway | 7500 | enable/disable V2 with local samples |
| R3-disabled-overlay | 8000 | enable/disable V3 with local samples |
| R3-Graphic | 8500 | linked V1/A1 split at 8600 beneath enabled V3 |
| R3-boundary | 9000 | authored marker at 9100; base split followed by A3 crossing-bed split |

The saved Matrix originally contained 114 placements. Case-start and occurrence markers/custom data identify authored test cases; they must not be assumed to be unique descendants after copying. R4 availability uses a separate isolated source/timeline. See [baseline preparation](evidence/baseline-preparation/summary.json), [matrix finalization](evidence/matrix-finalize-success/summary.json) and [editorial macro plan](editorial-macro-plan.md).

Original append requests used `MediaPool.AppendToTimeline([{mediaPoolItem: object, mediaType: 1|2, trackIndex: index, startFrame: 0, endFrame: requestedDuration-1, recordFrame: S+offset}])`, then `TimelineItem.SetClipEnabled`, occurrence `AddMarker`, and `Timeline.SetClipsLinked([V1,A1], True)`. `mediaType=1` is picture and `2` audio. The observed bounds in the table are the result of those specific requests. Reproduce the request and **observe** its result rather than silently replacing it with a different request that happens to yield the desired range. Baseline occurrence markers were Blue at local frame 0, duration 1, with JSON custom data `{issue:141, occurrence:index}`. Baseline also had an authored boundary marker at 100; the Matrix has its separate authored boundary at 9100.

### API entry and capture protocol

The verified entry was a Workflow Integration Python file invoked through `Workspace → Workflow Integrations → VERA Issue 141 Observation`. It reads the already-injected `resolve` object from its globals. The original launcher validates an absolute source path and SHA-256, records progress, disarms mutating actions to observation **before** invoking them, and retains a terminal result even after exceptions. It does not use an external `DaVinciResolveScript.scriptapp("Resolve")` fallback. A supplied scripting-preference configuration value is an attestation, not an API reading of the preference.

The installed launcher lives under `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/`; its configuration is `vera-issue-141-observation.json`. Relevant historical configuration keys are `probePath`, `probeSha256`, `projectName`, `externalScriptingSetting` (literal `None`), `action`, `mediaDir`, `outputDir`, `manifestSha256`, `stage`, and the applicable inventory/review bindings. Media/output directories are new absolute directories directly under this checkout's `out`, with prefixes `issue-141-media-` and `issue-141-observation-`. The project prefix is `VERA Issue 141 Synthetic Probe ` followed by a unique run identifier. The **actual attestation key enforced by `validate_config` is `externalScriptingSetting`**; historical installation records may separately describe the operator confirmation.

Many later helpers are checkpoint- and UID-pinned. They are retained experiment implementations, **not turnkey scripts for a differently named project**. An independent implementation must bind its own observed IDs, source hashes, inventory, selected context and before-state; pass its local comparison/refusal checks; and retain the exact revised helper source. Do not edit a pin or remove a guard solely to get a refusal to pass. A new project can use the same documented preparation calls and case geometry without reusing our historical checkpoint state machine.

Read APIs used by the core collector include:

- Resolve product/version/current page; project name/UID/settings and timeline inventory.
- Timeline name/UID/start/end/timecode/settings/markers; track count/name/enabled/locked, audio subtype; `GetItemListInTrack("video"|"audio", index)`.
- Occurrence `GetUniqueId`, `GetName`, `GetType`, `GetTrackTypeAndIndex`, `GetMarkers`, `GetProperties`, `GetSpeed`, `GetClipEnabled`, `GetSourceStartFrame`, `GetSourceEndFrame`, `GetSourceStartTime`, `GetSourceEndTime`, Fusion comp count/name list, source audio channel mapping, voice-isolation state, links and media-pool item.
- `GetStart`, `GetEnd`, `GetDuration`, `GetLeftOffset`, `GetRightOffset`, each with the default and `True` subframe argument.
- Media-pool item UID, clip properties, markers and audio mapping. Hashes only for allowlisted generated sources; the protected real-source locator was not opened.

The protocol stores **two complete adjacent observations**, each getter's raw value or error, the envelope timestamp/build/context, source verification, result consistency and content fingerprints. `None`, omitted keys and failed calls are distinct observations. The core capture refused unequal pairs as `inconsistent-refused`, or incomplete/error-bearing pairs as `incomplete-refused`. It explicitly retained `applicationRevisionToken: null`. Do not replace unknown values with defaults or treat equal reads as an application transaction.

For a fresh test:

1. Retain two stable complete baseline reads and the exact selected timeline, page, playhead, queue and relevant UI controls.
2. Bind the source/occurrence IDs and intended case-specific delta. Capture untouched timelines and the entire pool as well as the selected item.
3. Execute one operation and record invocation **before** dispatch, arguments, return value, journal and output references. A successful return alone is not success.
4. Retain complete post-action reads even if the expected-delta comparison refuses. Determine whether the action ran before any further operation.
5. Compare all fields, identifying expected Usage changes and context-sensitive values explicitly; do not discard unexplained fields merely to make a check pass.
6. Verify only the test's recorded temporary-context restoration separately. Preserve real editorial changes and failure evidence. Never repeat an uncertain mutation just because a wrapper failed or timed out.
7. Where the claim concerns program output, obtain the actual frame/PCM evidence and bind it to the exact observed state. Structure alone cannot prove visibility or audible omission.
8. Repeat on a fresh occurrence or fresh project, then test a controlled counterexample. Preserve raw captures, sources, scripts, SHA-256 bindings and independent interpretation.

Source: [probe.py](probe.py), [entry point](VERA%20Issue%20141%20Observation.py), [plan](../../plans/issue-141-resolve-observation.md).

### Exact menu actions and UI preconditions

The editorial tests used actual commands, not appended replacements pretending to be edits. [hammerspoon-editorial.lua](hammerspoon-editorial.lua) and [editorial-macro-plan.md](editorial-macro-plan.md) retain the dispatch guards and revisions. Menu paths in the tested installation:

| Purpose | Exact installed menu path |
|---|---|
| Launch injected observation | Workspace → Workflow Integrations → VERA Issue 141 Observation |
| Edit page | Workspace → Switch to Page → Edit |
| Start | Playback → Go To → Timeline Start |
| Deselect | Edit → Deselect All |
| Select nearest | Trim → Select Nearest → Clip/Gap |
| Split | Timeline → Split Clips |
| Trim end | Trim → Resize → End to Playhead |
| Move +1 | Trim → Nudge → One Frame Right |
| Copy / paste | Edit → Copy; Edit → Paste |
| Deterministic track Auto Select | Timeline → Auto Select → Auto Deselect All Tracks, followed by the named Auto Select V1/A1/A3 operations as applicable |
| One-frame playhead diagnostic | Playback → Step One → Frame Forward |

Locking other tracks was insufficient selection proof. `Select All Clips Under Playhead` selected additional locked-track clips; some nearest-selection attempts selected nothing. The investigation explicitly set Auto Select scope and required exact `GetSelectedClips` UID readback after selection and before each split/trim/nudge. Auto Select is UI context not attested by the complete data collector; menu tick fields were not reliable. Record commands and verify selected IDs. Hammerspoon focused Resolve and refused an unexpected app/project/window title or disabled menu. No arbitrary menu path, keyboard shortcut assumption or mouse-coordinate macro was used.

For another installation, first enumerate actual menu availability and confirm the object/selection context; do not assume these English menu labels exist unchanged. A disabled integration menu during rendering is an observation-path problem, not proof the render failed.

## Detailed results, limitations and success requirements

The following sections distinguish (a) reproducing the observed result, (b) what VERA needs before it can safely automate the corresponding inference, and (c) new experiments that could supply missing evidence.

## R1 — identity, lineage, context, and Copy/Paste metadata

### R1.1 Native timeline duplication: new occurrence IDs are normal creation, not ancestry proof

**Classification:** Supported bounded Timeline.DuplicateTimeline; lineage remains
ambiguous.

**Exact operation, state, and delta.** For the first native duplicate, the
reopened cache setting was restored through the probe's one SetSettings call
with a settings dictionary, followed by an equal-adjacent baseline pair. The
action then called Timeline.DuplicateTimeline("VERA 141 R1 identity") once on
the selected source timeline, passed the returned timeline handle through
Project.SetCurrentTimeline, and called SaveProject once.
The duplicate returned timeline UID
aa2b8e36-83bd-4292-9e33-217c00ca192f. Its six occurrence UIDs were disjoint
from the six baseline occurrence UIDs; the five distinct source-media UIDs
were shared. Track names, ranges, enable values, marker signatures and marker
custom data matched the source readback.

The source timeline's post-duplicate readback also changed all six track
enabled getters true -> false. Exact pool Usage changes were Video 1/2/3
1 -> 2, repeated.wav Audio 1/2 2 -> 4, and bed.wav Audio 3 1 -> 2. Eight
audio property keys were omitted on each of three audio items. The journal
contains no setter for those fields. They are retained raw observations, not
evidence of a track/effect edit or reset. The cache restoration, duplicate,
and saved readbacks had equal adjacent passes. The later standalone cache
restoration record is a different action: it called Project.SetSetting once
for perfCacheClipsLocation with a key/value and returned true; its postflight
matched the saved pin.

Evidence: [native duplicate review](evidence/native-duplicate-success/summary.json),
[reopen cache refusal](evidence/native-reopen-cache-refusal/summary.json), and
[cache restoration](evidence/cache-restoration-success/summary.json).

**Inference boundary and VERA requirement.** Disjoint IDs establish fresh
occurrence instances. Shared source IDs and matching signatures establish
copied shape/source association in this case. Neither proves that a duplicate
is the semantic descendant of a particular source occurrence, because copied
metadata and identical signatures are reproducible. A VERA identity decision
must retain the operation journal, source/occurrence IDs, source bytes or
verified artifact hashes, ranges, markers, and selected context separately;
it must refuse or request review when lineage is inferred only from name,
order, marker/custom-data equality, or signature equality.

**Known failures and limits.** The first close/reopen attempt stopped after
SaveProject/CloseProject because the current project ID changed; the guard did
not call LoadProject or duplicate an unexpected project. A duplicate-only
launch then refused because the exact project was not current. The manual
reopen readback differed only in project/timeline perfCacheClipsLocation
(CacheClip versus the owned path) and refused before duplication. A later
reopen had eight adjacent Usage changes and refused: timelines[0] tracks[0]
and [1] changed 2 -> 6; timeline[4] tracks[0], [1], [2], [3], [4], and [5]
changed 27 -> 28, 20 -> 21, 20 -> 21, 48 -> 50, 48 -> 50, and 21 -> 22.
Its stable follow-up showed eight Resolution leaves
changing 0x0 -> 1920x1080: two producer transcription proxy items, each with
one pool-item and one timeline-mapping leaf across two pool passes. None of
these refusals proves unsupported Resolve reopen or duplication, and the cache
path's resolved target was not inferred. Cache restoration ended
restored-to-saved-pin after one true setter and an exact postflight pair.

### R1.2 Razor, trim, and move: observed identity preservation is operation-specific

**Classification:** Supported bounded editorial observations; no general
lineage rule.

**Exact operations and deltas.** The approved native menu sequence selected the
reciprocal V1/A1 pair and called one Split Clips at frame 1600. The left
occurrence IDs remained and new right IDs were created; record ranges became
1500–1600 and 1600–1699, source ranges 0–100 and 100–199, reciprocal links and
markers were retained, and the expected source Usage +1 was the only other
modeled delta. One Trim -> Resize -> End to Playhead at frame 674 changed
each target's GetEnd 699 -> 674, GetDuration 199 -> 174, source end
199 -> 174, source end time 7.96 -> 6.96 seconds, and right offset 1 -> 26;
IDs, starts, source starts, links, markers and other state stayed equal. The
move driver sent 25 nudge-right menu actions, each followed by a complete
readback. Only target GetStart/GetEnd fields advanced one frame per action
(1000 -> 1025 and 1199 -> 1224); source bounds, IDs, markers, links and all
other content stayed fixed. Restoration changed only recorded secondary-track
locks and playhead; it did not save or undo the edit.

Evidence: [razor comparison](evidence/r1-razor-success/independent-comparison.json),
[trim evidence](evidence/r1-trim-success/), [move evidence](evidence/r1-move-success/),
and the dated [editorial report](report.md).

**GetEnd versus source geometry.** The matrix preparation used requested
AppendToTimeline endFrame = duration - 1 for the 200-frame generated clips.
That request convention and the later raw getter convention are separate
facts. The retained endpoint calibration applies only to named 100%-speed
integer cases: for those cases, the observed record GetEnd behaves as the
exclusive edge of the tested frame range. The synthetic getters can still
report record GetEnd = 199/duration = 199 while source getters report source
frames 0–199 and 7.96 seconds for the 200-frame input; source-bound getter
semantics remain recorded exactly as returned, not normalized. A 50% retime
also changed source end 199 -> 99 while record end/duration stayed 199. VERA
must store record start/end, source start/end, time values, offsets, speed and
subframe values as separate facts. It must not turn a GetEnd value into a
sample-exact word boundary or general endpoint convention. See the retained
[endpoint calibration review](../../../out/issue-141-observation-20260930-01a0f318/endpoint-calibration-independent-verdict.json)
and [R1 report details](report.md).

**Limits.** These are one synthetic split, one trim, and one 25-frame move.
They do not prove arbitrary movement, semantic section boundaries, sample-
exact audio edits, rendered output, or ancestry of either split half. A copied
marker can exist on both halves, so marker equality is not a unique binding.

### R1.3 Genuine Copy/Paste: copied metadata and four Out changes are retained as drift

**Classification:** Supported bounded Copy/Paste; metadata/meaning ambiguous;
the strict guard correctly stopped on an unexplained modeled delta.

**Exact operation, state, and delta.** From the verified Edit state, the native
menu sequence selected the pinned V1/A1 pair, called Copy once, moved the
playhead to frame 2250, then called Paste once. It returned new V1/A1
occurrence IDs 7dc4a98b-33cb-4feb-9727-b2bca434138e and
a9175c87-6bc0-4c07-a167-3b7c9de70fba. Both had record bounds 2250–2449,
source bounds 0–199, reciprocal links, and inherited marker/custom data;
source Usage +1 was observed. The original occurrences remained.

The complete-pair guard then stopped on exactly four Matrix pool leaves. In
both pool passes, these paths changed from 00:00:08:00 to empty:
poolPasses[0]/items[7]/evidence/GetClipProperty/value/Out,
poolPasses[0]/timelineMappings[2]/poolItemProperties/value/Out,
poolPasses[1]/items[7]/evidence/GetClipProperty/value/Out, and
poolPasses[1]/timelineMappings[2]/poolItemProperties/value/Out. The stopped
review found no other timeline/pool/byte delta. No undo, cleanup, save,
render, retry, or automatic context restoration followed. The copied clips
and the four Out changes remain retained evidence.

Evidence: [Copy/Paste delta review](../../../out/issue-141-observation-20260930-01a0f318/r1-copy-paste-delta-review.json),
[stopped Copy/Paste evidence index](evidence/r1-copy-paste-stopped/evidence-index.json),
[copy restoration review](evidence/r1-copy-paste-stopped/r1-copy-restore-review.json),
and [report entry](report.md).

**Inference boundary and VERA requirement.** New reciprocal IDs and an actual
Copy/Paste journal support a copied-occurrence classification. Inherited
markers/custom data do not prove ancestry or unique semantic binding. The
four Out changes have unknown render-range significance; VERA must preserve
them as an explicit unresolved delta and block automatic apply where their
meaning matters. It must not normalize them away or call the output
correct/incorrect without an output check.

**Known failures.** The first Copy/Paste launch refused its Edit/known-format/
empty-queue preflight while Resolve was on Deliver; no copy occurred. An
earlier selection reader expected a dictionary although the installed API
returned a list, and a local snapshot path check was corrected before the
native paste. These are harness/preparation issues, not capability findings.

### R1.4 Selected context and final duplicate: projection is a comparison aid, not state evidence

**Classification:** Supported bounded context dependence and final duplicate;
context-sensitive getters remain unknown for semantic interpretation.

**Exact observations.** Selecting R1 changed 60 raw fields relative to the
Matrix-selected pair: 12 track-enabled values and 48 presences of exactly
these eight audio properties: AudioDialogueLevelerBackgroundReduction,
AudioDialogueLevelerEnabled, AudioDialogueLevelerLiftSoftDialogue,
AudioDialogueLevelerMode, AudioDialogueLevelerOutputGain,
AudioDialogueLevelerReduceLoudDialogue, AudioVoiceIsolationAmount, and
AudioVoiceIsolationEnabled. IDs, geometry, markers, links, source metadata,
settings, Usage, and all other structural fields were equal. The local
repair projects out both track enabled/locked getters, Usage, and the eight
named audio properties from its cross-context signature, keeps every raw field,
and still rejects changed IDs, source bounds, record bounds, clip enablement,
markers, or an unlisted audio property. The
initial native duplicate stopped before mutation on the context mismatch. One
Project.SetCurrentTimeline restoration received the Matrix timeline handle,
returned true, and produced an exact stable six-timeline/pool pair.

The final native sequence called Timeline.DuplicateTimeline exactly once from
the selected R1 source and restored Matrix selection by passing the Matrix
timeline handle through Project.SetCurrentTimeline. It created
VERA 141 R1 identity repeat (timeline UID
1835476c-8bc1-48fc-bb78-99906490480a) with six new occurrence IDs disjoint
from every original occurrence. Source/signature multisets matched; original
six non-Usage fields and original pool non-Usage fields were preserved. The
review measured Usage changes on five original pool media items, 142 timeline
Usage paths across four timelines, and exactly one new duplicate pool proxy plus
one new timeline mapping. All Usage paths ended in Usage; no unknown unrelated
delta was found. The final Matrix context equaled its checkpoint. No save,
render, cleanup, or further native action followed.

Recovery status: selection restoration is PASS with exactly one native
Project.SetCurrentTimeline call receiving the Matrix timeline handle, exact
pair/context equality, and no save, render, clip, lock, or playhead mutation.
The final seven-timeline review is
PASS_WITH_EXPLICIT_LINEAGE_LIMIT; its terminal action is the one duplicate.

Evidence: [selected-context review](../../../output/r1-selected-context-independent-review.json),
[native restoration review](../../../output/r1-selection-restoration-native-independent-review.json),
[final seven-timeline review](../../../output/r1-final-seven-independent-review.json),
and [final reopen review](../../../output/r1-reopen-final-independent-review.json).

**Required interpretation.** The projection is only a context-normalized
comparison over a retained raw capture. The helper's structural signature pops
both track GetIsTrackEnabled/GetIsTrackLocked fields, Usage, and the eight
named audio properties; the independent comparison still reports the actual
cross-context delta as 12 enabled values, 0 locked values, and 48 audio-key
presence differences. It does not prove the underlying track enabled/locked
state, audio effects state, mute state, or speech state; missing context keys
and getter failures remain unknown. VERA must bind every control/effect
observation to the same selected timeline and a fresh complete pair, retaining
raw fields and errors. It may project only these exact reviewed context fields,
never arbitrary missing or failed getters.

**Known failures.** The first restoration launch stopped before integration
menu selection because the main window was unavailable; the later read-only
window check supplied availability and one guarded restoration succeeded. The
prior refusal remains terminal evidence. The final duplicate review did not
rerun the old shared six-timeline collector, reopen, save, or render.

## R2 — audio, timing, mute, Solo and supplemental transcripts

### Retained evidence and replication map

The consolidated findings and chronology are [final-findings.md](final-findings.md) and [report.md](report.md). The primary R2 artifacts are:

- [audio-cases-success/summary.json](evidence/audio-cases-success/summary.json): 14 equal-adjacent capture points, all six native reversible state cases, setter calls, retime fields, and limits.
- [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json): independent review of the terminal generated render, full-pair binding, six case findings, and exact PCM metrics.
- [pcm-real-render-analysis.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-real-render-analysis.json): source-support comparisons and output sample bindings.
- [endpoint-calibration-independent-verdict.json](../../../out/issue-141-observation-20260930-01a0f318/endpoint-calibration-independent-verdict.json) and [endpoint-calibration-corrected-review.json](../../../out/issue-141-observation-20260930-01a0f318/endpoint-calibration-corrected-review.json): the distinguishing 100% endpoint result and its scope.
- [mute-pcm-comparison-result.json](../../../out/issue-141-observation-20260930-01a0f318/mute-pcm-comparison-result.json): held mapping-mute output versus the unmuted baseline.
- [cli-mute-native-once-result-reviewed.json](../../../out/issue-141-observation-20260930-01a0f318/cli-mute-native-once-result-reviewed.json) and [audio-mapping-restore-summary.json](../../../out/issue-141-observation-20260930-01a0f318/audio-mapping-restore-summary.json): native mapping mutation, restoration, first post-render refusal, and exact final pair.
- [solo-output-comparison-result.json](../../../out/issue-141-observation-20260930-01a0f318/solo-output-comparison-result.json), [fairlight-operator-solo-on.json](../../../out/issue-141-observation-20260930-01a0f318/fairlight-operator-solo-on.json), and [solo-off-restored-state-20261002T121158.440922Z.json](../../../out/issue-141-observation-20260930-01a0f318/solo-off-restored-state-20261002T121158.440922Z.json): the bounded Solo output, operator state, and restoration evidence.
- [r1-fairlight-api-doc-audit.json](../../../output/r1-fairlight-api-doc-audit.json): installed README/stub search for mapping, Solo, and bus/output APIs.
- producer-transcript-probe.py (protected raw source transcript withheld; approved derived comparison is in the published run), [producer-transcript-range-comparison.json](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-range-comparison.json), and [producer-transcript-range-independent-review.json](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-range-independent-review.json): exact getter calls, source words/times, occurrence geometry, derived comparison, and independent limits.
- [transcription-readback.py](transcription-readback.py) and [transcript-coverage-requirement.md](transcript-coverage-requirement.md): the separate read-only source/proxy readback and the adopted future coverage/freshness requirement.

The terminal full-Matrix render used by the R2 review was one owned job, job ID a6ed7f33-9ad4-4d82-bfac-ff72903f4567, with one StartRendering request and a later same-job completion observation. The native MOV hash was 8af6fb6916afa4c1bc674617ad52460928582a3dbc22dd2af8550786bd28020c. Its extracted PCM was PCM24 stereo, 48 kHz, 17,664,000 sample frames per channel, 368 seconds, hash d2581dc047a348a104821cbd53c7b84e4a47b80fd4443ebf52f6fbd3382362a. The generated repeated.wav comparator source was PCM16 mono, 48 kHz, 384,000 samples, hash 832dd31cc46b9f4b4fdb7cbde18b4edc09ec249885634fba43da2a7b87dc768e. No protected presenter-media bytes were opened or hashed.

### Exact GetTranscription object and method distinction

The retained producer probe did not read a property named transcription and did not call GetTranscription on a Timeline or TimelineItem. It used method dispatch equivalent to:

    _call(item, "GetTranscription", nested)

for nested equal to False and True, with two adjacent reads per mode. The implementation is visible in [producer-transcript-probe.py](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-probe.py:207) and the target loop at [producer-transcript-probe.py](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-probe.py:613).

The installed DaVinciResolveScript.pyi does define MediaPoolItem.GetTranscription(useNestedClipTranscription=False) -> Transcription at lines 2098–2100. The same stub defines Timeline.GetMediaPoolItem() -> MediaPoolItem at lines 2272–2273 and TimelineItem.GetMediaPoolItem() -> MediaPoolItem at lines 2353–2354, but it does not define TimelineItem.GetTranscription. The installed README search retained in [r1-fairlight-api-doc-audit.json](../../../output/r1-fairlight-api-doc-audit.json) did not find a GetTranscription entry; the stub is the authoritative retained type declaration for this method search.

The probe used these distinct objects:

- **Source MediaPoolItem:** it selected the unique source handle returned by TimelineItem.GetMediaPoolItem() from the video/audio occurrences in the two named timelines. This source was semi1b.mp4, UID be5f1584-f0c4-4dd9-988b-73f3167e77d1. Calling GetTranscription(False) and GetTranscription(True) on that MediaPoolItem returned stable word-level data on both adjacent reads.
- **Timeline pool proxy MediaPoolItem:** for each named timeline, it called Timeline.GetMediaPoolItem(), then called GetTranscription(False/True) on the returned MediaPoolItem proxy. Both proxies returned a successful call with value None on both reads in both modes. The retained state is value/missing, getterMissing false, equal-adjacent-reads; it is not a thrown missing-method error.
- **Timeline and TimelineItem:** these objects supplied timeline identity, occurrence lists, source identity, track, record/source bounds, speed, and enabled state. Their GetMediaPoolItem() methods supplied the MediaPoolItem handles above. No claim was made that a TimelineItem itself has a direct transcript getter.

This is the exact observed distinction: source-level MediaPoolItem transcription was present; the two timeline-level pool-proxy MediaPoolItem transcriptions were null. It is evidence for these two proxies in this project/build/readback, not a global Resolve API absence claim. The source-item loop can return the same complete source transcript for both pieces of test 2, including words excluded by the edit; cut-aware reconstruction must intersect that source transcript with each enabled audio occurrence's source range.

### R2 native cases and rendered PCM

The generated Matrix is 25 fps with 48,000 Hz audio, so one timeline frame is 1,920 samples. The comparer uses half-open source-support windows, zero-mean-free normalized waveform correlation, coarse lag step 32 samples, maximum lag ±1,920 samples, and a strong-correlation threshold of 0.8. The four repeated.wav supports are [19210,36258), [115210,132258), [211210,228258), and [307210,324258), each 17,048 samples.

The native audio-cases action retained 14 equal-adjacent state captures and returned true from every named setter. These six reversible native setter transitions are separate from the six physical geometry/output cases in the table; native setter acceptance and readback do not themselves establish an editorial cut or rendered output:

- SetClipEnabled(true), then SetClipEnabled(false).
- SetTrackEnable("audio", 2, false), then SetTrackEnable("audio", 2, true).
- SetSpeed({Percentage: 50.0, PitchCorrection: true, RippleTimeline: false}), then the same with Percentage 100.0.

The final post-sequence pair equals the saved Matrix pin. This is cleanup/readback evidence for the native sequence; it does not mean deleted physical intervals were re-added to the terminal Matrix render. These return values establish setter acceptance and readback transitions; the PCM findings below came from the separately owned terminal output and generated-only analysis.

| Case | Physical geometry and temporary context/state restoration | Rendered PCM observation | Bounded interpretation |
|---|---|---|---|
| Linked cut | Linked V1/A1 middle interval [2560,2570), source [60,70), non-ripple DeleteClips returned true; the named linked middle items were removed for the terminal Matrix geometry, and temporary locks/playhead/selection/context were restored afterward. The physical gap remained in that render. | Expected second support [115210,132258) at record [2560,2570) had score 0.08115, gain 0.00467, rendered energy 0.9946, versus source-support energy 300.5012, peak 0.73871, RMS 0.13277. The 19,200-sample gap had energy 1.1203, peak 0.01080, RMS 0.00764. Neighbor supports scored 0.99836 at zero lag and gain 1.0021. | The named generated support is absent or near noise in the known cut interval. This is not universal speech deletion, routing, or audibility evidence. |
| Unlinked cut | A1-only interval [3060,3070), source [60,70), non-ripple DeleteClips returned true; V1 remained unchanged. Temporary locks/playhead/selection/context were restored afterward; the physical A1 gap remained in the terminal Matrix render. | The same second-support metrics apply at record [3060,3070): score 0.08115, gain 0.00467, gap energy 1.1203 versus source 300.5012; neighbor controls score 0.99836 at zero lag and gain 1.0021. | The named unlinked physical cut and its bounded output observation are supported. PCM does not establish link-state behavior outside this case or prove deletion in general. |
| Picture-only | Picture V1 interval [3560,3570) was removed while the A1 audio item remained continuous over the case; temporary locks/playhead/selection/context checks passed, while the physical picture removal remained in the Matrix render. | The [115210,132258) support crossing the picture interval scored 0.99836 at zero lag and gain 1.0021; window energy 302.883, RMS 0.12560, peak 0.74392. | Removing picture alone did not remove the named generated audio support. Do not infer spoken deletion from a picture cut. |
| Partial | A1 source pieces [0,65) and [70,199) remained at record [4000,4065) and [4070,4199); source [65,70) was the deleted gap, which remained physically present in the Matrix render. Temporary locks/playhead/selection/context were restored afterward. | Head support [115210,124800) (9,590 samples) scored 0.99843 at zero lag and gain 1.00095. The full expected comparison was score 0.80095, gain 0.64435, rendered energy 194.480, residual 69.717 because the tail through 132258 was absent from the compared item window. The gap [4065,4070) was 9,600 samples with energy 0.56015, RMS 0.00764, peak 0.01080. | The retained head and missing tail are bounded observations. A partial word/range overlap is not a whole-word deletion claim. |
| Residual | A1 middle interval [4560,4570) was deleted for the test and its physical gap remained; a separate enabled synthetic A2 item remained enabled for the terminal render and covers the same speech support on audio track 2. Temporary locks/playhead/selection/context were restored afterward. | The A1 gap window [4560,4570) still had program energy 152.621, RMS 0.08916, peak 0.52817. The enabled A2 support [115210,132258) scored 0.99674 at zero lag and gain 0.71004, residual energy 0.99212. | Residual speech-like generated signal is observed while A1 has a gap. Correlation does not identify bus/track origin or prove human audibility. |
| One-frame offset | The unlinked A1 item moved from raw record endpoints `5000..5199` to `5001..5200` in the retained description, with source bounds unchanged; temporary locks/playhead/selection/context were restored afterward, while the record move remained in the observed Matrix output. | At support [19210,36258), frame 5001 alignment scored 0.99835 at zero lag and gain 0.99585. The frame-5000 prediction had a +1,920-sample best lag with the same score/gain. Diagnostic frame [5000,5001) energy was 0.11290, peak 0.01080. | The current output aligns with the moved record position. This is not a before/after render comparison and does not generalize to arbitrary offsets. |

The independent review is [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json). It explicitly labels the comparison waveform-only: it does not establish source origin, routing, deletion, final audibility, or a universal speech rule.

#### R2 timing and retime observations

The 50% R2 retime setter returned true; this state-only retime was restored to 100%. For the named V1 retime item, retained fields changed from GetRightOffset 1 to 201, GetSourceEndFrame 199 to 99, GetSourceEndTime 7.96 to 4.0, and GetSpeed Percentage 100.0 to 50.0 while PitchCorrection stayed true. The linked A1 changed-field list was empty. This is a statement about the captured V1 and A1 readbacks; it is not a broad conclusion about all linked clips.

The corrected unlinked-cut review also retained an observed schema difference: after unlinking, the target video GetSpeed value omitted the PitchCorrection key that had been true in the prior pair. The review preserved that omission exactly. It is a getter/readback representation difference, not evidence that pitch correction was reset.

### Endpoint calibration

The independently verified calibration is limited to generated 100% speed integer-valued cases:

- The generated 100% audio tail reports GetStart 9100, GetEnd 9199, GetDuration 99, GetSourceStartFrame 100, and GetSourceEndFrame 199. Integer and float overloads agree for these integer-valued observations.
- Rendered timeline frame 9198 is nonzero and correlates to generated source frame 198. Timeline frame 9199 is exactly silent even though generated source frame 199 is nonzero. This supports an exclusive upper end for this named audio item.
- The rendered output is 9,200 timeline frames and 17,664,000 samples per channel, which verifies whole-output rate/duration arithmetic only.
- The retained 50% capture reports source end frame 99 and source end time 4.0. That pair does not establish a universal frame-to-time convention; the 50% readback is raw observation only.

Fractional start/end/duration, generalized retime endpoints, alternate frame rates, effects, and other Resolve getters remain untested. Preserve GetStart, GetEnd, GetDuration, source frame fields, source time fields, and render MarkOut as separate raw observations.

### Mapping mute: native setter versus final output

The mute operation targeted the generated residual A2 TimelineItem UID f4e9f649-894a-42f2-9f54-a8321ae7c163 on Audio 2 over [4500,4699), source repeated.wav. The operation used TimelineItem.SetSourceAudioChannelMapping with the exact JSON mapping:

    {"embedded_audio_channels":1,"linked_audio":{},"track_mapping":{"1":{"channel_idx":[1],"mute":true,"type":"mono"}}}

The pre-mutation and restored JSON had mute false. Both native setter calls returned true. The before pair and restored pair have the same SHA-256 d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14; the held muted pair differed only at the target mapping. The pool-level GetAudioMapping and TimelineItem-level GetSourceAudioChannelMapping getters were successful for the retained mapping review, but these are source-channel mapping/clip-attribute observations, not Fairlight track or bus state.

The held-mute render completed as job c5b1925b-f5aa-49d5-850a-be7a64c5cd29. Its extracted PCM SHA-256 was exactly the same as the unmuted baseline: d2581dc047a348a104821cbd53c7b84e4a47b80fd4443ebf52f6fbd3382362a. Both channels were byte-identical for the entire 17,664,000-sample output, including target [4500,4699), speech-gap [4560,4570), and frame 4570. The gap's baseline/held RMS was 0.0891571253533794; different samples were zero.

This is a reproduced limitation of treating the observed mapping mute flag as proof of program silence in this case. It is not evidence of universal API failure. After the render, one restoration preflight refused because Resolve was on the render page; one approved Edit-page action made the same exact mapping restoration possible, and the final pair matched the original. The refusal and successful restore are retained in [audio-mapping-restore-summary.json](../../../out/issue-141-observation-20260930-01a0f318/audio-mapping-restore-summary.json).

### Fairlight Solo and output comparison

The operator reported that A1, A2, and A3 initially had Mute and Solo off, then turned A2 Solo on. Output/bus labels were not visible. The operator-held state is retained in [fairlight-operator-solo-on.json](../../../out/issue-141-observation-20260930-01a0f318/fairlight-operator-solo-on.json); the API pair did not contain a Solo field.

The completed Solo render was not a second start: the queue setup issued no start, the separately authorized render issued exactly one StartRendering request, and the same owned job was later observed Complete/100% without replay. The generated output was PCM24 stereo 48 kHz. The bounded controls were:

| Control | Record frames | PCM samples | Baseline | A2-Solo output |
|---|---:|---:|---|---|
| A1-only speech | [2260,2269) | [4339210,4356258) | Per-channel peak 0.73870850, RMS 0.13276585 | Peak 0, RMS 0 |
| A2 speech plus A3 bed | [4560,4569) | [8755210,8772258) | Peak 0.52817225, RMS 0.09457784 | Peak 0.52296555, RMS 0.09399102; all four repeated.wav supports score approximately 1.0 at zero lag and gain 0.70794576 |
| A3-only track control | [4065,4070) | [7804800,7814400) | Peak 0.01080239, RMS 0.00763862 | Peak 0, RMS 0; this is energy only, not bed.wav correlation |

Whole-program RMS changed from 0.03788207 to 0.00583994, with 7,323,819 differing samples per channel. These observations are consistent with the operator-reported A2 Solo state retaining A2 support and excluding the named A1/A3 controls. They demonstrate a bounded Solo-sensitive rendered result on this build. They do not prove complete routing, bus origin, live monitoring audibility, spoken deletion, or lineage.

The installed README/stub audit found documented MediaPoolItem.GetAudioMapping, MediaPoolItem.SetAudioMapping, TimelineItem.GetSourceAudioChannelMapping, and TimelineItem.SetSourceAudioChannelMapping. The searched documents did not contain a matching public Fairlight Solo or bus/output-routing getter. That search is limited to those installed documents and is not proof of global API absence. The collector also cannot distinguish Solo state in an otherwise equal pair.

The producer later reported exactly “solo off” and requested A2 Solo off plus M/S off on A1–A3. One fixed Edit-page action and one fresh read-only capture followed. The fresh pair and post-selection pair both equal d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14, with idle renderer, empty queue, playhead zero, and protected state unchanged. Solo/M/S state remains operator evidence; the readback does not attest those controls.

### Supplemental transcript experiment

The first native transcript launch succeeded at the menu boundary but failed before transcript or occurrence-geometry getters with AttributeError: NoneType has no attribute __name__. The private configuration was restored; no transcript, edit, save, render, export, or source-file read followed. This was a probe serialization failure, not a Resolve capability result. The retained dispatch review is [producer-transcript-dispatch-review.json](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-dispatch-review.json).

After the local serializer repair, the one-shot read-only probe completed with unchanged project/timeline/page. Source semi1b.mp4 returned stable word-level transcription in both GetTranscription modes. The two timeline pool-proxy MediaPoolItems returned null in both modes on both reads. The source metadata retained FPS 29.97 and Start TC 14:57:30;11.

The producer accepted the following complete wording after correcting the supplied expectation:

**Test 1 — 22 source-aligned words:**  
Accepted wording: “KAJ is three Finns singing in Swedish, playing up the stereotypes that Swedes have for Finns. Specifically, that Finns really like saunas.”  
Observed source transcript: “Kai is three Finns singing in Swedish, playing out the stereotypes that Swedes have for Finns. Specifically, that Finns really like saunas.”

**Test 2 — 19 source-aligned words:**  
Accepted wording: “KAJ is three Finns playing up the stereotypes that Swedes have for Finns. Specifically, that Finns really like saunas.”  
Observed source transcript: “Kai is three Finns playing out the stereotypes that Swedes have for Finns. Specifically, that Finns really like saunas.”

Kai is accepted as the spoken form of KAJ. Specifically is correct; the remaining lexical variance is the minor producer-intended up versus observed out difference. Test 2 omits exactly singing, in, and Swedish from its selected source ranges.

#### Exact retained source-word labels

The following table transcribes the 22 selected source-word records in [producer-transcript-range-comparison.json](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-range-comparison.json). Starts/ends are the original `HH:MM:SS;FF` source timecode labels, with retained source metadata 29.97 fps and start TC `14:57:30;11`. They are not zero-based timeline seconds or sample timestamps. No timestamp normalization is performed here; the approximately two-source-frame mapping uncertainty above still applies. Inclusion describes the source-range reconstruction, not a direct timeline transcript getter or rendered audibility. The older comparison's expected-token fields predate the producer correction; the corrected accepted wording above governs the lexical verdict.

| # | Observed word | Source start label | Source end label | Test 1 | Test 2 |
|---|---|---|---|---|---|
| 1 | Kai | `14:57:59;01` | `14:57:59;15` | Included | Included |
| 2 | is | `14:57:59;15` | `14:57:59;24` | Included | Included |
| 3 | three | `14:57:59;24` | `14:58:00;04` | Included | Included |
| 4 | Finns | `14:58:00;04` | `14:58:00;21` | Included | Included |
| 5 | singing | `14:58:00;24` | `14:58:01;07` | Included | Omitted |
| 6 | in | `14:58:01;07` | `14:58:01;12` | Included | Omitted |
| 7 | Swedish, | `14:58:01;12` | `14:58:02;02` | Included | Omitted |
| 8 | playing | `14:58:02;07` | `14:58:02;17` | Included | Included |
| 9 | out | `14:58:02;17` | `14:58:02;21` | Included | Included |
| 10 | the | `14:58:02;21` | `14:58:02;23` | Included | Included |
| 11 | stereotypes | `14:58:02;23` | `14:58:03;13` | Included | Included |
| 12 | that | `14:58:03;13` | `14:58:03;18` | Included | Included |
| 13 | Swedes | `14:58:03;18` | `14:58:04;02` | Included | Included |
| 14 | have | `14:58:04;02` | `14:58:04;10` | Included | Included |
| 15 | for | `14:58:04;10` | `14:58:04;15` | Included | Included |
| 16 | Finns. | `14:58:04;15` | `14:58:05;04` | Included | Included |
| 17 | Specifically, | `14:58:05;09` | `14:58:06;00` | Included | Included |
| 18 | that | `14:58:06;00` | `14:58:06;07` | Included | Included |
| 19 | Finns | `14:58:06;07` | `14:58:06;18` | Included | Included |
| 20 | really | `14:58:06;19` | `14:58:07;02` | Included | Included |
| 21 | like | `14:58:07;02` | `14:58:07;15` | Included | Included |
| 22 | saunas. | `14:58:07;16` | `14:58:08;12` | Included | Included |

The exact occurrence geometry is:

| Timeline | Enabled audio occurrence(s) | Source-aligned words |
|---|---|---:|
| transcription test 1, UID 21436b8f-057c-49e6-80ba-5f733abe87b2 | Timeline [90000,90255), source [841,1147), 100% speed | 22 |
| transcription test 2, UID 2db0b2d1-6d81-48d4-b49c-360f56e012cd | Timeline [90000,90059), source [841,912), then timeline [90059,90220), source [954,1147), both 100% speed | 19 |

At nominal 29.97 fps, source timing and occurrence geometry agree within about 1.6 source frames. Test 2's first range ends 0.874 frames after the retained Finns word end and 2.126 frames before singing starts. Its second range starts 2.091 frames after Swedish ends. The retained source-range mapping is internally consistent and producer-accepted, but approximately two-frame endpoint uncertainty means edge clipping cannot be ruled out. No direct timeline-proxy transcript was returned, and source transcript plus enabled ranges do not prove final-mix audibility.

The proposed source loop has a specific consequence: TimelineItem.GetMediaPoolItem().GetTranscription() reads the source MediaPoolItem transcription, so both test-2 pieces can return the same complete source data, including omitted words. A video-track-only loop also misses audio-only occurrences and does not account for disabled state, mapping mute, Fairlight routing, repeated use, or speed. VERA must preserve source transcript, timeline occurrence, and timeline-proxy results as separate evidence.

### Known limitations and retained failures

Each item below states how to reproduce the observation, what would be required to call it successful for VERA, and an explicitly unrun experiment. “Unrun” means proposed only; it was not performed for this handoff.

#### 1. Mapping mute did not change program PCM

- **Classification:** Reproduced bounded output limitation; native mapping mutation succeeded, program-output mute did not follow in this case.
- **Setup/action/observation:** On the generated residual A2 TimelineItem over [4500,4699), call SetSourceAudioChannelMapping with track 1 mute true, require true return and target-only pair delta, render the held state, extract PCM, and compare with the unmuted baseline. The complete waveform was byte-identical, including the target and speech-gap windows.
- **Requirement to claim success:** VERA may call a mute effective only after it binds the correct layer (source mapping, clip, track, or bus) and observes the intended output change in a controlled render or an equivalent verified output path, followed by exact restoration.
- **VERA consequence:** Mapping mute alone cannot classify speech as absent and cannot authorize spoken-omission reconciliation. Route-ambiguous cases require stronger output evidence or manual review.
- **Proposed unrun experiment:** On a fresh generated-only matrix, compare source mapping mute, TimelineItem clip enable, track enable, and a producer-confirmed Fairlight track/bus mute one at a time, with isolated source and output controls. No such experiment is authorized or run here.

#### 2. Fairlight Solo and bus routing are collector gaps

- **Classification:** Bounded successful Solo-sensitive output with unresolved state/routing attribution; documentation search gap, not a global API absence.
- **Setup/action/observation:** Operator reported A2 Solo on; bus labels were not visible. One owned full-Matrix render retained zero A1/A3 control output and near-unit A2 source correlation. The full-pair collector and installed docs/stub exposed no Solo or bus/output-routing field.
- **Requirement to claim success:** VERA needs direct and fresh Solo/Mute/M/S state evidence, complete source-to-track-to-bus routing evidence, a terminal output comparison with isolated controls, and exact restoration. A pair hash alone is insufficient because Solo is absent from the pair.
- **VERA consequence:** The Solo output supports only the named bounded control result. Transcript/source-range evidence cannot be promoted to general audibility or deletion.
- **Proposed unrun experiment:** Capture producer-visible Fairlight track and bus labels or a verified public routing getter, then render Solo-on, Solo-off, and isolated-track controls from equal checkpoints. This was not run.

#### 3. Render settings and output setup had bounded refusals

- **Classification:** Harness/precondition and getter-observability failures, not Resolve audio-capability failures.
- **Setup/action/observation:** One exact owned XML import refused before a render and left the pair unchanged ([audio-render-import-refusal](evidence/audio-render-import-refusal/summary.json)). A SetRenderSettings call returned true, but subsequent GetCurrentRenderFormatAndCodec returned codec empty/format unknown; original ExportVideo is not exposed by that getter or explicit XML field ([audio-settings-restoration-refusal](evidence/audio-settings-restoration-refusal/observed-state.json)). A video-toggle attempt remained unresolved with the same unknown format state ([audio-video-toggle-unresolved](evidence/audio-video-toggle-unresolved/summary.json)). The later AV path used one owned MOV render and a separate verified restoration; hidden settings equality remains unexposed.
- **Requirement to claim success:** Bind a terminal successful job, exact output path/hash/format, requested audio/video settings, and a post-render restoration whose observable fields match the original. Keep hidden/unreadable settings explicitly unknown.
- **VERA consequence:** Queue/setup success or a true setter return is not output evidence. Output-dependent reconciliation must wait for the terminal output handoff and retain unknown settings.
- **Proposed unrun experiment:** Use a generated-only disposable render preset whose audio/video toggles are independently distinguishable in the final output and whose getter/XML fields are fully observable. No new render-settings experiment was run.

#### 4. Render observation and PCM analysis had transport/availability failures

- **Classification:** External tool/launcher failure with retained recovery; no native capability conclusion.
- **Setup/action/observation:** The first PCM analyzer hit upstream 502/503 errors before extraction/comparison. A Solo same-job observation initially refused because the observation menu was disabled while the render was at 1%; the existing job later completed and was observed without a second start. The final PCM comparison was offline against the retained terminal output.
- **Requirement to claim success:** Require a terminal job result and hash-bound output handoff before opening output bytes; never infer from a partial render or a failed comparator.
- **VERA consequence:** The retained generated-only metrics are valid for the completed output only. A failed analyzer or disabled menu is not evidence of absent Resolve rendering or audio.
- **Proposed unrun experiment:** Add a local-only comparator path with no upstream dependency and a read-only terminal-job wait protocol; this was not rerun or added here.

#### 5. Timing is calibrated only for integer-valued 100% cases

- **Classification:** Bounded endpoint success; fractional and generalized retime semantics unresolved.
- **Setup/action/observation:** Generated 25 fps/48 kHz tail and adjacent PCM samples distinguish frame 9198 from silent frame 9199 while source frame 199 remains nonzero. Float overloads match integer-valued getters. The 50% retime reports source end 99/time 4.0 and changed V1 fields while linked A1 changed fields stayed empty; the retained 50% read is not a generalized calibration.
- **Requirement to claim success:** For each method/domain, retain raw integer and float getter values plus adjacent distinguishing output. Fractional precision requires a non-integral boundary and output sample/frame evidence.
- **VERA consequence:** Preserve raw endpoints and use explicit precision labels. Do not derive duration as end minus start or assume all end fields share one convention. Word-edge cuts remain reviewable/ambiguous.
- **Proposed unrun experiment:** Use new generated frame-varying media with at least one non-integral boundary and 25/29.97 retime cases, retaining getter overloads and adjacent output frames. No such experiment was run.

#### 6. Direct timeline-proxy transcripts are missing

- **Classification:** Observed null values on exactly two timeline pool proxies; collector/project scope limitation.
- **Setup/action/observation:** Call MediaPoolItem.GetTranscription(False/True) twice on the source MediaPoolItem and on each Timeline.GetMediaPoolItem() proxy. Source returns value; both proxies return None with stable missing state. TimelineItem occurrence getters return source identity and geometry, not a direct transcript.
- **Requirement to claim success:** A transcript-based reconciliation path needs complete coverage for its relevant clips/occurrences, with source/proxy object identity, freshness, stable values and a verified time map. Missing proxy results block claims based on a direct timeline transcript; they do not by themselves prevent the separately evidenced source-range reconstruction path when its coverage and mapping requirements are met. Missing data must never become deletion evidence.
- **VERA consequence:** The accepted 22/19 result is source-derived range reconstruction only. It does not prove timeline-specific words or final audible text.
- **Proposed unrun experiment:** On an authorized generated/transcribed timeline, compare source MediaPoolItem, Timeline.GetMediaPoolItem proxy, and TimelineItem.GetMediaPoolItem source handles with method-level raw returns. Do not infer that a different object route will work; this experiment was not run.

#### 7. Transcript boundaries and lexical variance remain bounded

- **Classification:** Producer-accepted source-range reconstruction with endpoint and edge-word uncertainty.
- **Setup/action/observation:** Test 2 excludes source [912,954), which contains singing/in/Swedish. The first range ends 0.874 frames after Finns and 2.126 before singing; the next begins 2.091 after Swedish. Observed source transcript says out while accepted wording intends up; Kai is accepted for KAJ and Specifically is correct.
- **Requirement to claim success:** Resolve endpoint convention and edge clipping with distinguishing audio evidence, retain accepted wording separately from raw transcript, and require manual review for partial/ambiguous words.
- **VERA consequence:** It is safe to report the named source-range omission with the accepted 22/19 wording and its limits. It is unsafe to assert exact word-edge removal or final audible deletion.
- **Proposed unrun experiment:** Use generated speech with nonzero sentinels at word boundaries and independently rendered track/bus output to calibrate source-range edges. No experiment was run.

#### 8. Transcript coverage and freshness enforcement is not implemented

- **Classification:** Adopted future product requirement, tracked by Inbox #146; not an Issue 141 implementation.
- **Setup/action/observation:** The probe covered the two named timelines and one source, while direct proxies were missing. The retained requirement calls for all relevant clips/occurrences and explicit usable, valid no-speech/no-audio, empty, missing, error, unsupported, stale, and mismatched states.
- **Requirement to claim success:** Fail closed when any required clip is uncovered, unreadable, unstable, stale, or provenance-mismatched; bind source identity, occurrence identity, transcript version, and content revision.
- **VERA consequence:** Missing transcript coverage must visibly block transcript-based reconciliation, never silently turn a missing word into evidence of deletion.
- **Proposed unrun experiment:** Producer-accept the smallest #146 coverage/freshness evidence record and exercise it on a multi-source generated timeline. No implementation or experiment was run in Issue 141.

#### 9. R2 native sequence failures were harness failures

- **Classification:** Retained launcher/driver/registration failures; none establishes unavailable Resolve editing.
- **Setup/action/observation:** The first R2 picture continuation refused on a stale editorial-readback module pin; the partial executor narrative incorrectly said its result was absent even though the retained returncode-zero result existed; residual continuation stopped on early/missing evidence pins, an unapproved deselection label, and a wrong-tail UI selection before later bounded continuation. The exact physical cuts and final pairs were reviewed from retained artifacts without replay.
- **Requirement to claim success:** Validate dispatcher-owned hashes, exact phase/index, target UID/source/range, and final complete pair before each mutation; retain a partial result and do not replay a completed phase after a refusal.
- **VERA consequence:** Treat these records as evidence about harness robustness and scope, not as API capability failures or successful unrecorded edits.
- **Proposed unrun experiment:** Run a fresh synthetic driver with dispatcher pin checks and a single explicit phase index, but only under a new authorized native task. It was not run here.

#### 10. Protected real media and general routing were outside scope

- **Classification:** Deliberate evidence boundary, not a failed test.
- **Setup/action/observation:** Generated media bytes and hashes were allowlisted for PCM analysis; protected semi1b.mp4 bytes/hash/export/retranscription were not accessed. Transcript metadata came from retained Resolve getter readback. No real-script run was performed.
- **Requirement to claim success:** A production or real-script VERA claim requires a separate authorized run with source-byte provenance, complete transcript coverage, verified route/output evidence, and producer acceptance.
- **VERA consequence:** Issue 141 can constrain reconciliation behavior and synthetic support, but cannot claim universal real-media audibility or close #145's real-script requirement.
- **Proposed unrun experiment:** Run #145 against the actual real-script fixture with explicit producer authorization and the #146 coverage gate. It was not run.

### VERA acceptance criteria distilled from the retained evidence

VERA can safely mark the named synthetic observations as boundedly successful when it retains:

1. Exact project/timeline/source/occurrence identities, raw setter calls and returns, stable adjacent readbacks, expected record/source ranges, and exact restoration.
2. For an output claim, a terminal hash-bound render, PCM format/hash, generated-source support ranges, control windows, lag/gain/energy metrics, and explicit waveform-only semantics.
3. For mute/Solo/audibility, the specific control layer and an independent output effect; mapping state, operator Solo state, and Fairlight routing must remain separately labeled.
4. For timing, method-specific integer/float getter values and a distinguishing adjacent output observation; fractional and generalized retime claims stay blocked until separately calibrated.
5. For transcript reconciliation, source/proxy/occurrence objects remain distinct; the complete accepted 22/19 wording is retained with raw wording differences; every relevant clip has fresh transcript coverage; missing or stale coverage fails closed.

Within those boundaries, the retained evidence supports the six named R2 geometry/output observations, the bounded 100% endpoint convention, the negative mapping-mute output result, the bounded A2 Solo output result, and the producer-accepted source-range transcript reconstruction. It does not support a general spoken-deletion, Fairlight-routing, or final-audibility claim.

## R3 evidence that bounds the interpretation

### Calibration and sampled picture cases

The calibration at 2026-09-30 22:44 UTC is retained in
[evidence/picture-calibration-success/](evidence/picture-calibration-success/).
On Edit, `ExportCurrentFrameAsStill` returned true at four requested frames
after restoring the initial timecode. The base slate is visible at local
frames 0 and 198; local frames 199 and 200 are identical all-black samples.
This is a bounded base-video endpoint observation. It does not define an audio
endpoint, still-export synchronization, arbitrary effect behavior, or a
general “last visible frame” rule.

The picture case at 23:17 UTC is retained in
[evidence/picture-cases-success/](evidence/picture-cases-success/). It recorded
21 captures, eight setters, and 14 still exports, with exact final-matrix
equality. The synthetic opaque `cutaway.mov` samples were local frames
49/50/98/99/100, with disabled sample 50. The transparent `overlay.png`
samples were local frames 74/75/198/199/200, with disabled sample 75.
The observed cutaway is present at 50 and 98 while the base is present at 49,
99, and 100. The overlay is present at 75, 198, and 199; local 200 is black.
Inspector Opacity 25 reduced the green overlay, then the target was restored
to 100 and disabled.

The picture cases establish only those named synthetic samples and setter
round-trips. They do not establish general visibility, arbitrary OpenFX or
Fusion behavior, exact sample synchronization, clip lineage, audibility, or
product absence.

**Success gate.** A later R3 picture experiment must bind each requested frame
to the exact occurrence, playhead readback, export result, and restored
full-state pair; it must say which effect and enable/lock context was tested.

**Unrun experiments.** No broad effect matrix, arbitrary track-order
visibility test, exact rendered-sample synchronization test, lineage test, or
picture-to-audio audibility test was run.

### Offline guard and later recovery

The first offline-picture setup was correctly refused. R4 initially reported
`GetStartTimecode=01:00:00:00`, `GetStartFrame=90000`, and
`GetEndFrame=90000`, while the occurrence was record 0..199. The planned
frame 0/frame 50 action was stopped before a playhead setter or export. The
diagnostic is recorded at
[report.md#2026-10-01-04:00–04:01-utc--offline-picture-guard-refusal](report.md).
This was a preparation-range defect. It does not imply that offline picture
output is absent.

The later valid cycle is retained in
[evidence/offline-cycle-continuation-success/](evidence/offline-cycle-continuation-success/).
Online and offline samples at frames 0 and 50 were exported; the offline
samples were Media Offline, and same-byte relink restored the exact prior
state. The success gate is a fresh in-range occurrence with explicit
online/offline/relink pairs and no stale timecode assumption. The unrun
experiment is a second, independently reviewed offline visual case with
different source bytes and an explicit cache-refresh check.

### Graphic enable refusal and repair

At 2026-10-01 19:44 UTC the Graphic preparation attempted
`SetClipEnabled(True)` for locked, disabled V3 Graphic
`ea448c37-4821-419d-8fbf-112790cc0499`. The exact native output was
`SetClipEnabled did not return true` (the setter returned false). The
before/after pair is byte-identical; no split, lock, playhead, save, retry, or
cleanup followed. Retain
`graphic-preparation-refusal-analysis.json` and
`r3-graphic-native-executor-result.json` beside the
[report.md#graphic-enable-refusal-before-split--october-1-1944-utc](report.md)
entry.

The diagnosis is ordering: the first preparation tried to enable the target
before unlocking its locked track. It was unknown whether the false return
would also occur on an unlocked target. This does not imply missing
`SetClipEnabled` support or missing Graphic support.

The repaired order—unlock the exact target, enable it, perform the bounded
operation, and restore its original lock—succeeded. The linked V1/A1 split at
Matrix 8600 produced ranges 8500..8600/source 0..100 and
8600..8699/source 100..199; V3 remained enabled and distinct. Independent
review `graphic-full-pair-independent-review.json` passes the structural
criterion while retaining the restore-wrapper caveat.

**Success gate.** Any repeat must retain original lock, target UID, setter
return, split ranges, final lock, and complete postflight equality. It may
claim the named structural split only.

**Unrun experiment.** A general visibility or arbitrary-effect experiment under
the repaired lock ordering was not run.

### Authored section boundary

The first boundary-base preparation at about 20:21 UTC refused before mutation
with `Exact enabled R3-boundary A3 crossing bed changed`. The exact prior
source schema exposed `Clip Name` for `bed.wav`, but the guard required
`source.GetName`. The retained refusal is described at
[report.md#boundary-preparation-refused-captured-schema-mismatch-diagnosed--october-1](report.md)
and bound by the native result
`20261001T202103.928483Z`. No final pair was created for that attempt. The
executor also carried a stale R2 after-pair reference in its narrative; that
reference is not evidence of a boundary postflight. This is a captured-schema
and evidence-index defect, not a boundary or Razor capability failure.

After the predicate repair, the authored marker was placed at absolute frame
9100 (local frame 100), named `141 R3 exact section boundary`, duration 1,
Blue, with note `Synthetic authored boundary at local frame 100` and custom
data `{"issue":141,"section":"R3-boundary","boundaryLocalFrame":100}`.
Base V1/A1 was split at 9100, and separate enabled A3 `bed.wav` was split
9000..9100 and 9100..9199. Disabled V3 `overlay.png` and disabled A2
`repeated.wav` still cross 9100 and were unchanged; the enabled A3 crossing
became two pieces. The independent boundary review
`../../../out/issue-141-observation-20260930-01a0f318/boundary-complete-independent-review.json`
passes the structural criterion.

**Success gate.** Preserve the authored marker and its custom data, report
enabled and disabled crossing items separately, and compare both base and A3
full pairs. The result may establish the meaning of the authored section
marker and the named structural split.

**Unrun experiment.** A blade without an authored marker has not been shown to
carry section meaning. No “all crossings gone,” general visibility, audibility,
or lineage test was run.

## R4 — asset availability, bytes, and occurrence removal

### R4.1 Preparation/refusal history is not asset behavior

**Classification:** Harness/preparation failures, retained to prevent false
capability conclusions.

The initial complete media-pool inventory refused before ImportMedia. The
documented FilePath-dictionary ImportMedia shape refused; the separate path-
list form accepted ImportMedia, CreateEmptyTimeline, Project.SetCurrentTimeline, and
AppendToTimeline, then its post-append proxy/equality guard refused on an extra
or unreadable track item. A read-only follow-up verified exactly one online
base.mov occurrence with source/record bounds 0–199 and generated source bytes
matching the approved hash. Later MediaPool.UnlinkClips returned true, but the first
complete offline inventory refused because the guard did not allow Resolve's
OFFLINE - locator prefix. A start-timecode repair also shifted the R4 timeline
from 90000 to 0 and the occurrence to negative record coordinates before
refusing on unreviewed drift. None proves import, unlink, relink, offline
handling, or deletion unavailable.

Evidence: [pool refusal](evidence/r4-pool-inventory-refusal/summary.json),
[dictionary import refusal](evidence/r4-dictionary-import-refusal/summary.json),
[path-list partial](evidence/r4-path-list-import-partial/summary.json),
[post-append read-only state](evidence/r4-post-append-read-only/summary.json),
[offline refusal and prefix diagnosis](evidence/r4-offline-prefix-read-only/), and
[R4 report history](report.md).

VERA should preserve the exact refusal and partial state, then require a fresh
complete read of source UID, locator, bytes, occurrence UID, ranges and pool
mapping before any transition. It must never infer asset deletion from a
failed inventory or an unreadable proxy handle.

### R4.2 Offline-present versus same-byte relink

**Classification:** Supported bounded offline/relink; occurrence and source
remain present through the offline transition.

**Exact operation, state, and delta.** In the valid in-range re-prepared R4
arrangement, one MediaPool.UnlinkClips operation received the media-pool item
handle whose journaled source UID was 81d81dc0-4c37-478b-8079-03debba5e780.
The occurrence UID
65a7bcd1-f211-4dee-9726-8c7e0b89cc84 remained in the timeline with the same
source/record ranges and source identity. Online reads became Offline, the
locator acquired Resolve's OFFLINE - prefix, and offline source-byte evidence
was marked not accessed. Exported local frames 0 and 50 showed Media Offline.
One MediaPool.RelinkClips call received the media-pool item handle and the
verified original base.mov path, then returned true; complete postflight pairs
matched the original online timeline/pool state, including IDs, ranges and
source hashes, and the original playhead was restored.

Evidence: [offline/relink summary](evidence/offline-cycle-continuation-success/summary.json),
[relink recovery review](evidence/r4-recovery-success/summary.json), and
[R4 report entries](report.md).

This proves offline-present is distinct from occurrence removal for the tested
source. It does not prove arbitrary-source relink, arbitrary effects, general
visibility, program output, or byte access while offline. The earlier offline
picture arrangement with timeline start/end 90000 was rejected as out of range;
its failed preparation must not be used as output evidence.

### R4.3 Same locator and Online status do not prove bytes or displayed replacement

**Classification:** Supported bounded wrong-byte mismatch; displayed replacement
is ambiguous.

**Exact operation, state, and delta.** The generated relink candidate at the
same locator was replaced with wrong bytes
771b4bbbe771b980831e0a7b6d93ef11e1315cd995df22c5c7fbf7c2bf62c88b instead of
expected c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942.
A single MediaPool.RelinkClips refresh received the media-pool item handle and
the same-locator candidate path, then returned true. Source UID, occurrence
UID, locator, Online status, ranges and all other captured metadata stayed the
same; only explicit source-byte evidence changed to mismatch. The sampled frame-0
PNG after refresh was byte-identical to the earlier original slate, so this
run did not establish that wrong replacement bytes were displayed. The
original bytes were restored and refreshed once; complete state and the
original frame-0 sample then matched exactly.

Evidence: [wrong-byte summary](evidence/r4-wrong-bytes-success/summary.json),
[R4 report entry](report.md),
and [retained source readbacks](../../../out/issue-141-observation-20260930-01a0f318/r4-readonly-20261001T003141.604326Z.json.gz).

VERA must verify bytes independently of locator, UID, path and Online status;
a mismatch is stale/ambiguous asset evidence requiring review or refusal. It
must not infer displayed replacement from metadata or one cached frame.
Protected producer media was not read or hashed in these generated-media
checks.

### R4.4 Occurrence removal is distinct from asset deletion and identity restoration

**Classification:** Supported bounded non-ripple occurrence removal; asset
deletion and restoration are not established.

**Exact operation, state, and delta.** With a stable pinned R4 pair, one
Timeline.DeleteClips call received the timeline-item handle whose journaled UID
was af55478a-0ba3-458a-a6e1-e47b2544111d, with False for ripple, and returned
true. The exact occurrence disappeared; the source pool item remained online
with UID 81d81dc0-4c37-478b-8079-03debba5e780, unchanged generated-byte hash,
and Usage 1 -> 0. All other pool fields and timeline state were equal in
adjacent postflight reads. No MediaPool.DeleteClips, append, save, render,
rollback, or retry occurred.

One later AppendToTimeline of the same source at absolute record frame 0
returned a different occurrence UID 65a7bcd1-f211-4dee-9726-8c7e0b89cc84.
Its read-only follow-up verified source/record ranges 0–199 and Usage 0 -> 1,
but this is a new occurrence, not the removed identity restored. A page guard
refused the immediate append postflight; the later read-only capture is the
authority for the new-ID facts.

Evidence: [independent removal comparison](evidence/r4-removal-success/independent-comparison.json),
[removal result](evidence/r4-removal-success/result-extract.json),
[new occurrence readback](evidence/r4-post-append-read-only/summary.json), and
[R4 report entries](report.md).

VERA must represent timeline occurrence removal, source-pool retention, and
new occurrence preparation as separate events. A removed UID cannot be
recovered by matching source bytes, path, marker, or range; restoration of
semantic identity requires an explicit retained mapping or human decision.
## R5 — freshness, stable reads, and ABA

### R5.1 What the capture checks prove

**Classification:** Supported bounded drift detection; freshness/atomicity
remains unproven.

The separate quiet repeat took two adjacent reads in each launcher invocation.
After excluding only expected capturedAt/stage envelope fields, raw
observation payloads and content fingerprints matched exactly; there were no
getter failures or capture failures. This proves a repeatable quiet read for
that state, not close/reopen behavior or an application revision token.

The controlled metadata test called UpdateMarkerCustomData once between
observations, returned true, and changed only the named Matrix marker custom
data. The comparator returned inconsistent-refused; a second setter restored
the original marker and complete state. The real capture-loop test then
changed the same marker during capture, observed exactly that interpass delta,
returned inconsistent-refused, and verified full timeline/pool restoration
(observerRestored=true and fullTimelineAndPoolStateRestored=true).

Evidence: [quiet repeat](evidence/quiet-repeat/summary.json),
[controlled marker change](evidence/r5-controlled-metadata/summary.json),
[real capture-loop refusal](evidence/r5-capture-loop-success/summary.json),
and [R5 report entries](report.md).

### R5.2 Marker note and one-frame move

**Classification:** Marker-note edit and linked one-frame move are supported
bounded observations; unrelated state and freshness remain ambiguous.

The producer's marker editor change altered only Matrix marker 0 Notes to
Issue 141 R5 marker-note observation; IDs, ranges, sources and other marker
fields stayed equal in both full passes. A fixed Trim -> Nudge -> One Frame
Right menu action then produced a byte-identical readback and the checker
refused its expected delta; no retry, undo, or save followed. A later producer-
confirmed move, independently compared from retained JSON without replay,
showed linked video UID 3f2de461-d510-46f8-939f-0c794d48e38b and audio UID
22561398-bce0-4c22-b55f-a73d3ad5e4cf moving record start/end 0/199 -> 1/200
in both stable fresh passes. Source bounds, IDs, links, enabled state and the
calibration marker identity/note were preserved.

The fresh comparison also retained an unrelated cache-path change, selected-
timeline change, authorized producer timeline/pool additions, and omission of
the eight context-sensitive audio property keys. Its applicationRevisionToken
is null. It explicitly does not claim atomicity, ABA exclusion, all unrelated
state unchanged, or independent proof of the menu mechanism.

Evidence: [marker/move summary](evidence/r5-manual-marker-move/summary.json),
[confirmed marker note](../../../out/issue-141-observation-20260930-01a0f318/r5-manual-note-confirmed.json),
[fresh independent comparison](../../../out/issue-141-observation-20260930-01a0f318/r5-independent-fresh-comparison-20261001T181642Z.json),
and [R5 report entries](report.md).

**Known failures and limits.** The first manual-move readback timed out with
no new injected result. A later capture saw the requested 0/199 -> 1/200
geometry but refused on changing Usage and cache locators and lacked pool
passes. The stable later comparison is therefore a bounded move result, not
an all-fields-equal result. Equal adjacent reads cannot exclude a change that
occurs and is undone between reads (ABA), a simultaneous UI edit, or a change
between capture and apply.

## Successful VERA inference criteria

The following are the minimum conditions for using these observations in VERA
reconciliation or apply logic:

1. **Identity and lineage:** retain occurrence UID, source UID, source artifact
   hash, record/source geometry, links, markers, custom data, and operation
   journal as separate fields. Treat newly allocated IDs as normal creation.
   Infer ancestry only from an explicit operation-bound mapping plus verified
   source/occurrence evidence; copied signatures, names, order, markers, and
   shared source IDs are insufficient.
2. **Context:** capture selected timeline UID, page, queue/idle state, playhead,
   selection, complete timeline/pool pairs, and getter errors/missing fields.
   Compare control/effect properties in the same selected context. A reviewed
   context projection here excludes the explicitly reviewed track enabled/locked
   getters, Usage and eight named R1 audio properties for structural comparison;
   same-context control preservation is checked separately. It cannot turn
   projected fields, ignored errors or absent keys into known state.
3. **Geometry:** preserve record and source getter geometry independently,
   including integer and subframe values, time values, offsets, speed and
   endpoint convention. The tested GetEnd calibration is not a universal
   sample or word-boundary rule.
4. **Assets:** verify actual bytes before accepting a locator, UID, path, or
   Online status. Distinguish an offline-but-present occurrence from an absent
   occurrence, and distinguish occurrence removal from source-pool deletion.
   Mismatched bytes or unknown display behavior must block automatic
   replacement or deletion.
5. **Freshness:** require stable, complete adjacent reads and refuse any
   observed drift, incomplete inventory, getter failure, context change, or
   unexplained delta. These checks provide no atomic revision or ABA proof;
   apply authorization needs an application revision token, transaction/lock,
   or an explicit human review at the actual apply boundary.
6. **Failure policy:** preserve raw evidence and partial states. Do not label a
   guard refusal as unsupported Resolve behavior, and do not normalize away
   unknown Out, cache, Usage, Resolution, or context-property differences.

## Proposed unrun counterexamples and follow-up tests

These are proposals only; none was run for this handoff.

| Area | Unrun counterexample | Success criterion for a future VERA inference |
|---|---|---|
| R1 lineage | Duplicate or Copy/Paste two occurrences with identical markers/custom data and then mutate only one occurrence's marker, source range, or destination. | The mapping stays bound to the journaled source/destination IDs; copied metadata alone never selects the sibling. |
| R1 context | Capture the same timeline selected before and after a deliberate track/effect change, then capture it inactive. | Same-context reads expose the real change; inactive getter differences are tagged context-dependent and never interpreted as control state. |
| R1 geometry | Exercise 100%, 50%, fractional and non-frame-aligned ranges with frame stills/PCM and source/record getters. | VERA stores source and record bounds separately and adopts only explicitly calibrated endpoint conventions. |
| R1 Copy/Paste drift | Reopen or render the retained four-Out Copy/Paste case, then copy a case with a materially different source. | The four Out leaves receive a verified interpretation or remain a blocking unknown; no silent normalization. |
| R4 bytes | Relink a deliberately visually distinct wrong-byte file at the same locator, invalidate/reopen the cache, and sample output plus source hash. | Byte hash, displayed sample, source UID and occurrence mapping are compared independently; stale display cannot authorize replacement. |
| R4 availability | Compare source-present offline, missing/offline locator, same-byte relink, wrong-byte relink, and an occurrence removed while the source remains. | Offline state, byte mismatch, occurrence absence, and source-pool retention become distinct classifications with exact IDs and hashes. |
| R4 deletion | In a newly authorized disposable fixture, remove one occurrence, all occurrences, and (if explicitly approved) the pool item with ripple false/true. | Timeline occurrence removal never masquerades as asset deletion; source and occurrence IDs are tracked through each explicit destructive operation. |
| R5 ABA | Arrange A -> B -> A between two reads, including a marker or Usage change. | A monotonic revision/transaction token or lock detects ABA; equal content fingerprints alone fail closed. |
| R5 UI race | Edit/select/relink concurrently with capture and again between capture and apply. | The apply boundary is atomic or explicitly reviewed; stable preflight is not treated as a lease. |

No current record establishes a global Resolve API absence, general lineage
algorithm, arbitrary-source relink guarantee, atomic revision primitive, or
complete collector coverage. Those questions stay unclaimed until one of the
follow-ups produces the required evidence.

## Harness, launcher and recovery failure inventory

### 1. Setup, settings, reopen, and cache

#### 2026-09-30 16:56 UTC — rate representation stopped preparation

**Path.** [evidence/attempt-1/](evidence/attempt-1/), with the source history
and failure hashes retained in the issue-owned output directory.

**Trigger/output.** The first launcher created the project and applied settings,
then read `timelineFrameRate: 25.0` as a number while the request used the
string `"25"`. The guard compared string forms and stopped before import,
timeline creation, or media setup. The operator saw no visible result.

**Partial mutation.** `CreateProject` and `SetSettings` had run; the new
project existed with an otherwise empty preparation state. No import or
timeline mutation occurred. The readback also exposed inherited 24 fps
playback and storage locations outside the disposable slice.

**Diagnosis and product-absence interpretation.** This is a numeric/string
probe bug. It does not imply rejection of 25 fps, inability to create a
project, or product absence. The operator’s External Scripting and
synthetic-only attestations were not inferred from configuration.

**Later recovery.** The corrected guard compares exact finite numeric values and
the later successful baseline preparation created the named synthetic project,
timeline, media, markers, and links.

**Success gate.** Retain the requested type, actual readback type/value, and
an empty-project invariant before import. Refuse only on a real numeric
mismatch.

**Unrun experiment.** No independent test of a non-string rate request against
a newly created blank project was run after this correction.

#### 2026-09-30 17:20 UTC — read-only playback setting in a batch

**Path.** [evidence/attempt-2/](evidence/attempt-2/).

**Trigger/output.** The correction attempted to write
`timelinePlaybackFrameRate`; the installed stub marks it read-only and
`SetSettings refused operation` was returned.

**Partial mutation.** The operation stopped before import. README guidance says
batch settings may be partially applied in unspecified order on failure, so the
state of any other requested writable settings was not safely known. No
timeline or media was created by this attempt.

**Diagnosis and product-absence interpretation.** This is a second probe
boundary error. It does not imply that writable settings, media import, or
timeline creation are unavailable.

**Later recovery.** The operator set playback to 25 manually; the corrected
launcher stopped writing the read-only key, applied writable keys individually,
retained each readback, and later reached the successful baseline.

**Success gate.** Capture all settings before the batch, never include the
read-only key, set writable keys one at a time, and retain post-readback even
when a setter refuses.

**Unrun experiment.** A clean-project test of the documented partial-batch
ordering and each writable storage setter remains unrun.

#### 2026-09-30 18:12 UTC — native repeat baseline preflight

**Path.** [evidence/native-preflight-refusal/](evidence/native-preflight-refusal/).

**Trigger/output.** The native repeat launcher raised
`RuntimeError: Current project is not the prepared baseline-only state`.

**Partial mutation.** None: the refusal preceded native mutation and produced
no native journal. The exact current before-state comparison was not retained.

**Diagnosis and product-absence interpretation.** Cause is unknown: metadata
change and edit are both possible. This does not imply a Resolve mismatch,
unsupported repeat, or failure of the prepared timeline.

**Later recovery.** A quiet read-only repeat at 18:22 retained two equal
adjacent reads matching the baseline. The later run used explicit project and
cache guards, then native duplication succeeded.

**Success gate.** Persist the complete failed preflight (raw current pair,
expected pair, normalized diff, and project identity) before raising. A
repeat may proceed only from two equal complete baseline passes.

**Unrun experiment.** The missing 18:12 current state cannot be reconstructed;
no replay of that exact state is possible.

#### Historical #110 compatibility carryover

**Path.** The inherited evidence referenced by the preparation report, not a
new #141 native occurrence.

**Trigger/output.** Normalization and PCM-WAV render selection failed in the
older #110 workflow; preset/EQ/dynamics remained operator-only.

**Partial mutation.** No #141 state was mutated by that historical result.

**Diagnosis and product-absence interpretation.** Treat this as inherited
compatibility context, not fresh #141 evidence. It does not imply that the
Issue #141 synthetic authoring path is absent.

**Later recovery.** #141 reached a native synthetic baseline and later completed
a bounded generated render through a separately verified queue.

**Success gate.** Keep historical compatibility labels separate from #141
failures and require current-build evidence for any product conclusion.

**Unrun experiment.** The inherited operator-only controls were not re-tested
in #141 and remain outside this handoff.

#### 2026-09-30 19:42 UTC — close returned a different project

**Path.** [evidence/native-close-refusal/](evidence/native-close-refusal/).

**Trigger/output.** `SaveProject` and `CloseProject` returned true, but the
current project after close was UID
`fedceab7-8706-4b83-9ffe-fb77c65f0dbe`, not approved UID
`97037b5a-aab6-48a9-b7e4-4c5697ae10a0`. The launcher stopped before
`LoadProject` or `DuplicateTimeline`.

**Partial mutation.** The approved project was saved and closed. The
unexpected current project was neither inspected nor mutated; no duplicate
was attempted.

**Diagnosis and product-absence interpretation.** The cause and contents of the
unexpected project are unknown. This does not imply failed close/load support,
an empty/default project, or missing DuplicateTimeline capability.

**Later recovery.** The operator manually reopened the exact synthetic project;
a later cache-only mismatch was isolated and then restored before native
duplication.

**Success gate.** Retain current project UID and name after every close/load,
inspect only the approved project, and refuse before any duplicate call on
mismatch.

**Unrun experiment.** The unexpected project was never inspected, by design;
no automatic project switch or replay is authorized.

#### 2026-09-30 20:11 UTC — duplicate-only named-project guard

**Path.** [evidence/native-duplicate-project-refusal/](evidence/native-duplicate-project-refusal/).

**Trigger/output.** The duplicate-only launch returned
`Select only the named issue-141 project; no automatic switch`; current
project identity was absent or did not match.

**Partial mutation.** No capture, selection, or native mutation occurred.

**Diagnosis and product-absence interpretation.** This is a project-selection
guard refusal. It does not imply a Resolve project API or duplication failure.

**Later recovery.** Manual exact-project reopen plus read-only identity checks led
to cache restoration and successful duplication.

**Success gate.** Keep the refused identity in the retained result, then require
two complete exact-project reads before any action.

**Unrun experiment.** Automatic project switching was intentionally not tested.

#### 2026-09-30 20:17 UTC — cache readback mismatch on reopened project

**Path.** [evidence/native-reopen-cache-refusal/](evidence/native-reopen-cache-refusal/).

**Trigger/output.** Project identity matched, but
`perfCacheClipsLocation` read back as `CacheClip` at project and timeline
settings instead of the pinned owned cache path. IDs, ranges, markers, item
properties, and media hashes otherwise matched.

**Partial mutation.** None after the manual reopen; no duplication or native
journal was produced.

**Diagnosis and product-absence interpretation.** The resolved target of
`CacheClip` was unknown. This is an environment/readback mismatch, not
evidence that reopening, cache settings, or duplication are unsupported.

**Later recovery.** The guarded cache-restoration action set the project setting
once, returned true, and produced a postflight exactly equal to the saved
baseline; native duplicate then succeeded. See
[evidence/cache-restoration-success/](evidence/cache-restoration-success/).

**Success gate.** Pin the cache path and its observed readback form across
project and all timelines; restore only after a fresh full pair and verify the
same pair after restoration.

**Unrun experiment.** The meaning or persistence of the literal `CacheClip`
target after a fresh application restart was not tested.

#### 2026-09-30 21:49 UTC — source-list shape assumption

**Path.** [evidence/matrix-source-read-refusal/](evidence/matrix-source-read-refusal/).

**Trigger/output.** The matrix action refused
`Media pool items are unreadable; refusing` because it required exactly five
root-folder entries.

**Partial mutation.** None. Two complete before/after passes were equal and the
journal contains no API mutation.

**Diagnosis and product-absence interpretation.** The raw list type, value, and
count were not retained, so the precise mismatch is unknown. This is a probe
assumption, not unavailable media-pool or timeline capability.

**Later recovery.** The corrected continuation reused already observed source
handles, completed all 114 placements, and saved the matrix.

**Success gate.** Retain the raw source-list type/value/count and bind every
source handle to UID, locator, and owned-byte policy before creation.

**Unrun experiment.** The original five-entry source-list value cannot be
recovered; no replay of the discarded read is available.

#### 2026-09-30 21:56 UTC — marker numeric/string-key bug

**Path.** [evidence/matrix-marker-refusal/](evidence/matrix-marker-refusal/).

**Trigger/output.** After timeline creation and the first occurrence/marker,
the marker guard rejected a numeric/string key mismatch.

**Partial mutation.** The matrix timeline, first occurrence, and marker existed;
the remainder of the matrix was not completed in that invocation. The partial
state was retained and no cleanup or blind retry occurred.

**Diagnosis and product-absence interpretation.** The failure was an
implementation key-type assumption. It does not imply marker creation,
timeline creation, or placement capability is absent.

**Later recovery.** The corrected key handling preserved the first marker and
completed the remaining 113 placements.

**Success gate.** Normalize marker keys only after retaining their raw type and
verify the first marker plus all later markers in a fresh pair.

**Unrun experiment.** No separate marker-key regression was run against an
unrelated existing timeline; only the corrected synthetic path was exercised.

#### 2026-09-30 22:11 UTC — audio-format guard rejected stereo A1

**Path.** [evidence/matrix-track-refusal/](evidence/matrix-track-refusal/).

**Trigger/output.** After 114 placements completed, the final guard raised
`Final matrix audio tracks are not all mono`. Actual tracks were A1 stereo,
A2 mono, and A3 mono.

**Partial mutation.** All 114 items, source bindings, markers, links, and enable
states were present. The guard stopped before `SaveProject`.

**Diagnosis and product-absence interpretation.** The guard assumed every audio
track would be mono; the existing default A1 was stereo. This does not imply
audio placement or track-format support is unavailable.

**Later recovery.** The corrected observed matrix layout was accepted and a
save-only action succeeded with one `SaveProject` call.

**Success gate.** Pin the expected per-track format (stereo/mono/mono), rather
than an all-mono predicate, and require exact 114-item post-save equality.

**Unrun experiment.** No generic mono-conversion or all-mono authoring test was
run.

### 2. Media-pool, R4, range, and recovery-state failures

#### 2026-10-01 00:18 UTC — initial R4 pool inventory

**Path.** [evidence/r4-pool-inventory-refusal/](evidence/r4-pool-inventory-refusal/).

**Trigger/output.** Initial complete inventory refused with
`Media-pool item identity/properties are unreadable`.

**Partial mutation.** None; no `ImportMedia`, transition, or mutation journal
was produced.

**Diagnosis and product-absence interpretation.** The failure is limited to
the first identity/property read. It does not imply import, unlink, relink,
offline, replacement, removal, or R4 support is absent.

**Later recovery.** Later read-only checks enumerated the unchanged original pool;
the path-list import branch was run separately.

**Success gate.** Persist the failed item identity/property payload and require
a complete, readable inventory before any R4 transition.

**Unrun experiment.** The exact unreadable first shape was not reconstructed;
the later successful inventory used a new read.

#### 2026-10-01 00:27 UTC — dictionary-shaped ImportMedia request

**Path.** [evidence/r4-dictionary-import-refusal/](evidence/r4-dictionary-import-refusal/).

**Trigger/output.** `ImportMedia` refused the approved `FilePath`/hash
dictionary item shape.

**Partial mutation.** None. Follow-up read-only checks retained equal pools with
eight pre-existing entries and no mutation.

**Diagnosis and product-absence interpretation.** This applies only to that
argument shape. It does not imply path-list import, relink, unlink, or other
R4 operations are unavailable.

**Later recovery.** A path-list import succeeded and produced an imported item.

**Success gate.** Test each accepted argument shape independently and retain the
exact request and return before changing the next phase.

**Unrun experiment.** No second dictionary-shape variant was tried after the
refusal.

#### 2026-10-01 00:31 UTC — path-list import and append partial state

**Path.** [evidence/r4-path-list-import-partial/](evidence/r4-path-list-import-partial/).

**Trigger/output.** Path-list `ImportMedia` returned an item; the action
created `VERA 141 R4 availability`, selected it, and appended to V1. The
post-append proxy/equality guard then refused
`R4 contains an extra or unreadable track item`.

**Partial mutation.** Media UID
`81d81dc0-4c37-478b-8079-03debba5e780`, timeline UID
`64de8a4c-86bd-4f19-9d20-47b8940f610b`, and occurrence UID
`af55478a-0ba3-458a-a6e1-e47b2544111d` existed. The occurrence was enabled
on V1 with bounds 0..199. No `SaveProject` occurred.

**Diagnosis and product-absence interpretation.** The extra/unreadable postflight
guard failed after successful import and append. This does not imply either
native operation failed or that the new item cannot be read.

**Later recovery.** A read-only follow-up retained a single enabled base
occurrence, ten pool entries, and matching source bytes. Later unlink/relink,
removal, and new-ID in-range preparation were run as separate checkpoints.

**Success gate.** Bind the expected extra media item and occurrence UIDs before
append; permit exactly those deltas and require a complete post-append pair.

**Unrun experiment.** No retry of the original append or save was made; the
partial state was deliberately preserved.

#### 2026-10-01 01:21 UTC — unlink succeeded, offline-prefix guard refused

**Path.** [evidence/r4-unlink-offline-prefix-refusal/](evidence/r4-unlink-offline-prefix-refusal/)
and [evidence/r4-offline-prefix-read-only/](evidence/r4-offline-prefix-read-only/).

**Trigger/output.** `UnlinkClips` returned true. The occurrence remained
present with `Online Status: Offline` and locator
`OFFLINE - <approved relink/base.mov>`. The full pool inventory then refused
`Media-pool item identity/properties are unreadable` because the guard did
not accept the literal `OFFLINE -` prefix.

**Partial mutation.** The imported occurrence remained on R4 with the intended
offline status. Only one complete pool read was retained; no relink or save
followed.

**Diagnosis and product-absence interpretation.** This is prefix handling and
incomplete-read evidence. It does not imply unlink failure, disappearance,
deletion, or unavailable offline support.

**Later recovery.** The read-only comparison isolated the two intended offline
properties. A relink-only action returned true and restored the exact online
pair.

**Success gate.** Treat offline locator decoration as a display field; retain
the underlying locator/status separately and require two complete pool passes
before relink.

**Unrun experiment.** No cache/display-refresh test for an offline item was run
before relink.

#### 2026-10-01 02:54 UTC — start-timecode repair shifted occurrence negative

**Path.** [evidence/r4-range-repair-refusal/](evidence/r4-range-repair-refusal/).

**Trigger/output.** `SetCurrentTimeline` selected R4 and
`SetStartTimecode(00:00:00:00)` returned true. R4 timeline start/end changed
90000→0 and timecode 01:00:00:00→00:00:00:00, but the occurrence shifted from
record 0..199 to -90000..-89801. The postcondition refused the range.

**Partial mutation.** The same occurrence and source IDs remained; source range
and duration stayed intact, while seven timeline/occurrence and six mapped
pool-proxy leaves changed. No save/render/source mutation occurred. The
unsaved invalid state was retained without rollback.

**Diagnosis and product-absence interpretation.** The setter preserves absolute
record coordinates relative to the timeline start. The invalid occurrence was
not moved into range. This is a preparation arithmetic assumption, not an
offline-output or Resolve setter failure.

**Later recovery.** The occurrence was removed with exact before/after evidence;
a new append created a new occurrence UID at record 0..199 on the zero-start
timeline. The old identity was not reused.

**Success gate.** Derive record coordinates after changing start timecode,
require an in-range new occurrence, and keep removal and re-preparation pairs
separate.

**Unrun experiment.** No fractional or nonzero-start in-range offline visual
case was run.

#### 2026-10-01 03:26–03:28 UTC — append succeeded, page guard refused

**Path.** The native result is
`vera-issue-141-observation-result-20261001T032648.191508Z.json`; the
read-only recovery is [evidence/r4-reprepare-read-only/](evidence/r4-reprepare-read-only/).

**Trigger/output.** `AppendToTimeline` returned new occurrence UID
`65a7bcd1-f211-4dee-9726-8c7e0b89cc84`, source 0..199, V1, record frame 0.
The postflight required Deliver while Resolve was on Edit and refused.

**Partial mutation.** The new occurrence and timeline end 0→199 existed;
source Usage changed 0→1 and R4 proxy duration/end fields updated. No retry,
rollback, save, render, or cleanup occurred.

**Diagnosis and product-absence interpretation.** This is a page-precondition
failure after a successful append. It does not imply append, source access, or
in-range preparation is unavailable.

**Later recovery.** A read-only Edit capture verified the new UID, source/record
0..199, idle queue, and exact anticipated deltas.

**Success gate.** Require the observed Edit page or make page a read-only
diagnostic, and compare the actual new UID and all expected deltas.

**Unrun experiment.** No append retry or save from this partial state was made.


#### 2026-10-01 00:02:29 UTC — output discovery preflight mismatch

**Path.** [evidence/program-output-discovery-preflight-refusal/](evidence/program-output-discovery-preflight-refusal/).

**Trigger/output.** The read-only output-discovery launcher raised
`RuntimeError: Live preflight differs from saved Matrix pin` before any
capability getter. The persisted two passes themselves were equal to the
stable 23:47 pin; the mismatch was in the comparison representation.

**Partial mutation.** None. The journal contains only output-discovery start
and preflight readback; `GetRenderFormats`, codec, mode, job-list, and
rendering-status getters were never reached.

**Diagnosis and product-absence interpretation.** The probe compared native
Python marker keys/tuples with JSON-loaded keys/lists. This is a
canonicalization defect. It does not imply output-capability getters,
rendering, or audio output is absent.

**Later recovery.** Canonical JSON normalization was added; the 00:05:58
read-only continuation reached all eight getters and returned current
MOV/H264, mode 1, an empty queue, and idle rendering. No mutation was added.

**Success gate.** Canonicalize every persisted/live comparison while retaining
the raw representation, and record `capabilityGettersReached=false` on this
class of refusal.

**Unrun experiment.** No getter or render job was run from the refused
preflight; only the corrected read-only enumeration was accepted.

#### 2026-10-01 01:59 UTC — preset export directory/file shape

**Path.** [evidence/audio-preset-export-refusal/](evidence/audio-preset-export-refusal/).

**Trigger/output.** `SaveAsNewRenderPreset` and
`Resolve.ExportRenderPreset` each returned true, but Resolve created a
directory containing a named XML while the probe expected a file at the export
path. The probe refused `Could not retain owned render-preset recovery copy`.

**Partial mutation.** The owned preset and XML existed; no render settings,
queue, job, or render mutation followed.

**Diagnosis and product-absence interpretation.** This is a representation
gap in the probe. It does not imply preset export or audio capability is
absent.

**Later recovery.** The XML was retained and reused without replaying export.
Its recorded raw hash is
`1b3b21a728c3216f9782d87aa2feae977747c377901eb6b81ed5a83a2da06595`.

**Success gate.** Accept the documented directory/XML representation, bind the
actual XML path and hash, and retain the owned preset name.

**Unrun experiment.** A fresh export to an already existing directory was not
run.

#### 2026-10-01 02:12 UTC — audio-only settings made current format unknown

**Path.** [evidence/audio-settings-restoration-refusal/](evidence/audio-settings-restoration-refusal/).

**Trigger/output.** Audio-only `SetRenderSettings` returned true, then
`GetCurrentRenderFormatAndCodec` returned
`{"format":"unknown","codec":""}`. The guard refused before
`AddRenderJob`/ `StartRendering`. `LoadRenderPreset` also returned true
but left the getter unknown.

**Partial mutation.** Render settings changed enough to produce the unknown
readback; no job, render, save, or cleanup occurred. The owned preset/XML were
retained.

**Diagnosis and product-absence interpretation.** The getter behavior and
hidden preset fields were not exposed. This does not imply audio rendering,
preset load, or job creation is unavailable.

**Later recovery.** The exact XML import was attempted on Deliver and returned
false; explicit `SetRenderSettings({"ExportVideo": true})` returned true
but still left unknown. `SetCurrentRenderFormatAndCodec("mov","H264")` later
restored the visible format, with hidden-setting equality still unknown.

**Success gate.** Capture format, codec, mode, page, queue, and all exposed
settings before and after every one-field action; do not authorize a job on
unknown format.

**Unrun experiment.** No actual audio-only job was queued from the unknown
state, and no documented getter for the hidden ExportVideo state was found.

#### 2026-10-01 02:30 UTC — recovery assumed Edit instead of Deliver

**Path.** [evidence/audio-recovery-page-preflight-refusal/](evidence/audio-recovery-page-preflight-refusal/).

**Trigger/output.** Import recovery refused the Edit-page precondition before
calling `ImportRenderPreset`. Read-only state showed page Deliver, unknown
format, mode 1, idle empty queue.

**Partial mutation.** None after the prior settings change; no import request
was dispatched.

**Diagnosis and product-absence interpretation.** Wrong page assumption in the
recovery guard. It does not imply import or Deliver-page recovery failure.

**Later recovery.** The corrected Deliver action was run once with full content,
pool, source, and render guards.

**Success gate.** Pin current page and require the page observed in the
preceding read-only capture; retain a no-import journal on refusal.

**Unrun experiment.** No page-switch automation was attempted.

#### 2026-10-01 02:38 UTC — exact XML import returned false

**Path.** [evidence/audio-render-import-refusal/](evidence/audio-render-import-refusal/).

**Trigger/output.** Deliver-page recovery called
`ImportRenderPreset` once on the exact owned XML; return was false.

**Partial mutation.** Complete timeline/pool/source pairs remained equal; preset
list, mode, empty queue, idle state, and unknown format were unchanged. No
retry, setter, queue, render, save, or cleanup followed.

**Diagnosis and product-absence interpretation.** The reason for this exact
import refusal is unknown. It does not imply import of an absent preset, audio
rendering, or queueing is unavailable.

**Later recovery.** Visible format was restored using the documented explicit
MOV/H264 selector, then the original render snapshot was restored and cleaned
after later output work.

**Success gate.** Record XML path/hash, preset-list delta, page, format/mode,
and import return; separate “visible format restored” from “all hidden fields
restored.”

**Unrun experiment.** An import of an absent preset or a cleanly exported
fresh XML was not tested.

#### 2026-10-01 02:46 UTC — one-field video toggle did not recover format

**Path.** [evidence/audio-video-toggle-unresolved/](evidence/audio-video-toggle-unresolved/).

**Trigger/output.** `SetRenderSettings({"ExportVideo": true})` returned true,
but the format/codec getter remained unknown/empty.

**Partial mutation.** Complete content/pool/source pairs were unchanged; no
queue, render, save, cleanup, or retry followed.

**Diagnosis and product-absence interpretation.** The field did not restore the
visible format in this state. It does not imply SetRenderSettings, video
rendering, or audio rendering is unavailable.

**Later recovery.** A separate `SetCurrentRenderFormatAndCodec("mov","H264")`
call returned true and restored the visible format.

**Success gate.** Verify each setting through its own getter, and do not treat a
true setter return as restoration.

**Unrun experiment.** No clean baseline was used to isolate whether the
unknown state came from audio-only settings, preset loading, or page context.

#### 2026-10-01 06:20 and 06:32 UTC — AV settings/readback drift

**Path.** [evidence/av-preset-precondition-refusal/](evidence/av-preset-precondition-refusal/)
and [evidence/av-settings-pool-out-refusal/](evidence/av-settings-pool-out-refusal/).

**Trigger/output.** The 06:20 snapshot guard saw
`RecordAudioBitDepth=16` while the pin expected 24. At 06:32
`SetRenderSettings` returned true, then four Matrix proxy/mapping pool
`Out` leaves changed from empty to `00:00:08:00\), so the guard refused.

**Partial mutation.** The first attempt did not dispatch a setter. The second
changed exactly those four pool-display leaves; no `AddRenderJob` or
`StartRendering` was issued.

**Diagnosis and product-absence interpretation.** The bit-depth mismatch and
Out-display drift are state/pin and readback effects. They do not imply render
or audio capability is absent.

**Later recovery.** A fresh after-settings checkpoint independently verified
the four Out leaves, queued a job with actual dimensions/range, and later
completed one owned render.

**Success gate.** Derive settings and range from the current full pair, verify
actual queued metadata before start, and retain the four-leaf drift as an
explicit expected delta.

**Unrun experiment.** No second setter replay from the stale 16-bit or
pre-drift snapshot was run.

#### 2026-10-01 07:07 UTC — R1 copy page/format/queue guard

**Path.** [evidence/r1-copy-paste-stopped/](evidence/r1-copy-paste-stopped/).

**Trigger/output.** The copy launch refused
`Exact Edit/known format/empty queue required`; read-only context was Deliver
with MOV/H264 and an idle empty queue.

**Partial mutation.** No selection, copy, paste, or native mutation occurred.

**Diagnosis and product-absence interpretation.** The action assumed Edit. This
does not imply copy/paste capability is absent.

**Later recovery.** With renewed bounded approval, a genuine copy/paste ran on
the correct context. Its expected new clips were retained, but a later
four-leaf pool-Out drift stopped the continuation.

**Success gate.** Pin page, format, queue, selected UIDs, and complete before
pair; require exact new occurrence IDs and expected pool deltas afterward.

**Unrun experiment.** No retry of this refused invocation was made.

#### 2026-10-01 07:20–07:25 UTC — genuine Copy/Paste stopped on pool-Out drift

**Path.** The continuation records are in
[evidence/r1-copy-paste-stopped/](evidence/r1-copy-paste-stopped/) and the
full pair is in the issue-owned `out/` directory.

**Trigger/output.** Copy/Paste created new clips, but the postflight saw the
same four Matrix proxy/mapping `Out` leaves change. The action stopped before
accepting the final state.

**Partial mutation.** New copied timeline occurrences and expected Usage
increments existed; no save or cleanup was used to hide the drift.

**Diagnosis and product-absence interpretation.** The drift is a
context/readback delta. It does not imply that Copy/Paste or occurrence
creation failed.

**Later recovery.** The original stopped copies and metadata remained
protected; later R1 razor, trim, move, and final duplicate were verified with
their own context guards.

**Success gate.** Compare copy-specific expected deltas separately from known
pool Out-display fields, and retain copied UIDs, reciprocal links, markers, and
source identities.

**Unrun experiment.** A second copy/paste from the same stopped state was not
run.

### 3. Editorial, launcher, and bridge failures

#### Initial selection reader/API-shape failure

**Time/path.** The first R3/R1 selection reader expected a dictionary, while the
API returned a list; the retained helper sources and editorial refusal bundle
are in [evidence/editorial-helper-sources/](evidence/editorial-helper-sources/)
and the report’s approved editorial calibration section.

**Trigger/output.** The reader failed its shape expectation. The later Select
All action selected locked items, and the safety guard stopped rather than
editing them.

**Partial mutation.** Selection state may have changed during calibration, but
the guarded action dispatched no edit and retained no accepted final edit pair.

**Diagnosis and product-absence interpretation.** The reader and selection
scope were harness assumptions. This does not imply selection, lock handling,
or editorial commands are unavailable.

**Later recovery.** Explicit V1/A1 Auto Select and deselection produced exact
target lists; named R1 razor, trim, move, and copy/paste actions then completed
bounded cases.

**Success gate.** Normalize the actual list shape, pin selected UIDs and lock
state, and retain a complete readback after each menu action.

**Unrun experiment.** No broad Select All behavior on mixed locked tracks was
accepted as a product result.

#### 2026-10-01 05:48 UTC — R1 trim window/title guard

**Path.** [evidence/r1-trim-launch-refusal/](evidence/r1-trim-launch-refusal/).

**Trigger/output.** The Hammerspoon project-title/window guard refused before
the Trim menu was dispatched.

**Partial mutation.** None: no menu, selection, timeline, or save mutation.

**Diagnosis and product-absence interpretation.** Window identity/readiness was
unknown at that launch. This does not imply Trim or linked-pair editing is
unavailable.

**Later recovery.** A fresh focus check and exact selection enabled the bounded
25-frame linked-pair trim, with independent full comparison.

**Success gate.** Retain title, frontmost window, enabled menu, target UIDs,
and empty/expected selection before dispatch.

**Unrun experiment.** No automatic window activation or retry was performed.

#### 2026-10-01 06:20/06:32 and 07:07 — downstream editorial launch preconditions

The AV and R1-copy occurrences are recorded above because they share the page,
format, queue, and pool-Display-Out boundary. Each stopped before the unsafe
operation or retained its exact bounded partial result. None establishes
product absence.

**Success gate.** Use current page and current queue as observed inputs, not
pinned expectations copied from a prior checkpoint. **Unrun:** no generic
cross-page editorial macro was tested.

#### 2026-10-01 11:25–11:34 UTC — R2 selection returned empty lists

**Path.** The R2 continuation records are summarized in
[report.md#independent-r2-selection-attempts--october-1-1125–1134-utc](report.md).

**Trigger/output.** Focus and Auto Select attempts still returned empty
selected-item lists. No target could be authorized.

**Partial mutation.** Focus/Auto Select menu calls occurred, but no blade,
delete, or other edit was dispatched.

**Diagnosis and product-absence interpretation.** Selection/readback context
was not established. This does not imply R2 editing or selection is absent.

**Later recovery.** Explicit V1/A1 scope and named UIDs were used for later
R2 cuts and deletion.

**Success gate.** Require exact selected UIDs, scope, and complete before pair
before any R2 edit.

**Unrun experiment.** No generic Auto Select inference was accepted across
tracks.

#### 2026-10-01 11:xx UTC — R2 float guard

**Path.** R2 derived-end/selection continuation records.

**Trigger/output.** The guard rejected `7.96` versus
`7.959999999999999`.

**Partial mutation.** No blade or repeat was dispatched.

**Diagnosis and product-absence interpretation.** Decimal formatting/equality
was too strict. This does not imply a retime or endpoint capability failure.

**Later recovery.** A bounded comparison used normalized numeric tolerance and
completed the named R2 cases.

**Success gate.** Preserve raw values but compare documented numeric values
with explicit tolerance and endpoint convention.

**Unrun experiment.** No fractional retime endpoint case was run.

#### 2026-10-01 13:07–13:13 UTC — R5 no-effect menu nudge

**Path.** [evidence/r5-manual-marker-move/](evidence/r5-manual-marker-move/).

**Trigger/output.** After the operator’s marker-note change, the reviewed
Playback/nudge command returned without changing the target pair. The guard
refused the expected one-frame delta; the readback was byte-identical.

**Partial mutation.** Marker notes changed as requested; the nudge produced no
observed movement. No retry, undo, save, or unrelated mutation occurred.

**Diagnosis and product-absence interpretation.** This is a no-effect menu
observation. It does not imply Playback, nudge, or timeline move is absent.

**Later recovery.** The producer later reported a manual move. A subsequent
read-only comparison found the requested 1..200 geometry but retained Usage
and missing-pool-pass instability, so the full R5 pair remained unverified.

**Success gate.** Require a stable full pair with exact target geometry and
unrelated-field comparison after the single menu action.

**Unrun experiment.** No second automated nudge was issued; no atomic revision
or ABA test was run.

#### 2026-10-01 13:25–16:20 UTC — producer move/bridge readiness stalls

**Path.** [evidence/bridge-readiness-stall/](evidence/bridge-readiness-stall/),
plus the retained independent action and
`r5-manual-move-report.json`.

**Trigger/output.** The producer’s read-only launch timed out after 10 seconds.
No injected result appeared. Later bridge calls returned Usage-only
adjacent-read refusals, an unknown current render format, and
`<no main window>`/exact-window refusals.

**Partial mutation.** No nudge, save, reopen, edit, or render was replayed.
The producer’s “moved” report was not promoted to native evidence.

**Diagnosis and product-absence interpretation.** Window/process readiness and
capture freshness were unresolved. This does not imply a Resolve API or
timeline-edit failure.

**Later recovery.** Read-only comparisons eventually established the
requested geometry, but the complete R5 acceptance still required stable pool
passes and Usage handling. The bridge was restarted without replaying the
edit.

**Success gate.** Retain process state, window title, bridge result, exact
before/after pairs, and operator reports as separate evidence classes.

**Unrun experiment.** No automated retry of the timed-out manual move was run;
the exact producer action cannot be reconstructed.

#### 2026-10-01 16:55 UTC — transcript serializer failed before getters

**Path.** The producer transcript dispatch record and
`../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-dispatch-review.json`.

**Trigger/output.** The first launch failed before transcript or geometry
getters with `AttributeError: NoneType has no attribute __name__`.

**Partial mutation.** No transcription read, source-file read/hash/export,
timeline edit, save, or render occurred; configuration was restored.

**Diagnosis and product-absence interpretation.** Serializer/dispatch failure.
It does not imply transcript getters or source-word mapping are unavailable.

**Later recovery.** Serializer repair enabled a read-only test: source
transcription was returned, while the two existing timeline media-pool
proxies returned None. That bounds those objects only; it is not a universal
transcription absence claim.

**Success gate.** Validate serializer output and module pins offline before
dispatch; retain source, nested, and timeline proxy results separately.

**Unrun experiment.** No complete all-clips transcription coverage check was
run; Inbox #146 remains the required future coverage gate.

#### 2026-10-01 18:56 UTC — stale editorial dispatcher pin

**Path.**
`../../../out/issue-141-observation-20260930-01a0f318/r2-picture-native-executor-result.json`
and [report.md#r2-picture-only-harness-refusal--october-1-1856-utc](report.md).

**Trigger/output.** The R2 picture preparation completed two matching full
state reads, then the executor found that `probe.py` retained the old
`editorial-readback.py` hash. It exited 1 before getters.

**Partial mutation.** Auto Select none/V1 and deselection menus had dispatched;
no split, delete, retry, or restoration occurred, and final protected state
after those menus was not accepted.

**Diagnosis and product-absence interpretation.** Stale dispatcher-owned module
pin. This does not imply R2 picture editing is unavailable.

**Later recovery.** The pin was corrected and exact prepared-state readback
succeeded; the named picture-only case then ran once.


A separate root read-only invocation at 19:20 UTC used an unapproved
`r2-picture` readback label and refused before getters. Its raw launcher
failure is retained with the corrected approved `r2-picture-context` readback;
no split, deletion, or restoration occurred. This is the same label-contract
class, not a second Resolve failure.

**Success gate.** Validate dispatcher AST/module hashes before any menu action
and require a fresh exact pair after preparation.

**Unrun experiment.** No replay of the stale-pinned preparation is allowed.

#### R5 manual launcher timeout and unknown-window continuation

The 10-second timeout and later `Project changed; stop: <no main window>`
refusals are launcher/window failures recorded above. They stopped before
injected dispatch and therefore provide no native edit result.

**Success gate.** A read-only readiness check must prove exact project title,
frontmost window, enabled menu, and `triggered=false` before one approved
continuation. **Unrun:** no automatic retry or window-switch policy was
tested.

### 4. Render, output, residual, and restoration failures

#### Residual first-cut review was invoked too early

**Time/path.** 2026-10-01, first residual cut; evidence is in the issue-owned
residual continuation records and
`../../../out/issue-141-observation-20260930-01a0f318/residual-resume-native-executor-original-wording.json`.

**Trigger/output.** The genuine first split at record frame 4560 was retained,
but the driver called the full-state review before the relative approved-output
pin existed. It refused `A relative approved-output evidence pin is required`.

**Partial mutation.** First cut and selection occurred; no second cut,
deletion, final readback, save, or render occurred.

**Diagnosis and product-absence interpretation.** Harness sequencing/evidence
pin failure. It does not imply Razor, linked cutting, deletion, or rendering is
unavailable.

**Later recovery.** The continuation resumed from the retained first split,
performed the second cut at 4570, later deleted the exact middle interval, and
restored context without replaying either cut.

**Success gate.** Validate all relative evidence pins before the first native
mutation; retain phase-indexed records and exact UIDs.

**Unrun experiment.** No replay of the first cut or preparation is allowed.

#### Residual second-position/selection labels

**Trigger/output.** A continuation reached the second-position checkpoint but
stopped because a deselection label was outside the approved readback list.
Later the right-tail selection did not match the intended deletion target.

**Partial mutation.** Position setter and menu preparation ran; no incorrect
deletion was made. The exact middle interval was deleted only in the corrected
continuation using explicit handles.

**Diagnosis and product-absence interpretation.** Selection label/index and
executor narrative defects. They do not imply deletion or R2 editing is absent.

**Later recovery.** The corrected driver treated observed UI selection as
diagnostic and used the explicit derived interval UIDs as deletion authority;
independent final review passed.

**Success gate.** Require exact target UID/source/range/link guards and make a
wrong UI selection refuse before `DeleteClips`.

**Unrun experiment.** No deletion using an unverified UI tail selection was
run.

#### 2026-10-01 11:53 UTC — stale render range/dimensions

**Path.** [evidence/av-owned-unstarted-job-recovery/](evidence/av-owned-unstarted-job-recovery/)
and the queue records in `out/`.

**Trigger/output.** `AddRenderJob` created owned job
`9c4f9ad9-9acf-4c60-bac2-fb7cc9269ebd`, but actual metadata was 1920x1080
and MarkOut 2449 while the guard expected 640x360 and 200. It refused before
`StartRendering`.

**Partial mutation.** One unstarted job existed; recovery preset/XML and edited
timeline remained. No render started.

**Diagnosis and product-absence interpretation.** Queue guard used stale
dimensions/range. This does not imply AddRenderJob or rendering is unavailable.

**Later recovery.** The owned job was removed with exact full before/after
equality; a fresh queue derived MarkOut 9199 and later rendered once.

**Success gate.** Derive dimensions and MarkOut from the current complete state,
then compare actual job metadata before allowing one start.

**Unrun experiment.** No start of the stale 640x360/200 job was attempted.

#### 2026-10-01 — full-Matrix queue dispatcher route missing

**Path.** `../../../out/issue-141-observation-20260930-01a0f318/dispatch-registration-check.py`
and the AV continuation records.

**Trigger/output.** The first registered continuation lacked its runtime
dispatch route and silently returned observation-only results. No native render
start occurred.

**Partial mutation.** Earlier attempts reached preset export/settings and
refused before `AddRenderJob`; the route-missing invocations added no native
mutation.

**Diagnosis and product-absence interpretation.** Dispatcher registration
defect. It does not imply queue or rendering absence.

**Later recovery.** The route was added and a registration regression covered
all owned aliases. The actual owned job was then started exactly once.

**Success gate.** Validate route presence and action/route consistency before
registration; reject non-observe actions with no route.

**Unrun experiment.** No silent observation-only invocation may be promoted to
native evidence.

#### 2026-10-02 — render poll menu unavailable and caller wait expired

**Path.** `cli-av-owned-render-resume-result.json` and retained render
continuation records under `out/`.

**Trigger/output.** The first poll could not find the approved Observation
menu while rendering and stopped. A resume-only call later observed Complete
100% without a second start. A separate queue caller’s wait expired, but its
same-job result was recovered without replay.

**Partial mutation.** One owned job had already started; no second
`StartRendering` was issued. Output and final restored pair were retained.

**Diagnosis and product-absence interpretation.** Menu/window availability and
caller wait behavior. This does not imply an incomplete render or missing
render API.

**Later recovery.** Same-job continuation observed completion; the generated
MOV was retained and independently analyzed.

**Success gate.** Bind job UID, one-start count, terminal status, output hash,
and restored pair; resume only with `resumeExistingJob=true`.

**Unrun experiment.** No second start or duplicate output was attempted.

#### 2026-10-02 — first PCM analyzer failed upstream

**Path.** `pcm-real-render-analysis.json` lineage and the retained analyzer
worker record.

**Trigger/output.** The first PCM analyzer ended on upstream HTTP 502/503 before
extraction/comparison.

**Partial mutation.** No Resolve call, render, source read, or output rewrite
occurred; no analyzer artifact was produced by that worker.

**Diagnosis and product-absence interpretation.** External analyzer transport
failure. It does not imply render, PCM extraction, or speech analysis is absent.

**Later recovery.** An offline replacement used the retained generated MOV and
produced the reviewed six-case waveform result; the render was not repeated.

**Success gate.** Bind the analyzer input/output hashes and distinguish
transport failure from parser or waveform verdict.

**Unrun experiment.** No second online analyzer call was issued.

#### Outer render restoration registration and worker failure

**Path.** `../../../out/issue-141-observation-20260930-01a0f318/cli-outer-native-once-result.json`
and the outer-recovery review.

**Trigger/output.** Registration was rejected because the helper counted
original journal reads without actually reading format/mode after loading the
preset; its fake client lacked those getters. The first correction worker then
failed upstream 502 without editing or calling Resolve.

**Partial mutation.** None from the rejected registration or failed worker.

**Diagnosis and product-absence interpretation.** Review/fake-client coverage and
transport defects. They do not imply preset loading, restoration, or rendering
is unavailable.

**Later recovery.** The helper was corrected to read format/mode twice and
refuse wrong values before deletion. A later native restoration loaded and
deleted the owned preset with MOV/H264/mode 1 and exact final pair equality.

**Success gate.** Read actual post-load settings twice, compare final settings
before deletion, and bind preset ownership and final pair.

**Unrun experiment.** Hidden render fields remain unobservable; no claim of
complete hidden-setting equality is allowed.

#### 2026-10-02 — held-mute restoration first refused on render page

**Path.** `mute-render-existing-job-completion-summary.json`,
`mute-pcm-comparison-result.json`, and
`audio-mapping-restore-summary.json`.

**Trigger/output.** The post-render restoration readback refused its
Edit/empty-queue guard while Resolve remained on the render page.

**Partial mutation.** The held A2 source-mapping mute had already rendered; no
additional render or restore setter was issued on the refusal.

**Diagnosis and product-absence interpretation.** Page/queue guard state. It
does not imply mute restoration or mapping setters are unavailable.

**Later recovery.** One approved Edit-page action preceded one A2 restore; the
fresh complete pair exactly matched the original. The held-mute output PCM was
byte-identical to baseline, so the mapping flag did not prove program silence.

**Success gate.** Restore only after Edit/idle/empty-queue readiness and compare
the complete pair; treat mapping mute and audible program output as separate
claims.

**Unrun experiment.** No generalized bus/routing or live-monitor audibility
test was run.

#### 2026-10-02 — Fairlight Solo observation menu disabled

**Path.** Fairlight operator/queue/render records under `out/`.

**Trigger/output.** Operator reported A2 Solo on, but output/bus labels were not
visible. The same-job follow-up could not dispatch because the observation menu
was unavailable/disabled while rendering.

**Partial mutation.** Queue setup issued zero starts; the separately authorized
render issued exactly one start. No second start or Solo-state setter was
issued.

**Diagnosis and product-absence interpretation.** Routing labels and collector
visibility were unknown; menu availability was transient. This does not imply
Solo, routing, or render capability is absent.

**Later recovery.** The existing job completed; offline comparison found zero
A1/A3 control output and retained A2 waveform under the operator-reported Solo
state. Solo-off was later restored with exact full-state equality.

**Success gate.** Bind operator state, job UID, one-start count, generated PCM,
and exact restored pair. State only the named output controls tested.

**Unrun experiment.** Complete Fairlight bus routing and collector-backed Solo
getter coverage remain unrun.

### 5. Final reopen, duplicate, and restoration failures

#### 2026-10-02 12:13–12:22 UTC — transient Usage refusal after reopen

**Path.** `../../../out/issue-141-observation-20260930-01a0f318/r1-reopen-final-independent-review.json`.

**Trigger/output.** Save/close/load each returned success. The first post-load
capture refused eight Usage differences between adjacent reads; stable pool
reads remained available. A later pair was stable, with only eight
Resolution 0x0→1920x1080 reads on producer-timeline proxies.

**Partial mutation.** No replay, edit, duplicate, or save followed the first
refusal.

**Diagnosis and product-absence interpretation.** Transient Usage/Resolution
readback. This does not imply reopen or project persistence failure.

**Later recovery.** The stable pair was accepted for the final duplicate preflight;
the remaining selection-signature guard exposed a separate context issue.

**Success gate.** Retain every transient pair and require a later stable pair
with an explicit explanation of all deltas.

**Unrun experiment.** No atomic snapshot, revision-token, or ABA-exclusion
experiment was run.

#### 2026-10-02 12:22 UTC — second duplicate stopped on selected-context fields

**Path.** `r1-repeat-duplicate-20261002T122220.047704Z` and
`../../../out/issue-141-observation-20260930-01a0f318/r1-selected-context-local-repair.json`.

**Trigger/output.** Before `DuplicateTimeline`, the guard reported
`selected R1 source signature changed; no duplicate attempted`. Switching
between R1 and Matrix changed active/inactive track enabled/locked getters and
eight audio dialogue/voice property-presence fields.

**Partial mutation.** No duplicate, save, or cleanup occurred.

**Diagnosis and product-absence interpretation.** The structural comparator
included context-sensitive inactive getters. This does not imply duplicate
capability or source identity changed.

**Later recovery.** The repair excluded only those known context-sensitive
fields while retaining all identity, source, range, record, marker, link,
enablement, and unlisted-property guards. Independent restoration then selected
Matrix and the final duplicate created six new occurrence IDs.

**Success gate.** Capture source/structure in the same selected timeline
context, document excluded context fields, and independently review the
projection before native duplicate.

**Unrun experiment.** No cross-context universal getter equality experiment was
run; inactive getters remain unknown for control/effect claims.

#### 2026-10-02 12:54 UTC — selection-restoration launch had no main window

**Path.** `../../../out/issue-141-observation-20260930-01a0f318/independent-action-20261002T125424.498570Z/launch.json`
and `r1-restoration-menu-refusal-independent-review.json`.

**Trigger/output.** The fixed macro passed its first project-window guard, then
refused `Project changed; stop: <no main window>` before selecting the
integration menu.

**Partial mutation.** No injected result, selection setter, duplicate, or save
followed.

**Diagnosis and product-absence interpretation.** Window availability changed
between checks. This does not imply SetCurrentTimeline or duplicate support is
absent.

**Later recovery.** Read-only readiness found the exact title and enabled menu;
one bounded continuation then executed exactly one SetCurrentTimeline(Matrix)
and restored complete pair/context equality.

**Success gate.** Require one fresh readiness check, one bounded invocation, and
a complete post-selection pair before any duplicate.

**Unrun experiment.** No automatic retry after a missing-window refusal was run.

### User-reported thread transport failure (not a Resolve test)

The producer supplied this error from the chat transport: `response.create is too large for upstream websocket (33239899 bytes > 15728640 bytes)`, status 400, type `invalid_request_error`, code `payload_too_large`, parameter `input`. The error explicitly requested reducing historical images/screenshots or compacting the thread. This is conversation-level evidence; no matching original transport log is bundled with the Resolve captures, and no transport reproduction was run here.

The reported request exceeded the stated transport ceiling. It explains a refused model request, not a failed Resolve getter, macro, render or editorial operation. A focused follow-up should retain the request-size/error metadata and verify a compact, text-first continuation below the reported limit; it must separately determine whether any native action had already run before replaying an operation. Other backend 502/503 failures are retained under their individual analyzer/worker events below. A successful new model request would resolve transport availability only, not any Resolve evidence question.

### Automated validation caveat

The first independent full validation exited in the contracts Vitest lifecycle
without an available assertion. The isolated pinned-contracts rerun then passed
all 141 tests without code or test repair, and the subsequent full pinned
validation passed all 175 Python tests. An intermediate Ruff run stopped on one
overlong error-message line; splitting the same literal fixed that lint issue,
and the full validation rerun passed. These are validation-harness events, not
Resolve or product failures. Retain the first exit as unexplained evidence;
never summarize it as a failing product test.

### Evidence-retention gaps and replication rules

The following gaps materially affect how a future engineer should reproduce or
interpret the run:

1. **Retain failed preflight state before raising.** The 18:12 baseline
   refusal retained the result and hashes but not the raw current before-state.
   The 19:42 unexpected project was identified but not inspected. Future
   preflight failures need project UID/name, page/window, two full pairs, and
   normalized diff before the guard raises.
2. **Retain source-list shape.** The 21:49 matrix refusal omitted the raw
   list type/value/count. A message saying “unreadable” is insufficient to
   distinguish API shape from unreadable content.
3. **Record mutation phase and partial state.** The R4 path-list append,
   start-timecode repair, render job creation, and residual cuts all prove why
   “refused” must carry a phase-indexed journal and a read-only continuation
   plan. Never replay a phase whose successful result is already retained.
4. **Do not trust wrapper narratives over native phase records.** The boundary
   base wrapper timed out at 30 seconds while PID 38693 remained alive; the
   process was monitored to terminal, but the wrapper exit code is unavailable.
   The A3 executor narrative used preparation deselection as final context; the
   corrected raw final pair is authoritative.
5. **Keep output/analyzer failures separate.** The first PCM analyzer failed
   upstream 502/503 before extraction. A later offline analyzer produced the
   result. The failed worker is not a missing render artifact or a negative
   waveform verdict.
6. **Bind paths and hashes without exposing private paths.** Published evidence
   must use issue-local relative links and preserve raw/public hash bindings.
   Protected real-media locator/hash access remains false in the retained
   reviews.
7. **Separate observed absence from unobserved fields.** Unknown page,
   format, routing, Fairlight bus, inactive getter, or timeline proxy values
   must remain unknown. A getter that returns no data for one context is not a
   product-absence finding.
8. **Use one phase, one owner, one recovery.** Native actors must be
   single-dispatch, action-specific, and resume from retained state. A wait
   timeout or missing menu must not trigger a second start, duplicate, cut,
   save, or cleanup.

### What a successful follow-up must prove

A follow-up can close a named handoff item only when it has:

- an exact UTC timestamp and action/configuration hash;
- a complete preflight pair with page, project, selected timeline, queue,
  locks, source IDs, occurrence IDs, and relevant settings;
- a phase-indexed native journal showing the exact setter/operation and return;
- an explicit partial-state record if any later guard refuses;
- a complete postflight pair with only the allowlisted expected deltas;
- independent review of the raw pair and wrapper/native binding;
- a recovery pair that proves the owned state was restored where required; and
- a plain-language claim limited to the tested synthetic case.

No listed harness failure establishes Resolve/product absence or a failure of the
core script-to-timeline authoring workflow. The successful baseline, saved
114-item Matrix, bounded R3 samples, R4 relink/offline cycle, authored boundary,
generated render, and final duplicate all demonstrate that the investigation
reached native operations when their preconditions and evidence contracts were
correct. Their limits remain explicit: no general effect visibility, lineage,
complete mixer routing, universal audibility, fractional endpoint semantics,
atomic revision token, or protected-media access is claimed.

## What would count as a useful second opinion

For each challenged conclusion, name the claim and report one of these outcomes:

1. **Same result reproduced:** the same API/object, operation, selected context and output binding produce the observed limitation.
2. **Resolved by a different supported method:** provide the exact API/export/object type and actual observed result, plus a controlled counterexample proving it detects the relevant difference.
3. **Harness explanation:** show a local reproduction of the bad assumption, then a real application test after the correction. A passing fake alone does not resolve the application question.
4. **Still ambiguous:** preserve the missing fact and say what test would discriminate the competing explanations.

For a successful VERA inference, the test must establish the relevant source/occurrence identity, precise time mapping, coverage, selected context and freshness. Positive examples alone are insufficient: a method that always returns the source transcript, always reports Online, or always matches copied metadata can pass a simple demonstration while failing the actual reconciliation decision. Include cases that should be refused or classified unknown.

### Prioritized follow-up experiments (all unrun in this investigation)

| Priority | Question | Minimum discriminating experiment | Required success evidence |
|---|---|---|---|
| 1 | Can a documented timeline/occurrence transcript method avoid source-range reconstruction? | Compare unedited, phrase-cut, repeated/overlapping and picture-only-cut timelines, invoking each method on its documented object type. | Timed words differ correctly for each occurrence edit; source text is kept distinct; errors/missing coverage remain explicit. Verify whether it describes editing structure or rendered speech. |
| 2 | Which documented mute/Solo/routing controls affect program output? | Separate source mapping mute, timeline-item enable, track enable, Fairlight Mute and Solo; use distinguishable signals per track, explicit buses and a baseline render for each. | Output changes follow the exact control and routed signal; all paths are covered, including sends and residual tracks. A readback flag alone cannot establish silence. |
| 3 | Is there stronger lineage evidence? | Copy, razor, duplicate, relink and intentionally duplicate markers/signatures; compare any proposed origin identifier/provenance method. | Correct ancestry is recovered or the result refuses when two candidates are indistinguishable; reopened and duplicated timelines preserve the intended semantics. |
| 4 | Are source ranges accurate for partial words and speed changes? | Use impulses/non-frame-aligned signal edges at normal, fractional and changing speed; include audio/video unlink and offset. | Actual rendered sample/frame support matches a declared rounding and time-mapping rule; partial speech is classified explicitly. |
| 5 | Can visibility be observed beyond simple layers? | Test transitions, opacity animation, crop/transforms, masks, OpenFX/Fusion and nested content against frame output. | Predicted visible contributions match every relevant output frame or unsupported combinations are rejected. |
| 6 | Can media-byte identity and replacement display be separately attested? | Same-name/same-metadata wrong bytes, relink with cache variations, proxies/optimized media and known distinguishable frames. | The method distinguishes file identity from the bytes actually displayed; source mismatches trigger review even when IDs/Online remain stable. |
| 7 | Can review/apply freshness be guaranteed? | Controlled edit, edit-and-undo (ABA), selection changes, reopen and an edit between the final read and apply. | A documented revision/snapshot mechanism or proven guarded workflow invalidates stale authorization; equality of two reads alone is insufficient. |

## Evidence access and reproducibility limits

The historical run's scripts and records are local working-tree artifacts, including ignored output. A GitHub issue number or branch name does not make these files available to another AI. Provide this handoff plus the referenced artifacts if independent auditing of the original result is required.

Minimum materials for auditing:

- [Final findings](final-findings.md), [chronological report](report.md), [operator record](operator-record.md), [operator checklist](operator-checklist.md), [plan](../../plans/issue-141-resolve-observation.md), and [41-title evidence audit](../../../output/issue141-per-title-evidence-audit.json).
- The linked real before/after captures, call journals, independent reviews, result wrappers and original source/configuration hash bindings for each disputed case. Published path-redacted captures and private raw captures can have different hashes; consult the named `hashes.json` rather than equating them.
- [Synthetic manifest](inputs/manifest.json), the allowlisted generated source files, associated rendered PCM/still outputs and analysis/checker sources. Generated inputs are not rendered-output evidence.
- A matching installed API README/stub, including their recorded hashes. Different Resolve releases/object wrappers should be reported as a different setup, not silently equated.
- The exact helper version used in that result, selected using the installation record or archived helper hash. Current helper files changed over the investigation; they are not necessarily the code used in an earlier capture.

The human's real source clip is not part of a general shareable synthetic evidence bundle. For a new speech experiment, use a separately authorized clip with known spoken content and preserve its consent/coverage boundaries. Missing original footage does not prevent testing the method on a new source, but it does prevent byte-for-byte reproduction of that specific real-source experiment.

The final native result is `vera-issue-141-observation-result-20261002T131625.143034Z.json`, SHA-256 `117fcc6ae0f432b9160436faf3053982df7c3f5417a51fa2efd922fa661d92dd`. The corresponding [final seven-timeline independent review](../../../output/r1-final-seven-independent-review.json) has verdict `PASS_WITH_EXPLICIT_LINEAGE_LIMIT`. These identify the last completed native sequence; they do not authorize another launch.

### New-result record template

Use the following fields for each independent experiment. This is a reporting template, not a claim that these follow-ups ran.

```text
Claim being challenged:
Run identifier / date / host:
Resolve edition / full version / Python / scripting entry:
API documentation version and hash:
Exact project / timeline / occurrence / source identifiers:
Relevant source-byte or protected-metadata provenance:
Preconditions (selection, page, playhead, tracks, routes, queue, controls):
Known signal/text/frame ground truth and interval convention:
Expected result and counterexample that must be rejected:
Exact calls/menu operations, parameters and returns:
Before/after raw captures and SHA-256:
Action journal and terminal result:
Rendered/exported evidence, extraction method and state binding:
Measured result (including errors, None, omitted fields, residuals):
Restoration evidence / retained partial state:
Repeat and independent comparison:
Classification: bounded support / adverse result / unknown / harness failure:
Alternative explanation still possible:
Effect on VERA and success requirement met or still missing:
```

### Source and checker catalog

These files are supplied as evidence and starting points. Mutating helpers were invoked through the injected integration with specific hashed state bindings; running a Python file directly is not an equivalent test. Checker results validate the harness/comparison, not Resolve behavior. Many require historical paths/IDs; inspect their entry point and arguments before using them with a new experiment.

| Area | Sources / analyses | Relevant local checks |
|---|---|---|
| Input generation and baseline | [prepare-media.py](prepare-media.py), [probe.py](probe.py), [entry point](VERA%20Issue%20141%20Observation.py) | [check.py](check.py), [launcher-check.py](launcher-check.py) |
| Native dispatch and selection | [hammerspoon-launch.lua](hammerspoon-launch.lua), [hammerspoon-editorial.lua](hammerspoon-editorial.lua), [editorial-readback.py](editorial-readback.py) | [hammerspoon-check.lua](hammerspoon-check.lua), [hammerspoon-editorial-check.lua](hammerspoon-editorial-check.lua), [editorial-readback-check.py](editorial-readback-check.py), [dispatch-registration-check.py](dispatch-registration-check.py) |
| Editorial cases | [editorial-cases.py](editorial-cases.py), [r1-razor.py](r1-razor.py), [r1-move-driver.py](r1-move-driver.py), [editorial-restore.py](editorial-restore.py) | [editorial-cases-check.py](editorial-cases-check.py), [r1-trim-evidence-check.py](r1-trim-evidence-check.py), [r1-move-evidence-check.py](r1-move-evidence-check.py), [r1-razor-evidence-check.py](r1-razor-evidence-check.py), [r1-copy-evidence-check.py](r1-copy-evidence-check.py) |
| Reopen and duplicate | [r1-repeat-six.py](r1-repeat-six.py), [second-duplicate.py](second-duplicate.py), [reopen-check.py](reopen-check.py) | [r1-repeat-six-check.py](r1-repeat-six-check.py), [second-duplicate-check.py](second-duplicate-check.py) |
| Audio setters/output/mapping | [audio-cases.py](audio-cases.py), [audio-output.py](audio-output.py), [av-output.py](av-output.py), [audio-mapping-readonly.py](audio-mapping-readonly.py), [audio-mapping-mute.py](audio-mapping-mute.py) | [audio-cases-check.py](audio-cases-check.py), [audio-output-check.py](audio-output-check.py), [av-output-check.py](av-output-check.py), [audio-mapping-readonly-check.py](audio-mapping-readonly-check.py), [audio-mapping-mute-check.py](audio-mapping-mute-check.py), [program-pcm-check.py](program-pcm-check.py) |
| Output restoration | [audio-render-recovery.py](audio-render-recovery.py), [render-outer-recovery.py](render-outer-recovery.py) | [audio-render-recovery-check.py](audio-render-recovery-check.py), [render-outer-recovery-check.py](render-outer-recovery-check.py) |
| Picture samples | `picture_calibration` / `picture_cases` in [probe.py](probe.py), [offline-picture.py](offline-picture.py) | [picture-check.py](picture-check.py), [offline-picture-check.py](offline-picture-check.py) |
| Availability/byte identity | [r4-transitions.py](r4-transitions.py), [offline-cycle.py](offline-cycle.py), [r4-wrong-bytes.py](r4-wrong-bytes.py), [r4-removal.py](r4-removal.py), [r4-reprepare.py](r4-reprepare.py) | [r4-transitions-check.py](r4-transitions-check.py), [offline-cycle-check.py](offline-cycle-check.py), [r4-wrong-bytes-check.py](r4-wrong-bytes-check.py), [r4-removal-check.py](r4-removal-check.py), [r4-reprepare-check.py](r4-reprepare-check.py) |
| Freshness | [r5-freshness.py](r5-freshness.py) | [r5-freshness-check.py](r5-freshness-check.py), [r5-edit-evidence-check.py](r5-edit-evidence-check.py) |
| Transcript readback | [transcription-readback.py](transcription-readback.py), [producer-transcript-probe.py](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-probe.py) | [transcription-readback-check.py](transcription-readback-check.py), [producer-transcript-probe-check.py](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-probe-check.py) |

Original focused check records and the initial full validation are documented in [report.md](report.md). A contracts-test lifecycle exited once without an available assertion, then isolated and full pinned runs passed without a contract-test repair; that original failure remains unexplained. The validation history is harness/code evidence and cannot substitute for native captures or output. No broad validation rerun was required to write this document.

## Complete original check inventory

This appendix retains every planned dashboard title and its evidence references. It uses the existing evidence audit; it does not rerun the tests. The detailed sections above give experiment steps and inference limits. The sole unfinished entry is final External review; it is not a pending native test.

| # | Planned title | Status | Retained references |
|---:|---|---|---|
| 1 | Investigation setup | done | [issue-141-resolve-observation.md](../../plans/issue-141-resolve-observation.md); [report.md](report.md) |
| 2 | Generated synthetic media and manifest | done | [hashes.json](evidence/baseline-preparation/hashes.json); [identity.json](evidence/baseline-preparation/identity.json) |
| 3 | Harness checks | done | [check.py](check.py); [report.md](report.md) |
| 4 | Named project and baseline timeline | done | [summary.json](evidence/baseline-preparation/summary.json); [operator-record.md](operator-record.md) |
| 5 | Batched matrix prepared and saved | done | [summary.json](evidence/matrix-finalize-success/summary.json); [matrix-finalize-success](evidence/matrix-finalize-success) |
| 6 | Duration convention calibration | done | [endpoint-calibration-independent-verdict.json](../../../out/issue-141-observation-20260930-01a0f318/endpoint-calibration-independent-verdict.json); [endpoint-calibration-corrected-review.json](../../../out/issue-141-observation-20260930-01a0f318/endpoint-calibration-corrected-review.json) |
| 7 | Overlay placement and visibility calibration | done | [summary.json](evidence/picture-calibration-success/summary.json); [picture-calibration-success](evidence/picture-calibration-success) |
| 8 | R1-reopen: reopen exact project and compare IDs, custom data, ranges | done | [summary.json](evidence/native-duplicate-success/summary.json); [summary.json](evidence/after-reopen-read-only/summary.json) |
| 9 | R1-duplicate: DuplicateTimeline to VERA 141 R1 identity; compare both timelines | done | [summary.json](evidence/native-duplicate-success/summary.json); [native-duplicate-success](evidence/native-duplicate-success) |
| 10 | R1-trim: trim a separate labeled linked occurrence by 25 frames | done | [r1-trim-success](evidence/r1-trim-success) |
| 11 | R1-move: move a separate labeled linked occurrence 25 frames later | done | [r1-move-success](evidence/r1-move-success) |
| 12 | R1-razor: blade a separate labeled linked occurrence at local frame 100 | done | [independent-comparison.json](evidence/r1-razor-success/independent-comparison.json); [independent-comparison.json](evidence/r1-razor-context-restored/independent-comparison.json) |
| 13 | R1-copy: copy/paste one linked piece at a nonoverlapping location | done | [r1-copy-paste-stopped](evidence/r1-copy-paste-stopped); [r1-copy-restore-review.json](evidence/r1-copy-paste-stopped/r1-copy-restore-review.json) |
| 14 | R1-repeat: save/reopen repeat and second named duplicate | done | [summary.json](evidence/native-close-refusal/summary.json); [summary.json](evidence/native-reopen-cache-refusal/summary.json); [summary.json](evidence/native-duplicate-success/summary.json); [r1-registration-readiness.json](../../../output/r1-registration-readiness.json); [r1-repeat-six-readiness.md](r1-repeat-six-readiness.md); [r1-reopen-final-independent-review.json](../../../output/r1-reopen-final-independent-review.json); [r1-selected-context-independent-review.json](../../../output/r1-selected-context-independent-review.json); [r1-selection-restoration-independent-review.json](../../../output/r1-selection-restoration-independent-review.json); [r1-selection-restoration-local.json](../../../output/r1-selection-restoration-local.json); [r1-restoration-menu-refusal-record.json](../../../output/r1-restoration-menu-refusal-record.json); [r1-final-native-executor-20261002-state.json](../../../output/r1-final-native-executor-20261002-state.json); [launch.json](../../../out/issue-141-observation-20260930-01a0f318/independent-action-20261002T125424.498570Z/launch.json); [r1-restoration-menu-refusal-independent-review.json](../../../output/r1-restoration-menu-refusal-independent-review.json); [r1-selection-restoration-native-independent-review.json](../../../output/r1-selection-restoration-native-independent-review.json); [r1-final-seven-independent-review.json](../../../output/r1-final-seven-independent-review.json); [r1-final-accepted-evidence.json](../../../output/r1-final-accepted-evidence.json) |
| 15 | R2-linked-cut: remove frames 60–70 on linked V1/A1 | done | [r2-linked-physical-cut](evidence/r2-linked-physical-cut); [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json) |
| 16 | R2-unlinked-cut: unlink and remove interval on A1 only | done | [r2-unlinked-physical-cut](evidence/r2-unlinked-physical-cut); [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json) |
| 17 | R2-picture-only: remove interval on V1 only | done | [summary.json](evidence/audio-cases-success/summary.json); [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json) |
| 18 | R2-partial: remove only frames 65–70 on A1 | done | [summary.json](evidence/audio-cases-success/summary.json); [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json) |
| 19 | R2-residual-track: enable A2 repeated-speech occurrence | done | [summary.json](evidence/audio-cases-success/summary.json); [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json) |
| 20 | R2-disable-mute: compare enabled/disabled, mute/solo, routing and output | done | [summary.json](evidence/audio-cases-success/summary.json); [solo-output-comparison-result.json](../../../out/issue-141-observation-20260930-01a0f318/solo-output-comparison-result.json); [fairlight-render-completion-summary.json](../../../out/issue-141-observation-20260930-01a0f318/fairlight-render-completion-summary.json); [solo-off-restored-state-20261002T121158.440922Z.json](../../../out/issue-141-observation-20260930-01a0f318/solo-off-restored-state-20261002T121158.440922Z.json) |
| 21 | R2-offset: shift unlinked A1 one frame without changing source bounds | done | [summary.json](evidence/audio-cases-success/summary.json); [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json) |
| 22 | R2-retime: set linked clip to 50% and capture source map | done | [summary.json](evidence/audio-cases-success/summary.json); [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json) |
| 23 | R2-derived-end: compare subframe/source-time values to exact sample support | done | [endpoint-calibration-independent-verdict.json](../../../out/issue-141-observation-20260930-01a0f318/endpoint-calibration-independent-verdict.json); [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json) |
| 24 | R3-opaque: enable V2 and inspect frames 49, 50, 99, 100 | done | [summary.json](evidence/picture-cases-success/summary.json); [picture-cases-success](evidence/picture-cases-success) |
| 25 | R3-transparent: enable V3 and inspect overlap and return frames | done | [summary.json](evidence/picture-cases-success/summary.json); [picture-cases-success](evidence/picture-cases-success) |
| 26 | R3-effect: apply identified effect and record settings/viewer result | done | [summary.json](evidence/picture-cases-success/summary.json); [picture-cases-success](evidence/picture-cases-success) |
| 27 | R3-disabled: disable cutaway and overlay separately | done | [summary.json](evidence/picture-cases-success/summary.json); [picture-cases-success](evidence/picture-cases-success) |
| 28 | R3-offline: use R4 unlink probe and inspect present offline occurrence | done | [summary.json](evidence/offline-cycle-continuation-success/summary.json); [summary.json](evidence/picture-cases-success/summary.json) |
| 29 | R3-merge-graphic: blade V1/A1 under enabled V3; keep Graphic distinct | done | [r3-graphic-native-executor-result.json](../../../out/issue-141-observation-20260930-01a0f318/r3-graphic-native-executor-result.json); [result.json](../../../out/issue-141-observation-20260930-01a0f318/r3-graphic-deselected-20261001T195652.401414Z/result.json); [graphic-full-pair-independent-review.json](../../../out/issue-141-observation-20260930-01a0f318/graphic-full-pair-independent-review.json) |
| 30 | R3-boundary: blade base A/V at frame 100, then A3 crossing bed | done | [result.json](../../../out/issue-141-observation-20260930-01a0f318/r3-boundary-split-20261001T203852.778627Z/result.json); [result.json](../../../out/issue-141-observation-20260930-01a0f318/r3-boundary-a3-split-20261001T204503.938058Z/result.json); [boundary-complete-independent-review.json](../../../out/issue-141-observation-20260930-01a0f318/boundary-complete-independent-review.json); [boundary-base-native-executor-result.json](../../../out/issue-141-observation-20260930-01a0f318/boundary-base-native-executor-result.json) |
| 31 | R3-visibility interpretation: bound claims to inspected frames/effects | done | [report.md](evidence/visibility-interpretation/report.md); [report.md](report.md); [analysis.json](evidence/visibility-interpretation/analysis.json) |
| 32 | R4-unlink: unlink synthetic base.mov pool item; capture occurrence/status | done | [summary.json](evidence/offline-cycle-continuation-success/summary.json); [summary.json](evidence/r4-offline-prefix-read-only/summary.json) |
| 33 | R4-relink: relink exact item to same-byte generated candidate | done | [summary.json](evidence/offline-cycle-continuation-success/summary.json); [summary.json](evidence/r4-recovery-success/summary.json) |
| 34 | R4-wrong-bytes: staged same-locator replacement and refresh/reopen | done | [summary.json](evidence/r4-wrong-bytes-success/summary.json) |
| 35 | R4-remove: compare removed occurrence with offline-present case; journal restore | done | [independent-comparison.json](evidence/r4-removal-success/independent-comparison.json); [independent-comparison.json](evidence/r4-reprepare-read-only/independent-comparison.json) |
| 36 | R5-quiet: separate-launch quiet comparison | done | [summary.json](evidence/quiet-repeat/summary.json) |
| 37 | R5-reopen: compare markers, IDs, ranges and settings after reopen | done | [summary.json](evidence/after-reopen-read-only/summary.json); [summary.json](evidence/native-duplicate-success/summary.json) |
| 38 | R5-marker-and-move: edit marker note, then move one clip one frame | done | [summary.json](evidence/r5-manual-marker-move/summary.json); [r5-independent-fresh-comparison-20261001T181642Z.json](../../../out/issue-141-observation-20260930-01a0f318/r5-independent-fresh-comparison-20261001T181642Z.json) |
| 39 | R5-concurrent-edit: bounded edit during capture; retain refusal if inconsistent | done | [summary.json](evidence/r5-capture-loop-success/summary.json); [summary.json](evidence/r5-controlled-metadata/summary.json) |
| 40 | Complete evidence report and bounded interpretations for every R1–R5 result | done | [report.md](report.md); [operator-record.md](operator-record.md); [operator-checklist.md](operator-checklist.md); [final-findings.md](final-findings.md); [r1-final-seven-independent-review.json](../../../output/r1-final-seven-independent-review.json) |
| 41 | External evidence review and remaining operator judgments | pending | [operator-record.md](operator-record.md); [operator-checklist.md](operator-checklist.md) |
