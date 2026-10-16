# Issue 141 — R2 audio, timing, mute, Solo, and supplemental transcript evidence handoff

**Task ID:** Issue 141 / handoff_audio_v2  
**Evidence boundary:** retained Issue 141 evidence only; no Resolve launch, probe, stage, render, test rerun, or protected semi1b.mp4 byte/hash read was performed for this handoff.  
**Assumed document location for links:** docs/investigations/issue-141/second-opinion-handoff.md. Links below are intentionally relative to that location.

This handoff covers the six R2 generated-audio cases, the generated-output comparison, endpoint/timing calibration, channel-mapping mute, Fairlight Solo output, and the supplemental producer-authored transcript experiment. The tested application was DaVinci Resolve Studio 21.1.0 build 14, project VERA Issue 141 Synthetic Probe 20260930-01a0f318, selected Matrix timeline VERA 141 Batched Matrix (UID 29ae8331-b86e-4041-a548-960695cc7b24). The evidence is bounded to the named synthetic media and the exact retained readbacks.

The evidence has three separate layers:

1. **Native state:** a Resolve getter or setter call, its return value, and a complete before/after pair.
2. **Rendered output:** a terminal owned render, extracted PCM, source-support correlation, and control-window energy.
3. **Operator state:** UI-held Fairlight Mute/Solo/M/S labels that the tested collector did not expose.

A successful setter is evidence for layer 1 only. A rendered waveform is evidence for layer 2 only. An operator report is evidence for layer 3 only. None of these layers should be silently substituted for another.

## Retained evidence and replication map

The consolidated findings and chronology are [final-findings.md](final-findings.md) and [report.md](report.md). The primary R2 artifacts are:

- [audio-cases-success/summary.json](evidence/audio-cases-success/summary.json): 14 equal-adjacent capture points, all six native reversible state cases, setter calls, retime fields, and limits.
- [pcm-r2-independent-completion-review.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-r2-independent-completion-review.json): independent review of the terminal generated render, full-pair binding, six case findings, and exact PCM metrics.
- [pcm-real-render-analysis.json](../../../out/issue-141-observation-20260930-01a0f318/pcm-real-render-analysis.json): source-support comparisons and output sample bindings.
- [endpoint-calibration-independent-verdict.json](../../../out/issue-141-observation-20260930-01a0f318/endpoint-calibration-independent-verdict.json) and [endpoint-calibration-corrected-review.json](../../../out/issue-141-observation-20260930-01a0f318/endpoint-calibration-corrected-review.json): the distinguishing 100% endpoint result and its scope.
- [mute-pcm-comparison-result.json](../../../out/issue-141-observation-20260930-01a0f318/mute-pcm-comparison-result.json): held mapping-mute output versus the unmuted baseline.
- [cli-mute-native-once-result-reviewed.json](../../../out/issue-141-observation-20260930-01a0f318/cli-mute-native-once-result-reviewed.json) and [audio-mapping-restore-summary.json](../../../out/issue-141-observation-20260930-01a0f318/audio-mapping-restore-summary.json): native mapping mutation, restoration, first post-render refusal, and exact final pair.
- [solo-output-comparison-result.json](../../../out/issue-141-observation-20260930-01a0f318/solo-output-comparison-result.json), [fairlight-operator-solo-on.json](../../../out/issue-141-observation-20260930-01a0f318/fairlight-operator-solo-on.json), and [solo-off-restored-state-20261002T121158.440922Z.json](../../../out/issue-141-observation-20260930-01a0f318/solo-off-restored-state-20261002T121158.440922Z.json): the bounded Solo output, operator state, and restoration evidence.
- [r1-fairlight-api-doc-audit.json](../../../output/r1-fairlight-api-doc-audit.json): installed README/stub search for mapping, Solo, and bus/output APIs.
- [producer-transcript-probe.py](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-probe.py), [producer-transcript-probe-20261001T170340.864739Z/raw-readback.json](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-probe-20261001T170340.864739Z/raw-readback.json), [producer-transcript-range-comparison.json](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-range-comparison.json), and [producer-transcript-range-independent-review.json](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-range-independent-review.json): exact getter calls, source words/times, occurrence geometry, derived comparison, and independent limits.
- [transcription-readback.py](transcription-readback.py) and [transcript-coverage-requirement.md](transcript-coverage-requirement.md): the separate read-only source/proxy readback and the adopted future coverage/freshness requirement.

The terminal full-Matrix render used by the R2 review was one owned job, job ID a6ed7f33-9ad4-4d82-bfac-ff72903f4567, with one StartRendering request and a later same-job completion observation. The native MOV hash was 8af6fb6916afa4c1bc674617ad52460928582a3dbc22dd2af8550786bd28020c. Its extracted PCM was PCM24 stereo, 48 kHz, 17,664,000 sample frames per channel, 368 seconds, hash d2581dc047a348a104821cbd53c7b84e4a47b80fd4443ebf52f6fbd3382362a. The generated repeated.wav comparator source was PCM16 mono, 48 kHz, 384,000 samples, hash 832dd31cc46b9f4b4fdb7cbde18b4edc09ec249885634fba43da2a7b87dc768e. No protected presenter-media bytes were opened or hashed.

## Exact GetTranscription object and method distinction

The retained producer probe did not read a property named transcription and did not call GetTranscription on a Timeline or TimelineItem. It used method dispatch equivalent to:

    _call(item, "GetTranscription", nested)

for nested equal to False and True, with two adjacent reads per mode. The implementation is visible in [producer-transcript-probe.py](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-probe.py:207) and the target loop at [producer-transcript-probe.py](../../../out/issue-141-observation-20260930-01a0f318/producer-transcript-probe.py:613).

The installed DaVinciResolveScript.pyi does define MediaPoolItem.GetTranscription(useNestedClipTranscription=False) -> Transcription at lines 2098–2100. The same stub defines Timeline.GetMediaPoolItem() -> MediaPoolItem at lines 2272–2273 and TimelineItem.GetMediaPoolItem() -> MediaPoolItem at lines 2353–2354, but it does not define TimelineItem.GetTranscription. The installed README search retained in [r1-fairlight-api-doc-audit.json](../../../output/r1-fairlight-api-doc-audit.json) did not find a GetTranscription entry; the stub is the authoritative retained type declaration for this method search.

The probe used these distinct objects:

- **Source MediaPoolItem:** it selected the unique source handle returned by TimelineItem.GetMediaPoolItem() from the video/audio occurrences in the two named timelines. This source was semi1b.mp4, UID be5f1584-f0c4-4dd9-988b-73f3167e77d1. Calling GetTranscription(False) and GetTranscription(True) on that MediaPoolItem returned stable word-level data on both adjacent reads.
- **Timeline pool proxy MediaPoolItem:** for each named timeline, it called Timeline.GetMediaPoolItem(), then called GetTranscription(False/True) on the returned MediaPoolItem proxy. Both proxies returned a successful call with value None on both reads in both modes. The retained state is value/missing, getterMissing false, equal-adjacent-reads; it is not a thrown missing-method error.
- **Timeline and TimelineItem:** these objects supplied timeline identity, occurrence lists, source identity, track, record/source bounds, speed, and enabled state. Their GetMediaPoolItem() methods supplied the MediaPoolItem handles above. No claim was made that a TimelineItem itself has a direct transcript getter.

This is the exact observed distinction: source-level MediaPoolItem transcription was present; the two timeline-level pool-proxy MediaPoolItem transcriptions were null. It is evidence for these two proxies in this project/build/readback, not a global Resolve API absence claim. The source-item loop can return the same complete source transcript for both pieces of test 2, including words excluded by the edit; cut-aware reconstruction must intersect that source transcript with each enabled audio occurrence's source range.

## R2 native cases and rendered PCM

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

### R2 timing and retime observations

The 50% R2 retime setter returned true; this state-only retime was restored to 100%. For the named V1 retime item, retained fields changed from GetRightOffset 1 to 201, GetSourceEndFrame 199 to 99, GetSourceEndTime 7.96 to 4.0, and GetSpeed Percentage 100.0 to 50.0 while PitchCorrection stayed true. The linked A1 changed-field list was empty. This is a statement about the captured V1 and A1 readbacks; it is not a broad conclusion about all linked clips.

The corrected unlinked-cut review also retained an observed schema difference: after unlinking, the target video GetSpeed value omitted the PitchCorrection key that had been true in the prior pair. The review preserved that omission exactly. It is a getter/readback representation difference, not evidence that pitch correction was reset.

## Endpoint calibration

The independently verified calibration is limited to generated 100% speed integer-valued cases:

- The generated 100% audio tail reports GetStart 9100, GetEnd 9199, GetDuration 99, GetSourceStartFrame 100, and GetSourceEndFrame 199. Integer and float overloads agree for these integer-valued observations.
- Rendered timeline frame 9198 is nonzero and correlates to generated source frame 198. Timeline frame 9199 is exactly silent even though generated source frame 199 is nonzero. This supports an exclusive upper end for this named audio item.
- The rendered output is 9,200 timeline frames and 17,664,000 samples per channel, which verifies whole-output rate/duration arithmetic only.
- The retained 50% capture reports source end frame 99 and source end time 4.0. That pair does not establish a universal frame-to-time convention; the 50% readback is raw observation only.

Fractional start/end/duration, generalized retime endpoints, alternate frame rates, effects, and other Resolve getters remain untested. Preserve GetStart, GetEnd, GetDuration, source frame fields, source time fields, and render MarkOut as separate raw observations.

## Mapping mute: native setter versus final output

The mute operation targeted the generated residual A2 TimelineItem UID f4e9f649-894a-42f2-9f54-a8321ae7c163 on Audio 2 over [4500,4699), source repeated.wav. The operation used TimelineItem.SetSourceAudioChannelMapping with the exact JSON mapping:

    {"embedded_audio_channels":1,"linked_audio":{},"track_mapping":{"1":{"channel_idx":[1],"mute":true,"type":"mono"}}}

The pre-mutation and restored JSON had mute false. Both native setter calls returned true. The before pair and restored pair have the same SHA-256 d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14; the held muted pair differed only at the target mapping. The pool-level GetAudioMapping and TimelineItem-level GetSourceAudioChannelMapping getters were successful for the retained mapping review, but these are source-channel mapping/clip-attribute observations, not Fairlight track or bus state.

The held-mute render completed as job c5b1925b-f5aa-49d5-850a-be7a64c5cd29. Its extracted PCM SHA-256 was exactly the same as the unmuted baseline: d2581dc047a348a104821cbd53c7b84e4a47b80fd4443ebf52f6fbd3382362a. Both channels were byte-identical for the entire 17,664,000-sample output, including target [4500,4699), speech-gap [4560,4570), and frame 4570. The gap's baseline/held RMS was 0.0891571253533794; different samples were zero.

This is a reproduced limitation of treating the observed mapping mute flag as proof of program silence in this case. It is not evidence of universal API failure. After the render, one restoration preflight refused because Resolve was on the render page; one approved Edit-page action made the same exact mapping restoration possible, and the final pair matched the original. The refusal and successful restore are retained in [audio-mapping-restore-summary.json](../../../out/issue-141-observation-20260930-01a0f318/audio-mapping-restore-summary.json).

## Fairlight Solo and output comparison

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

## Supplemental transcript experiment

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

The exact occurrence geometry is:

| Timeline | Enabled audio occurrence(s) | Source-aligned words |
|---|---|---:|
| transcription test 1, UID 21436b8f-057c-49e6-80ba-5f733abe87b2 | Timeline [90000,90255), source [841,1147), 100% speed | 22 |
| transcription test 2, UID 2db0b2d1-6d81-48d4-b49c-360f56e012cd | Timeline [90000,90059), source [841,912), then timeline [90059,90220), source [954,1147), both 100% speed | 19 |

At nominal 29.97 fps, source timing and occurrence geometry agree within about 1.6 source frames. Test 2's first range ends 0.874 frames after the retained Finns word end and 2.126 frames before singing starts. Its second range starts 2.091 frames after Swedish ends. The retained source-range mapping is internally consistent and producer-accepted, but approximately two-frame endpoint uncertainty means edge clipping cannot be ruled out. No direct timeline-proxy transcript was returned, and source transcript plus enabled ranges do not prove final-mix audibility.

The proposed source loop has a specific consequence: TimelineItem.GetMediaPoolItem().GetTranscription() reads the source MediaPoolItem transcription, so both test-2 pieces can return the same complete source data, including omitted words. A video-track-only loop also misses audio-only occurrences and does not account for disabled state, mapping mute, Fairlight routing, repeated use, or speed. VERA must preserve source transcript, timeline occurrence, and timeline-proxy results as separate evidence.

## Known limitations and retained failures

Each item below states how to reproduce the observation, what would be required to call it successful for VERA, and an explicitly unrun experiment. “Unrun” means proposed only; it was not performed for this handoff.

### 1. Mapping mute did not change program PCM

- **Classification:** Reproduced bounded output limitation; native mapping mutation succeeded, program-output mute did not follow in this case.
- **Setup/action/observation:** On the generated residual A2 TimelineItem over [4500,4699), call SetSourceAudioChannelMapping with track 1 mute true, require true return and target-only pair delta, render the held state, extract PCM, and compare with the unmuted baseline. The complete waveform was byte-identical, including the target and speech-gap windows.
- **Requirement to claim success:** VERA may call a mute effective only after it binds the correct layer (source mapping, clip, track, or bus) and observes the intended output change in a controlled render or an equivalent verified output path, followed by exact restoration.
- **VERA consequence:** Mapping mute alone cannot classify speech as absent and cannot authorize spoken-omission reconciliation. Route-ambiguous cases require stronger output evidence or manual review.
- **Proposed unrun experiment:** On a fresh generated-only matrix, compare source mapping mute, TimelineItem clip enable, track enable, and a producer-confirmed Fairlight track/bus mute one at a time, with isolated source and output controls. No such experiment is authorized or run here.

### 2. Fairlight Solo and bus routing are collector gaps

- **Classification:** Bounded successful Solo-sensitive output with unresolved state/routing attribution; documentation search gap, not a global API absence.
- **Setup/action/observation:** Operator reported A2 Solo on; bus labels were not visible. One owned full-Matrix render retained zero A1/A3 control output and near-unit A2 source correlation. The full-pair collector and installed docs/stub exposed no Solo or bus/output-routing field.
- **Requirement to claim success:** VERA needs direct and fresh Solo/Mute/M/S state evidence, complete source-to-track-to-bus routing evidence, a terminal output comparison with isolated controls, and exact restoration. A pair hash alone is insufficient because Solo is absent from the pair.
- **VERA consequence:** The Solo output supports only the named bounded control result. Transcript/source-range evidence cannot be promoted to general audibility or deletion.
- **Proposed unrun experiment:** Capture producer-visible Fairlight track and bus labels or a verified public routing getter, then render Solo-on, Solo-off, and isolated-track controls from equal checkpoints. This was not run.

### 3. Render settings and output setup had bounded refusals

- **Classification:** Harness/precondition and getter-observability failures, not Resolve audio-capability failures.
- **Setup/action/observation:** One exact owned XML import refused before a render and left the pair unchanged ([audio-render-import-refusal](evidence/audio-render-import-refusal/summary.json)). A SetRenderSettings call returned true, but subsequent GetCurrentRenderFormatAndCodec returned codec empty/format unknown; original ExportVideo is not exposed by that getter or explicit XML field ([audio-settings-restoration-refusal](evidence/audio-settings-restoration-refusal/observed-state.json)). A video-toggle attempt remained unresolved with the same unknown format state ([audio-video-toggle-unresolved](evidence/audio-video-toggle-unresolved/summary.json)). The later AV path used one owned MOV render and a separate verified restoration; hidden settings equality remains unexposed.
- **Requirement to claim success:** Bind a terminal successful job, exact output path/hash/format, requested audio/video settings, and a post-render restoration whose observable fields match the original. Keep hidden/unreadable settings explicitly unknown.
- **VERA consequence:** Queue/setup success or a true setter return is not output evidence. Output-dependent reconciliation must wait for the terminal output handoff and retain unknown settings.
- **Proposed unrun experiment:** Use a generated-only disposable render preset whose audio/video toggles are independently distinguishable in the final output and whose getter/XML fields are fully observable. No new render-settings experiment was run.

### 4. Render observation and PCM analysis had transport/availability failures

- **Classification:** External tool/launcher failure with retained recovery; no native capability conclusion.
- **Setup/action/observation:** The first PCM analyzer hit upstream 502/503 errors before extraction/comparison. A Solo same-job observation initially refused because the observation menu was disabled while the render was at 1%; the existing job later completed and was observed without a second start. The final PCM comparison was offline against the retained terminal output.
- **Requirement to claim success:** Require a terminal job result and hash-bound output handoff before opening output bytes; never infer from a partial render or a failed comparator.
- **VERA consequence:** The retained generated-only metrics are valid for the completed output only. A failed analyzer or disabled menu is not evidence of absent Resolve rendering or audio.
- **Proposed unrun experiment:** Add a local-only comparator path with no upstream dependency and a read-only terminal-job wait protocol; this was not rerun or added here.

### 5. Timing is calibrated only for integer-valued 100% cases

- **Classification:** Bounded endpoint success; fractional and generalized retime semantics unresolved.
- **Setup/action/observation:** Generated 25 fps/48 kHz tail and adjacent PCM samples distinguish frame 9198 from silent frame 9199 while source frame 199 remains nonzero. Float overloads match integer-valued getters. The 50% retime reports source end 99/time 4.0 and changed V1 fields while linked A1 changed fields stayed empty; the retained 50% read is not a generalized calibration.
- **Requirement to claim success:** For each method/domain, retain raw integer and float getter values plus adjacent distinguishing output. Fractional precision requires a non-integral boundary and output sample/frame evidence.
- **VERA consequence:** Preserve raw endpoints and use explicit precision labels. Do not derive duration as end minus start or assume all end fields share one convention. Word-edge cuts remain reviewable/ambiguous.
- **Proposed unrun experiment:** Use new generated frame-varying media with at least one non-integral boundary and 25/29.97 retime cases, retaining getter overloads and adjacent output frames. No such experiment was run.

### 6. Direct timeline-proxy transcripts are missing

- **Classification:** Observed null values on exactly two timeline pool proxies; collector/project scope limitation.
- **Setup/action/observation:** Call MediaPoolItem.GetTranscription(False/True) twice on the source MediaPoolItem and on each Timeline.GetMediaPoolItem() proxy. Source returns value; both proxies return None with stable missing state. TimelineItem occurrence getters return source identity and geometry, not a direct transcript.
- **Requirement to claim success:** A transcript-based reconciliation path needs complete coverage for its relevant clips/occurrences, with source/proxy object identity, freshness, stable values and a verified time map. Missing proxy results block claims based on a direct timeline transcript; they do not by themselves prevent the separately evidenced source-range reconstruction path when its coverage and mapping requirements are met. Missing data must never become deletion evidence.
- **VERA consequence:** The accepted 22/19 result is source-derived range reconstruction only. It does not prove timeline-specific words or final audible text.
- **Proposed unrun experiment:** On an authorized generated/transcribed timeline, compare source MediaPoolItem, Timeline.GetMediaPoolItem proxy, and TimelineItem.GetMediaPoolItem source handles with method-level raw returns. Do not infer that a different object route will work; this experiment was not run.

### 7. Transcript boundaries and lexical variance remain bounded

- **Classification:** Producer-accepted source-range reconstruction with endpoint and edge-word uncertainty.
- **Setup/action/observation:** Test 2 excludes source [912,954), which contains singing/in/Swedish. The first range ends 0.874 frames after Finns and 2.126 before singing; the next begins 2.091 after Swedish. Observed source transcript says out while accepted wording intends up; Kai is accepted for KAJ and Specifically is correct.
- **Requirement to claim success:** Resolve endpoint convention and edge clipping with distinguishing audio evidence, retain accepted wording separately from raw transcript, and require manual review for partial/ambiguous words.
- **VERA consequence:** It is safe to report the named source-range omission with the accepted 22/19 wording and its limits. It is unsafe to assert exact word-edge removal or final audible deletion.
- **Proposed unrun experiment:** Use generated speech with nonzero sentinels at word boundaries and independently rendered track/bus output to calibrate source-range edges. No experiment was run.

### 8. Transcript coverage and freshness enforcement is not implemented

- **Classification:** Adopted future product requirement, tracked by Inbox #146; not an Issue 141 implementation.
- **Setup/action/observation:** The probe covered the two named timelines and one source, while direct proxies were missing. The retained requirement calls for all relevant clips/occurrences and explicit usable, valid no-speech/no-audio, empty, missing, error, unsupported, stale, and mismatched states.
- **Requirement to claim success:** Fail closed when any required clip is uncovered, unreadable, unstable, stale, or provenance-mismatched; bind source identity, occurrence identity, transcript version, and content revision.
- **VERA consequence:** Missing transcript coverage must visibly block transcript-based reconciliation, never silently turn a missing word into evidence of deletion.
- **Proposed unrun experiment:** Producer-accept the smallest #146 coverage/freshness evidence record and exercise it on a multi-source generated timeline. No implementation or experiment was run in Issue 141.

### 9. R2 native sequence failures were harness failures

- **Classification:** Retained launcher/driver/registration failures; none establishes unavailable Resolve editing.
- **Setup/action/observation:** The first R2 picture continuation refused on a stale editorial-readback module pin; the partial executor narrative incorrectly said its result was absent even though the retained returncode-zero result existed; residual continuation stopped on early/missing evidence pins, an unapproved deselection label, and a wrong-tail UI selection before later bounded continuation. The exact physical cuts and final pairs were reviewed from retained artifacts without replay.
- **Requirement to claim success:** Validate dispatcher-owned hashes, exact phase/index, target UID/source/range, and final complete pair before each mutation; retain a partial result and do not replay a completed phase after a refusal.
- **VERA consequence:** Treat these records as evidence about harness robustness and scope, not as API capability failures or successful unrecorded edits.
- **Proposed unrun experiment:** Run a fresh synthetic driver with dispatcher pin checks and a single explicit phase index, but only under a new authorized native task. It was not run here.

### 10. Protected real media and general routing were outside scope

- **Classification:** Deliberate evidence boundary, not a failed test.
- **Setup/action/observation:** Generated media bytes and hashes were allowlisted for PCM analysis; protected semi1b.mp4 bytes/hash/export/retranscription were not accessed. Transcript metadata came from retained Resolve getter readback. No real-script run was performed.
- **Requirement to claim success:** A production or real-script VERA claim requires a separate authorized run with source-byte provenance, complete transcript coverage, verified route/output evidence, and producer acceptance.
- **VERA consequence:** Issue 141 can constrain reconciliation behavior and synthetic support, but cannot claim universal real-media audibility or close #145's real-script requirement.
- **Proposed unrun experiment:** Run #145 against the actual real-script fixture with explicit producer authorization and the #146 coverage gate. It was not run.

## VERA acceptance criteria distilled from the retained evidence

VERA can safely mark the named synthetic observations as boundedly successful when it retains:

1. Exact project/timeline/source/occurrence identities, raw setter calls and returns, stable adjacent readbacks, expected record/source ranges, and exact restoration.
2. For an output claim, a terminal hash-bound render, PCM format/hash, generated-source support ranges, control windows, lag/gain/energy metrics, and explicit waveform-only semantics.
3. For mute/Solo/audibility, the specific control layer and an independent output effect; mapping state, operator Solo state, and Fairlight routing must remain separately labeled.
4. For timing, method-specific integer/float getter values and a distinguishing adjacent output observation; fractional and generalized retime claims stay blocked until separately calibrated.
5. For transcript reconciliation, source/proxy/occurrence objects remain distinct; the complete accepted 22/19 wording is retained with raw wording differences; every relevant clip has fresh transcript coverage; missing or stale coverage fails closed.

Within those boundaries, the retained evidence supports the six named R2 geometry/output observations, the bounded 100% endpoint convention, the negative mapping-mute output result, the bounded A2 Solo output result, and the producer-accepted source-range transcript reconstruction. It does not support a general spoken-deletion, Fairlight-routing, or final-audibility claim.
