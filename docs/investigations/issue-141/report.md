# Issue 141 — Resolve observation investigation

## Publication and control correction — acceptance remains pending

This PR publishes the retained native evidence and WI confirmations, with consistently aliased private paths, remapped links and lossless compression. See [publication guide](PUBLICATION.md) and [manifest](publication-manifest.json). The original local evidence is preserved; no new Resolve test was run. #149 remains accepted/Done. **#141 remains open for producer review of this published report.**

## Correction: automated and manual audio controls

**Plugin-proven automated silence control:** `TimelineItem.SetClipEnabled(False)` on the tested audio occurrence. On Studio **21.1.1.10**, Workflow Integration W1 disabled A1, read back disabled state, and generated subtitles/rendered output containing the A2 numbers without A1 NATO words ([W1 result](../issue-149/workflow-reruns/w1-result.md)). This is the bounded automation alternative to mapping mute.

**Manual controls:** W2's track Mute and Solo were set by the producer in Resolve's interface. Current-timeline OTIO flags and rendered output verified their effects, but this does not prove an automated setter ([W2 result](../issue-149/workflow-reruns/w2-result.md)). No documented `SetTrackMute` or `SetTrackSolo` setter was found in the installed scripting reference.

**Unverified through the plugin with output:** `Timeline.SetTrackEnable(trackType, trackIndex, enabled)` exists in the installed reference. Older #141 calls/readback are state evidence only; no retained WI setter→render test proves it silences the program. Do not assume equivalence to a person's Mute click or to Console behavior. VERA cannot currently offer it as a proven automated silence control. **No additional test was run for this correction.**

**Excluded control:** `SetSourceAudioChannelMapping` mute is unavailable as a VERA WI output control in the tested **21.1.1.10** contexts. It read back true without reducing the A2 pilot or removing number words; Claude's Console setter worked on the same-project comparisons. Internal cause remains unknown.

## Positive supported envelope for #144 and #145

These are retained capability proofs and input conditions for the bounded successors, not a completed real-script round trip.

| Positive case | Proven build / path | Exact supported observation | #144/#145 may do, with limits |
| --- | --- | --- | --- |
| Visual placement move | **21.1.0 build 14**, original #141 WI and guarded selected-clip menu macros | Linked V1/A1 pair moved +25 frames at 25 fps: record bounds 1000→1025 and 1199→1224; IDs, source bounds, markers and reciprocal links preserved. [Move evidence](evidence/r1-move-success/) | #144 may map this identified placement delta to a proposed placement change within the verified synthetic envelope. #145 must bind the real visual/source and verify its actual move. The tested move included linked audio; it is not proof of arbitrary independent visual movement or permission to reorder spoken text. |
| Safe source end trim | **21.1.0 build 14**, original #141 WI and guarded menu macros | Linked V1/A1 `GetEnd` 699→674, duration 199→174, source end 199→174; starts, IDs, links and markers preserved. [Trim evidence](evidence/r1-trim-success/) | #144 may derive a bounded 25-frame end-trim proposal for the proven identified source/range at normal speed. #145 must verify real handles, source identity, remaining media and intended output. This structural proof does not supply sample-exact word edges or arbitrary trim semantics. |
| Spoken phrase omission from actual edited program | **21.1.1.10**, WI W1 | Linked cut omitted Charlie; picture-only cut retained it; disabled A1 left A2 numbers. Generated subtitles agreed with rendered speech. [W1](../issue-149/workflow-reruns/w1-result.md) | #144 may use edited-mix transcription on a duplicate or verified render as the chosen evidence route for a phrase-level proposal. #145 must perform its actual producer-approved real phrase cut, derive the proposal through the harness and verify the rebuilt result. Transcript use requires accepted #146 coverage/freshness/precision rules; a non-transcript route must independently prove its output. |
| Supplemental source-range reconstruction | **21.1.0 build 14**, original #141 source-transcript getter experiment | The producer's two timelines reconstructed 22 versus 19 words, omitting “singing in Swedish.” | Supporting source/range evidence only: it does not prove audible omission or replace W1's edited-program/output evidence. Preserve accepted Kai/KAJ and Specifically wording and the minor out/up ASR uncertainty. |

Moving a picture does not authorize a narration rewrite. A picture-only trim, muted flag, duplicate, offline source, missing transcript or residual word must produce preservation/review/refusal rather than a false narration deletion. A real-script run and the integrated proposal/decision/rebuild seam still belong to #144/#145; no silent narrower “all refused” substitute counts as their positive proof.

## Build and entry-point coverage — conclusions are not interchangeable

| Evidence lane | Build / path | Scope and status |
| --- | --- | --- |
| Original #141 R1–R5 | **Studio 21.1.0 build 14**, injected WI; guarded macros/operator actions explicitly journaled | The original project's move/trim/razor/Copy-Paste/duplicate/reopen, six physical audio geometries, picture/boundary/graphic samples, offline/removal/relink and freshness/marker records are original-build evidence. [41-title audit](../../../output/issue141-per-title-evidence-audit.json) |
| #149 independent comparisons | **Studio 21.1.1.10**, Console-injected object; separate synthetic fixtures | Claude compared same-class split, Copy/Paste, Cut/Paste, duplicate and +1 menu nudge; tested transcript, constant retime, replacement, simple visibility, stamps and freshness. These are separate controlled comparisons, not re-execution of the original #141 objects. [Pinned accepted Console report](../../../output/issue149-accepted-readme-e020bd1.md) |
| #149 W1–W7 confirmations | **Studio 21.1.1.10**, injected WI; W2 Mute/Solo and W7 UI Delete include named manual operator actions | W1 edited-speech/clip-disable, W2 manual M/S/export/output, W4 constant retime/topology, W5 active-only getters and W7 selected locks reproduced. W3 mapping mute adverse. Original kept-time W6 adverse was later explained by its timestamp setup. [Results](../issue-149/workflow-reruns/results.md), [row-by-row verdicts](../issue-149/workflow-reruns/verdict-review.md) |
| Five WI discriminators | **Studio 21.1.1.10**, fresh disposable project; direct WI / operator Console-render / operator Fairlight-page paths | Two W6 timestamp cases reproduced. Three WI-applied mapping-mute cases adverse; original mappings/media and restored output verified. [Complete case records](../issue-149/workflow-discriminators/results/final-summary.md) |
| Later same-project Console setter | **Studio 21.1.1.10**, Claude Console | Console setter silenced A2 on a duplicate of Codex's direct timeline and fresh timeline from Codex's media. This isolates the tested entry-path difference, not the internal mechanism. [Retained primary record](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5971577666) |

**Not rerun on 21.1.1.10:** no original #141 project, original six/seven-timeline checkpoint or protected producer media was re-executed there. In particular, the exact +25 linked move and end trim, original Copy/Paste Out-mark/context drift and restoration, original marker/manual one-frame move, source 22/19-word experiment, 19-section graphic/boundary matrix, full six-case physical audio matrix and original final identity/reopen captures were not exact newer-build WI reruns. Claude's newer same-class structural edits and simple visibility tests do not transfer those exact checkpoints or prove all macro/context restoration behavior. W1–W7 confirm only the named newer gates. No version-causality or blanket cross-build support is inferred.

## Individual production mapping for every remaining limit

The existing #131/#139/#144–#146 matrix remains in [accepted design inputs](accepted-149-design-inputs.md). This additional matrix maps the same remaining limits separately to the four production owners; it does not implement or promote those placeholders.

| Remaining limit | [#101: capture/baseline](https://github.com/mbelinkie/vera-script-to-timeline/issues/101) | [#102: classification](https://github.com/mbelinkie/vera-script-to-timeline/issues/102) | [#103: review UI](https://github.com/mbelinkie/vera-script-to-timeline/issues/103) | [#104: selective apply](https://github.com/mbelinkie/vera-script-to-timeline/issues/104) |
| --- | --- | --- | --- | --- |
| Atomicity/ABA/staleness | Retain build/entry point, immutable revisions/hashes and freshness evidence; equal reads are not an atomic token. | Classify detected drift as stale/conflicting; do not claim absent races. | Expose outdated evidence and require refresh/review. | Recheck, preserve originals, verify a fresh timeline before baseline promotion; no promised atomic in-place apply. |
| Lineage and forged/copied stamps | Capture occurrence/source IDs, journals, ranges/hashes/stamps separately. | Keep ambiguous ancestry/mismatched candidates unresolved. | Show candidates and why automatic binding was refused. | Refuse ambiguous bindings; never pick by filename/sort order. |
| Word precision and general retime | Retain source alignment and verified OTIO map/precision. | Do not turn frame/phrase edges into sample-exact deletion. | Show partial-word and unknown-speed uncertainty. | Use only verified timing/handles; refuse unsupported curves/boundaries. |
| Transcript mutation/coverage/freshness | Bind generated duplicate transcript to exact source/timeline state; consume #146's coverage gate. | Missing/empty/stale/errored coverage means unknown, not absent speech. | Show missing scope and consent/remediation. | Block transcript-dependent changes until valid evidence; preserve original timeline. |
| Source replacement/offline/removal | Hash sources and retain timestamp/relink/render source check. | Distinguish changed bytes, offline-present and removed occurrence. | Show mismatch/remediation without claiming asset deletion. | Refuse failed reload/output identity and verify replacement before promoting baseline. |
| Plugin mapping mute | Capture stored flag separately from rendered/edited-mix speech; automated clip-disable evidence is distinct from manual M/S. | Never infer program silence from mapping mute or an untested track-enable setter. | Label mapping mute unavailable; manual M/S and unverified automation clearly. | Exclude mapping mute; use tested clip disable, or require manual control/output evidence. |
| Complex visibility/effects | Record simple-stack scope, inspected frames and output evidence. | Unknown transitions/Fusion/OpenFX are unresolved, not a shot deletion. | Require render/review for uncertain picture meaning. | Preserve unsupported effects; apply only verified picture mappings. |
| Routing, active context and untested controls | Pin current timeline UID, exports and named output controls. | Inactive false/unknown bus/sends is not silence. | Show routing/context limits and manual versus automatic operation. | Recheck context; refuse unverified mix changes and verify actual output. |
| Linked retime topology | Record embedded/separate sources, reciprocal links and every speed. | Do not infer A1 follows a V1-only setter. | Show per-item speed and pitch/context differences. | Set/verify each intended linked item through validated controls, or refuse. |
| Copy/Paste marks and harness/context drift | Retain full context/deltas and separate harness refusal from native outcome. | Do not convert a harness bug or non-reproduction into a capability absence. | Show unrelated drift and stopped action honestly. | Stop on unowned drift; restore only authorized context, verify and never replay uncertain actions. |

## Producer-directed #149 adoption — October 3, 2026

The producer accepted #149 and directed its roadmap status to Done. The [accepted #149 verdicts and safe downstream behavior](accepted-149-design-inputs.md) are now the current decision matrix for this report, pinned to [PR #150 commit e020bd1](https://github.com/mbelinkie/vera-script-to-timeline/blob/e020bd1b15b6294cc6a9e8c0c2fa330d71ede0c4/docs/investigations/issue-149/README.md), the Workflow Integration re-runs and Claude’s later same-project Console comparison.

- **W6 replacement:** detect changed files by content hash; change modified time → `RelinkClips` → verify decoded source with a render before accepting a reload/baseline. Metadata and relink success are insufficient; other codecs/cache contexts remain bounded by verification.
- **W3 mapping mute:** treat it as unavailable as an output control from VERA’s WI plugin. Use plugin-proven clip disable for automation, in verified current-timeline context with output verification. Track Mute/Solo were manual; plugin SetTrackEnable output is unverified. The same-project Console setter works, while WI readback mute:true did not silence A2; the internal cause remains unknown.
- **Actual program speech:** use Resolve’s `CreateSubtitlesFromAudio` on a disposable duplicate or a verified render. Source transcripts and structural API flags/ranges are not proof of what the edit audibly says. Generated phrase/frame timing and ASR require coverage/freshness/precision gates; #146 owns them.

The [remaining-limit table](accepted-149-design-inputs.md#remaining-limits-affected-issues-and-required-safe-behavior) maps atomicity, lineage, word timing, transcript mutation/coverage, replacement bytes, plugin mute, visibility, routing/current context, linked retime and unresolved mark/context drift to #131, #139 and #144–#146, with safe verification, review or refusal for each. These are adopted implementation requirements, not claims that the future harness or product already implements them. Accepted #131 and frozen designs/contracts remain unchanged.

**#141 remains open for its separate producer sign-off plus retained outside evidence.** Earlier pending #149 acceptance entries below are historical. The old Codex 9-timeline/12-job save is also historical: Claude reported two subsequent added timelines/jobs in the disposable #149 project. No fresh native read or mutation was performed for this documentation update.

## Current supplemental result — five discriminators complete

All five producer-requested October 3 cases are independently reviewed and [published on #149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5970657049), with a [summary on #141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5970661013). Two replacement cases **reproduced**: kept modified time rendered source ID 1, changed modified time plus relink rendered source ID 2. Three mapping-mute cases are **adverse**: WI direct, WI-mute/Console-render, and WI-mute/Fairlight-page/WI-render each retained A2 pilot 0.01986 and all eight number words despite getter mute:true (silence gate ≤0.001). The setter entry remains different from Claude’s Console-applied setter; the internal cause is unresolved.

Bounded design input: **content hash → changed modified time → `RelinkClips` → render verification**. VERA must not use WI mapping mute alone to infer program silence or speech removal; use output verification or a separately validated control. These cases did not reproduce a core authoring failure. General routing, lineage, arbitrary retime, visibility and atomicity are not established.

All original hashes/times/mappings and restored output are verified. The deferred direct restored-output check is now complete. Final `SaveProject=True`, equal pre/post SHA-256 `c0f8757df49d537d96ec00cbbbba0a80330fbf32a2c3f9dbe1862ae527a99a82`; 9 timelines, 36 items, 16 pool objects, 12 terminal jobs, idle Resolve, disarmed configs. **Native work has stopped; no operator action remains. #149 stays open for producer review.** Original #141 remains 40/41 pending External review. Subsequent pending/paused sections are historical checkpoints.

## Supplemental second opinion and Workflow Integration re-confirmation

The producer requested the independent [Issue #149 / PR #150](https://github.com/mbelinkie/vera-script-to-timeline/pull/150) verdicts be re-confirmed through Workflow Integration in a new disposable project on Resolve Studio 21.1.1.10. This is separate from the historical 41-entry denominator below and does not authorize reopening the protected #141 project. The [handoff's second-opinion update](second-opinion-handoff.md#second-opinion-update-issue-149-2026-10-02) distinguishes superseded broad limitations from still-conflicting measured results.

All seven required Phase10 groups have independently reviewed results published on both issues; see the [final supported/adverse summary](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5965027605): [W1 subtitle/render agreement](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5963986370); [W3 mapping-mute adverse output](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5963821842), including the [Edit-selected follow-up](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964195014); [W4 exact constant retime with embedded versus separately sourced linked audio](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964033332); and [W6 relink returned True but rendered the original source](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964191971). Each is also posted on #141. [W7 selected lock/Delete/API-disable/unlock/save](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964227757) is complete and independently reviewed for the named structural guard. It does not establish an atomic transaction or a guard for every API. [W5 current/inactive getter behavior](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964921838) is reviewed and published. [W2 required Mute/Solo/on/off export/output gates](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5965021351) pass, including all16words and baseline PCM after Y Solo-off. An extra neutral-X render remains unrun: a later fresh read revealed TC/Out-mark drift after the prior save, and no further Resolve edit or save occurred. The changed current state is retained with unknown cause, separately from earlier verified evidence. Neither issue is closed or producer-accepted.

## October 3 replacement discriminators

The [two independently verified Workflow Integration W6 cases](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5966033331) reproduce Claude’s modified-time discriminator on Studio 21.1.1.10, External Scripting None, in the new disposable synthetic project. Atomic replacement with the original modified time rendered source ID 1 after `RelinkClips=True`; atomic replacement with modified time advanced by one second rendered source ID 2. Both cases restored original hashes/times and verified restored source ID 1, with complete captures and terminal jobs. This explains the prior W6 discrepancy for the tested layouts.

**Bounded #141 design input:** detect replacement by content hash; force reload with changed modified time → `RelinkClips` → render verification. Online status, displayed Date Modified and setter success remain insufficient. Other codecs, cache paths and replacement methods remain unproved. W3 entry/operator discriminators are still pending completion; #149 stays open for producer review.

## October 3 direct mapping-mute discriminator and pause

The [fresh never-rendered native AV W3 case](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5966117633) is independently verified **adverse**: `SetSourceAudioChannelMapping` returned True and getter read back `mute:true`, but the A2 1500 Hz pilot remained 0.01986 (silence requirement ≤0.001), with all eight number words and the named picture/NATO controls retained. No target baseline render preceded mute. This excludes prior baseline rendering as a necessary cause for this adverse result; it does not isolate an internal mechanism.

Original mapping is restored. Full original-pre-mute→saved-state review attributes only the new render queue row and observed page/playhead changes; the final save pair is byte-identical. **Native testing is paused at the producer’s requested checkpoint: three of five new cases reviewed, two operator-dependent variants unrun.** Resolve is idle, launcher disarmed; no current operator action. #149 remains open for producer review.

The producer subsequently resumed. The fresh Console case is now WI-muted with no render job and an independently verified operator command. Native launches are held for Workspace → Console execution; the Fairlight case remains unrun. The direct post-restoration output render was not run at the requested stop; complete native restoration is verified, and the extra program-output closeout check remains planned.

## Workflow Integration mute → Console render

The [complete operator Console render result](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5970434832) is independently reviewed **adverse**, with mapping restored and restored program output verified. A2 stayed at pilot 0.01986 and all eight number words remained. Console rendering alone did not remedy a WI-applied mute; the Console-applied setter used by Claude remains a different entry path. The pre-helper ASCII decoding error is separately retained as a harness failure. The last fresh Fairlight page-only stage is verified and awaiting the operator; new cases are four of five reviewed. #149 remains open for producer review.

## Historical #141 completion record

September 30–October 2, 2026. **40 of 41 planned checks are complete.
All 39 preparation/Resolve evidence checks are independently reviewed and the
final report is consolidated. External review remains pending.** The six R2 physical
edit/output cases are now performed with bounded findings from the actual
completed synthetic render; independent review verifies the render, complete
state binding and named waveform results. Solo-off operator restoration and
fresh exact protected-six readback are reviewed. The final reopen and second
named duplicate are independently reviewed, with seven timelines retained and
Matrix context restored. [Final findings](final-findings.md) and the
[41-title evidence index](../../../output/issue141-per-title-evidence-audit.json)
consolidate the results and downstream limits. External review is the sole
remaining dashboard entry; all native testing has stopped.

The named synthetic Matrix has 19 sections. Baseline, stopped Copy/Paste
clips/metadata, real-source metadata and both producer transcription timelines
remain protected. External Scripting stays None. Only the injected integration
and approved fixed Hammerspoon menu actions are used. Failed probes and their
partial results are retained; a harness failure is not a Resolve capability
failure. Completed means the named observation was performed and reviewed,
including bounded or ambiguous findings; it does not mean universal support.

| Requirement | Current evidence | Remaining limit |
| --- | --- | --- |
| R1 identity | Native reopen/duplication repeats and genuine razor, trim, move and Copy/Paste have reviewed identity, range and marker evidence. Final second duplicate adds six disjoint occurrence IDs with matching copied signatures/shared sources; original six and pool are preserved apart from expected Usage and the new proxy/mapping. Matrix context is restored. | Inherited metadata and identical signatures do not prove lineage. Active/inactive getter differences, transient reopen Usage/Resolution readings and Copy/Paste Out-display changes remain explicit. |
| R2 speech/audio | Linked and unlinked cuts, picture-only removal, partial removal, residual-track speech and one-frame offset have physical edit/restoration plus actual generated-program waveform evidence. Held source-mapping mute produced byte-identical PCM to baseline. Operator-reported A2 Solo produced zero output in tested A1/A3 controls and retained the known A2 waveform at zero lag. Solo-off operator restoration and exact full-state readback are reviewed. | The mapping mute flag alone cannot establish absence of program speech. Complete bus routing and generalized endpoint precision remain unestablished. Waveform correlation does not prove bus/track origin or universal audibility. Partial words require review. |
| R3 picture/structure | Named opaque/translucent/Inspector-opacity/disabled/offline samples, Graphic edits and authored-boundary/crossing-bed edits have retained bounded observations and independent structural review. | Sampled visibility is not general visibility across all effects. An authored section marker establishes section meaning; a blade alone does not. |
| R4 assets | Offline-present versus removed occurrence, same-byte relink and independently verified different bytes at one locator are observed. | ID/path/Online metadata cannot establish byte identity or deletion. Cached display of the replacement remains unestablished in the tested case. |
| R5 freshness | Quiet/reopen observations, actual capture-loop refusal, manual marker-note edit and manual one-frame move have complete retained comparisons. | Equal adjacent reads provide a content fingerprint, not an atomic revision token, ABA exclusion or UI-race guarantee. |

The completed render contains 9,200 video frames and 17,664,000 PCM audio
samples over 368 seconds. Known generated speech survives the picture-only
cut and the primary-track gap with residual A2 present. The linked/unlinked
cut windows have low-level residual energy with weak correlation to the known
removed support, while neighboring speech supports correlate strongly. The
partial case retains its word head; the offset aligns one frame later. These
support the tested 100% speed source-range mapping path; complete mixer state
and other timing transformations remain separate questions.

Supplemental producer transcription tests, outside the 41-check denominator,
retrieved source timed words and reconstructed the two edited timelines' 22/19
word sequences, including omission of “singing in Swedish.” The producer
accepted Kai/KAJ and Specifically, leaving a minor out/up wording error. Source
transcription coverage and freshness must be enforced by VERA for this path;
Inbox #146 records that requirement. Timeline media-pool proxies returned None
in the observed transcription reads; this does not negate source-word mapping.

Current evidence includes `pcm-r2-independent-completion-review.json`,
`pcm-real-render-analysis.json`, `cli-av-owned-render-resume-result.json`,
`cli-mute-native-once-result-reviewed.json`,
`endpoint-calibration-corrected-review.json` and
`endpoint-calibration-independent-verdict.json` in the issue-owned output
directory.
The latest dated records below provide hashes, raw readback bindings, refusal
history and limitations. Earlier dated states are historical and do not replace
this current summary. Final External acceptance remains pending.

For #144/#145, the named synthetic observations support a 25-frame linked
V1/A1 move and a 25-frame linked V1/A1 end trim, with retained target IDs,
markers and links. The move preserves source bounds; the trim shortens the
observed source and record ends by 25 frames as detailed in the dated evidence. They do
not establish general lineage, arbitrary movement or final rendered output.
The producer transcript test supports source-range reconstruction of the
omitted phrase, not audible deletion. A transcription-based downstream path
requires #146's accepted coverage/freshness enforcement; otherwise spoken
omission needs verified complete audible routing/timing, which remains
unestablished. #145 still requires its own actual real-script run. These are
decision constraints, not changes to downstream contracts or readiness.

## Successful baseline preparation

At 17:39:43 UTC (13:39:43 EDT), the operator reported “It worked!” The retained
injected run identifies DaVinci Resolve Studio 21.1.0 build 14 / CPython 3.14.7,
project `VERA Issue 141 Synthetic Probe 20260930-01a0f318`
(`97037b5a-aab6-48a9-b7e4-4c5697ae10a0`) and baseline timeline
`88f7923d-55a7-471f-b09b-cf10f9fae8ad`. Preparation setters/imports/linking/markers
and save returned success. The capture has two identical adjacent passes, no
getter failures, six distinct timeline occurrence IDs, matching hashes for all
reachable sources, 25 fps timeline/playback, 48 kHz sample rate, and storage
locations under the probe output. The operator subsequently confirmed: “Yes, None
stayed set; synthetic project only.” This confirms External Scripting remained None
and only the named synthetic project/generated media were touched for this run.

The readback differs from requested bounds: base, speech and bed each report
`GetDuration=199`, start 0, end 199 (requested duration 200); cutaway reports
49, start 50, end 99 (requested 50); overlay reports 125, start 75, end 200
(requested 50). These are raw reported values; no endpoint convention is assumed
and the baseline is not corrected. This establishes preparation and adjacent-read
consistency only. Later reopen/duplication observations are recorded below.

## Native repeat preflight refusal

At 18:12:39 UTC on September 30, the native-repeat launcher stopped with
`RuntimeError: Current project is not the prepared baseline-only state`. Its
full preflight comparison differed from the prepared baseline. The cause is
unknown (metadata change or edit); this does not establish unsupported Resolve
behavior. The harness stopped before mutation and produced no native journal.
The preflight current-observe readback was not retained, leaving an evidence-
retention gap: the exact before-state comparison cannot now be reconstructed.
The sanitized launcher result and matching raw/published SHA-256 are retained in
`evidence/native-preflight-refusal/`.

A read-only quiet repeat subsequently ran at 18:22:47 UTC. Its retained capture
(`evidence/quiet-repeat/`) has two equal adjacent reads, no capture failure or
getter errors, and the same content fingerprint as the baseline. The two raw
observation passes match the baseline passes exactly. Only the outer
`capturedAt` and `stage` envelope values differ between launcher runs. Both
runs report the same content fingerprint and equal adjacent reads. The launcher
result path is redacted in the retained publication. This is bounded unchanged-
read evidence only and does not establish atomicity or close/reopen. The 18:12:39
preflight refusal had no retained capture and remains unknown.

At 19:42:33 UTC, the native repeat attempt saved and closed the named project;
both calls returned true. The post-close current project ID was
`fedceab7-8706-4b83-9ffe-fb77c65f0dbe`, different from the approved project
`97037b5a-aab6-48a9-b7e4-4c5697ae10a0`. The launcher stopped before
`LoadProject` or `DuplicateTimeline`; it did not inspect or mutate the unexpected
project. The operator reported, “It closed the project but did not seem to reopen
anything,” and confirmed External Scripting stayed None and only the synthetic
project/generated media were touched. See `evidence/native-close-refusal/` for the
preflight capture, journal, sanitized result, and hashes. The raw preflight passes
match the original baseline passes exactly with no getter errors or capture
failure. This does not prove automatic reopen, test `LoadProject`, or establish
that the unexpected project is empty/default. The next launch waits for the staged
`native-duplicate` action and requires the operator to manually reopen only the
exact synthetic project with its baseline unchanged.

At 20:11:04 UTC (16:11 EDT), the operator launched the duplicate-only action and
reported no visible result. The retained launcher result in
`evidence/native-duplicate-project-refusal/` reports
`Select only the named issue-141 project; no automatic switch`. The current
project was absent or its name did not match; no current-project identity was
retained. This guard runs before capture and native mutation, so there is no
reopened-state capture or duplication result. Operator confirmation of the
manual reopen is pending. Do not infer an API capability failure or silently
switch projects.

## Manual reopen capture and cache-setting refusal

At 20:17:34 UTC, the operator reported: “I reopened Synthetic Probe project and
ran it but no effect. Check it?” The retained pre-duplicate capture is at
`evidence/native-reopen-cache-refusal/`. Its two adjacent reads are consistent,
with no getter failures or capture failure, and project ID matches the approved
synthetic project. Compared with the original baseline, both passes differ only
in `perfCacheClipsLocation`, at project and timeline settings: the baseline-owned
cache path is now the readback string `CacheClip`; its resolved target is unknown.
IDs, ranges, markers, custom data, item properties and media hashes otherwise
match in the full raw comparison. The matching identity guard refused; no native journal was produced
and no duplication or other mutation occurred.

This is bounded evidence from one manual reopen. It does not establish API
`LoadProject` support or infer anything about the unexpected project seen after
the earlier close. The operator confirmed for this run: “Yes, None stayed set;
synthetic project only.” Earlier preflight refusals remain separately
unresolved. Exact-cache-only restoration is now reviewed and staged; require
two fresh complete raw passes equal to the pinned baseline before duplication.
`installation-cache-restoration-native-duplicate.json` binds this variant.
The independent review caught and corrected a setter-signature bug before
staging: the installed API requires one settings dictionary, matching the
existing preparation call. Focused CPython 3.14 `-S` harness/media checks,
Ruff lint/format and diff checks passed. These are probe checks, not live
restoration or duplication evidence.

## Native duplicate result and selection-context calibration

At 20:44:38 UTC, the guarded cache restoration and native duplicate succeeded.
See `evidence/native-duplicate-success/`. Two cache-restoration passes equal the
pinned raw baseline exactly. DuplicateTimeline created `VERA 141 R1 identity`,
selection was verified, and SaveProject returned true. All four captures have
equal adjacent reads with no recorded getter errors. The operator confirmed
None/synthetic-only scope and asked us to stop repeating the mode question.

All six copied occurrence IDs are new; all five distinct source-media IDs are
shared. Copied track/range/media/item-enable/marker signatures match, including
custom data. This supports one native-duplication observation and proves that
copied custom data alone is not a unique occurrence binding. Trim, move, razor,
copy/paste and repeat behavior remain untested.

The baseline's post-duplicate readback has all six track-enabled getters false,
increased media Usage values and eight absent audio-property keys on each of
three audio items. These are actual captured differences, not demonstrated
track/effect edits. The journal contains no explicit setter for those values;
At that checkpoint the cause was untested; missing values remained unknown.

At 21:24:00 UTC, one fixed Hammerspoon menu launch ran the reviewed
`native-context` action. See `evidence/native-context-success/`. It selected
baseline, captured it, then reselected R1 and captured again. All three captures
have equal adjacent reads and no getter failures. The selected baseline matches
its original raw timeline apart from exactly six Usage leaves across five
sources, attributable to duplication. Its track-enabled values and previously
absent audio-property keys return. Reselecting R1 reproduces the entire saved
duplicate observation passes exactly. No content, property, settings or save
mutation occurred in this selection-only action.

For #101/#102, this limits interpreting inactive-timeline getters as manual
changes, mute state or audio-effect removal. In this tested build/project,
observation must establish selected timeline context before using these getters;
inactive readings cannot establish an editor change. This is a bounded context
constraint, not a claim about every getter or general routing. It does not demonstrate
a failure to generate a timeline; preparation and duplication have succeeded.
It does not yet establish complete program audio, sample precision or rendered
picture visibility.

## Matrix source-list preflight refusal

At 21:49:15 UTC, the fixed menu launch reached the injected matrix action and
refused before creation with `Media pool items are unreadable; refusing`.
`evidence/matrix-source-read-refusal/` retains the two captures, journal,
dispatch and result. Both complete observation passes before/after match
exactly; the journal has no API mutation requests. No matrix was created.
The probe required a list/tuple of exactly five root-folder entries. It did
not retain the listing's raw type/value/count, so the precise mismatch is
unknown. This is a probe-assumption refusal, not an unavailable Resolve
capability. The correction reuses the already observed baseline occurrences'
source handles, retaining exact source UID/locator/owned-byte checks and the
unchanged two-timeline/R1 gate. No new editorial result is implied.

## First operator run and correction

At 16:56:37 UTC (12:56:37 EDT), the operator launched the integration and
reported no visible result. Actual injected evidence confirms **DaVinci Resolve
Studio 21.1.0 build 14**, **CPython 3.14.7**, and creation of project
`97037b5a-aab6-48a9-b7e4-4c5697ae10a0`, named
`VERA Issue 141 Synthetic Probe 20260930-01a0f318`.

The journal records only CreateProject and SetSettings, with true setter
return. The readback has `timelineFrameRate: 25.0` (number), while the request
used `"25"` (string). The agent's guard wrongly compared their string forms
and stopped before any import or timeline creation. This is a probe bug,
not evidence that Resolve rejected 25 fps. Replaying the actual readback
reproduced the failure. The numeric guard now compares exact decimal values
and still rejects missing/incorrect/nonfinite settings.

Full originals remain immutable locally; `evidence/attempt-1/` publishes
private-path-redacted versions plus raw/published hashes. Operator launch and
symptom are confirmed; None and synthetic-only/untouched-existing-state
attestations remain pending and are not inferred from config or the audit.

The readback also showed inherited 24 fps playback and storage locations
outside the disposable directory. The first correction requested 25 fps
playback and slice-owned media/cache/gallery paths. That continuation ran at
17:20:18 UTC (13:20:18 EDT) and failed with `SetSettings refused operation`,
again before import. `evidence/attempt-2/` retains the request, failure and
launcher result with raw/published hashes. The operator again reported no
visible result; scripting/synthetic-only attestations remain pending.

## Read-only playback setting and current correction

The installed `DaVinciResolveScript.pyi:424–425` explicitly marks
`timelinePlaybackFrameRate` read-only. Writing it was the agent's second
probe bug. `README.md:237–244` documents batch settings as partially applied
in unspecified order on failure. Thus the second attempt does not prove that
other settings remained unchanged; their current values need a fresh readback.
The setter form itself is documented and is not the problem.

The corrected continuation never writes the playback property. Before any
further setting mutation it retains current settings and requires the operator
to have set Playback frame rate to 25 in the named project's settings. It then
applies each writable setting separately and retains its readback even on
refusal. Final verification includes 25 fps playback, 25 fps timeline, 48 kHz
audio and the slice-owned storage paths before any media import. Writable
storage setter support remains untested; a refusal must remain explicit.

The continuation is bound to the second failed journal/failure hashes and
project ID. It requires the current project to have zero timelines, no root
media and no subfolders. It does not create another project, delete/replay
items, overwrite prior evidence or supply a generic retry system. Any mismatch
stops before further Resolve mutation. The launcher becomes read-only observe
only after successful preparation.

`installation-resume.json` recorded the latest staged launcher/source/config
hashes at that checkpoint; the staged correction subsequently ran successfully
in Resolve, as documented under Successful baseline preparation. The
settings-boundary regression
failed on the read-only write before the fix and passes after it; inherited
24 fps playback stops with an operator instruction before any setter/import.
These are harness results, not newly established Resolve capabilities. The
actual-readback regression, incorrect/missing/nonfinite-rate refusals and
empty-project recovery guards pass under CPython 3.14.7 `-S`.

## Evidence retained

- #131 baseline `817d0e5ab76219fdc3df95b196f84fbad0382f0a` and accepted #110
  immutable reference `22d86fa783c141b59f8631ba3020338c3368aa3e` were inspected.
  No unrelated implementation was merged to obtain #110's evidence.
- #110's operator observed Studio 21.1.0 build 14 / injected CPython 3.14.7,
  External Scripting None, synthetic-only scope, channel-1 mono mapping, Voice
  Isolation and Dialogue Leveler changed/read back/restored. Normalization and
  PCM-WAV render selection failed; preset/EQ/dynamics remained operator-only.
  These are historical compatibility bounds, not new #141 probe results.
- The initial status query reported **not running**, installation version 21.1.
  Actual injected identity from the later operator run supersedes that query
  for the named run. Preferences still require operator confirmation.
- Generated inputs and exact manifest are retained under `inputs/`. Eleven
  files, 25 fps / video time base 1/12800, 48 kHz PCM, four byte-identical
  synthetic “echo” kernels, a crossing tone bed, a 50%-alpha overlay, and
  same-byte/wrong-byte relink candidates. Original manifest SHA-256:
  `10eafc271a38be2db2cc34a808e5d0346755009a366d3566a562d8b28442aef3`.
  These are generated test inputs, never captured program output.
- Separate stdlib-only Workflow Integration launcher matches #110's injected
  object pattern. It refuses changed input hashes, project collisions,
  non-None attestation, unknown project ID and unexpected locators. Preparation
  journals calls/returns and item before/after getters; observation has no
  Resolve mutations. Failures retain the partial project rather than cleaning up.
- Fingerprints cover two adjacent read-only passes. Changed/failed/incomplete
  capture is refused. There is no application revision token, no atomicity
  guarantee, and no proof against changes occurring and being undone between
  reads. Do not use this content hash as apply authorization.

## Extension boundary

The installed Workflow Integrations `README.txt` says integrations use the same
scripting API (lines 142–144). The actual capture contains `TimelineItem.GetUniqueId`
and composite/opacity/crop properties; the installed `DaVinciResolveScript.pyi`
(lines 2311–2336) documents fractional frame values through `subframePrecision`
getters; its composite property declarations list opacity and crop controls.
Those declarations establish only bounded API evidence. Later completed-output
reviews add the named synthetic waveform findings; plugin installation itself
does not grant hidden access or prove full routing or rendered visibility.
Additional provenance, hashing, export,
render or Fusion evidence is useful only when each result is independently
verified.

## R1–R5 status and downstream limits

| Required evidence | Current status | Constraint until an actual result |
|---|---|---|
| R1 reopen/trim/move/razor/copy/timeline duplicate; identical signatures | **Reopen, native duplication, genuine razor, bounded linked-pair trim/move and actual Copy/Paste observed; second duplicate/full repeat pending** | Trim/move retained target IDs, markers and links. Actual copies have new reciprocal linked IDs and inherited markers; source Usage+1 and exactly four additional Matrix pool Out clearings are retained. Rendering significance remains unresolved. Inactive getter context, cache readbacks and Usage variation remain separately bounded. No general lineage or binding by filename, sort order, signature or copied custom data. |
| R2 complete program audio, repeated word/sample/derived ends, residual/mute/retime | **Linked/unlinked/picture-only/partial/residual/offset edits, generated-program waveform review, 100% integer endpoint calibration and held-mute output/restoration retained; Fairlight Solo/bus/routing remains pending** | Completed output contains known generated speech through the picture-only cut and primary-track gap with residual A2 present. The held mapping-mute flag produced byte-identical PCM to the unmuted baseline, so it cannot prove speech absence in this case. Earlier refused output attempts remain historical evidence. Unlink omitted the target video PitchCorrection field; the omission is retained exactly. Partial words need review; complete routing, fractional/generalized retime precision and universal speech-omission decisions remain unproved. |
| R3 compositing/effects/offline/Graphic/structural boundary/crossing bed | **Named picture samples plus Graphic and authored-boundary/crossing-bed structural checks retained with independent review** | Sampled visibility is bounded to the named synthetic conditions; general visibility, arbitrary effects, lineage, audibility and exact export synchronization remain unproved. Track order and a blade alone are not structural mappings. |
| R4 verified relink/offline/present versus removed/wrong bytes at same locator | **All four bounded R4 checks retained** | Offline presence differs from occurrence removal. Same-byte relink restores observed state. Wrong bytes preserved source/occurrence IDs and Online status; sampled frame0 still showed the original slate after refresh. Byte verification is necessary; displayed replacement and its cause remain unestablished. Reprepared content has an actual new occurrence UID. |
| R5 quiet/reopen/new-edit/marker repeats and inconsistent capture | **Quiet/reopen reads, actual capture-loop refusal, marker-note edit and one-frame move retained with complete comparisons** | A controlled custom-data change between actual capture passes is visibly refused, with zero getter failures and exact restoration. This does not establish an atomic token, ABA exclusion or simultaneous UI-race protection. |

The table above is the current acceptance map. Dated entries below preserve
earlier in-progress or refused states as history; later dated reviews supersede
those rows only for the named bounded observations. The current remaining work
is the R1 repeat/second duplicate, Fairlight Solo/bus/routing output,
final report consolidation, and the producer's External
acceptance statement.

Focused 41-title check: each planned title is represented by a dated retained
evidence/review reference or by one of those four pending entries. No title is
classified unsupported solely from documentation or an untested path; the
external dashboard remains authoritative for its individual title fields.

For #131/#139, these observations bound the named identity, media availability,
visibility and consistency assumptions. They support retaining raw facts,
explicit ambiguity and manual review. They do not amend accepted artifacts or
prove every observation-dependent production behavior. No fresh
script-to-timeline build failure is reproduced by these checks.

Future #101 must retain raw observations, exact source hashes and unknown states;
#102 cannot manufacture identity, speech deletion or visibility from incomplete
facts; #103 must surface ambiguity and stale/inconsistent review; #104 must
preserve sources and block unsafe apply. Contract and review decisions remain
separate gates. #137/#128/#138/#139 retain their current scopes/statuses and
dependencies on #141/#142. Neither dependency is removed here.

## Automated check record

- The selection-only `native-context` action and fixed Hammerspoon launcher
  passed their focused refusal/success checks and independent review. The
  authentic prepared-versus-identity record shapes are covered. Focused
  CPython 3.14.7 `-S`, Ruff lint/format, compilation and diff checks passed.
  `installation-native-context.json` retains the staged bindings; six actual
  raw/published evidence hashes were independently rechecked. Checks alone
  do not establish Resolve behavior; the successful real capture is above.
- The original `native-repeat` batch passed its fake lifecycle/refusal checks and
  independent safety review. It binds the original raw baseline hash, requires
  the unchanged single-timeline baseline, journals save/close/load/duplicate
  operations and checks project identity before mutations. Its partial real run
  is retained above; it stopped before load/duplicate. Its launcher returns to
  observation after a consistent result.
- The `native-duplicate` variant passed CPython 3.14.7 `-S` harness/media checks
  and focused Ruff lint/format checks, plus independent safety review. It retains
  the same preflight guards,
  skips project close/load, and journals only duplication, selection and save.
  A changed preflight is retained and refuses all mutations. These checks do not
  establish the operator reopen sequence or a real duplication result.
  `installation-native-duplicate.json` binds the staged variant; staging made no
  Resolve call.
- Independent verification checked all 26 published baseline artifact hashes
  and found no private-path leak. Its first full validation exited in the
  contracts Vitest lifecycle without an available assertion. An isolated
  pinned contracts rerun passed all 141 tests with no code/test repair; the
  original failure remains unexplained rather than being called fixed.
  The subsequent full pinned validation passed, including all 175 Python tests.
  `installation-native-repeat.json` binds the installed source/config for the
  original operator batch; staging made no Resolve call.
- `python3 -S docs/investigations/issue-141/check.py <generated-media-dir>`:
  passed; refusal/error-retention and exact media hash/time-base/sample checks.
- `npm exec --yes --package=node@24.19.0 -- npm run validate`: passed;
  generated types current, TypeScript lint/typecheck, 141 contract tests,
  1 smoke, 6 progress and 23 roadmap tests; Python lint/format/strict mypy and
  175 tests. Python application test runtime 3.12.14 / pytest 9.1.1.
  The preparation correction passed the full command again. An intermediate run
  stopped on one overlong error-message line; splitting the same literal
  corrected lint, and the full rerun passed.
- Locked install only: `npm ci --ignore-scripts`, no dependency/lock changes.
  It reproduced the three advisories already owned by #142; no fix attempted.
- Initial checkpoint frozen-boundary audit: passed; all 21 changed
  paths belong to this investigation and its plan. No frozen contracts,
  fixtures, goldens, accepted tests/design artifacts or locks changed.
  `git diff --check` and `git diff --cached --check`: passed.
- Harness/media checks ran in CPython 3.14.7 with `-S`, matching #110's
  accepted injected runtime. The installed launcher and probe source have
  retained hash bindings in `installation.json`; the successful-run None
confirmation is recorded in the operator report and interpretation summary.

Use repository shell wrappers for those commands. The injected code imports
only Python stdlib; synthetic preparation reuses the existing slate writer and
installed macOS say/FFmpeg/FFprobe. Automated checks validate the harness and
inputs, never R1–R5 application behavior.

## Historical next-evidence checkpoint — superseded

The following text retains an earlier pause and inventory checkpoint. It is
not the current execution plan. The opening summary, current R1–R5 acceptance
map and latest dated results govern remaining work; the pending action is now
the Fairlight operator observation, with Resolve launches held until reply.

Follow `operator-checklist.md` and the dashboard's unchanged41 planned steps.
Testing is paused at the producer-requested save checkpoint; no operator
action is pending. The manual R5 move request is cancelled. On resume,
preserve stopped Copy/Paste clips/metadata and use the latest saved-content
checkpoint, not the stale AV queue checkpoint. The marker-note change already
passes exact full-state comparison. No uncertain setter or menu is replayed.

Remaining native evidence is picture-only/partial/residual cuts and program
audio for the completed linked/unlinked physical cuts; mute/solo and full
routing/output; one-frame audio offset and
derived-end/sample calibration; Graphic and exact-boundary/crossing-bed edits;
one-frame calibration move; and the final save/reopen/second-duplicate
repeat. Complete the four-timeline probes before the second duplicate.
The final report and External evidence review remain required. Completed
R1/R3/R4/R5 observations are not rerun merely to reach a checkpoint.

Preserve actual baseline bounds in the retained capture and use them in editorial
probes; do not silently correct them. Keep the remaining independent-case actions
pending until their own evidence is retained. Update classifications only with
actual bounded supported/unsupported/ambiguous interpretations. Probe refusals
are not capability evidence; External acceptance remains required.
Only complete truthful evidence permits In review. External confirmation is
required for acceptance; this checkpoint does not close the issue.

## Completed matrix layout and audio-format guard refusal

At 22:11:37 UTC, the exact one-clip continuation appended the remaining 113
placements. The full 114-item readback validates all requested case positions,
source UID/locator/hash bindings, distinct occurrence UIDs, markers, links and
enable states. The first occurrence/marker was preserved; no timeline/track
creation or save request occurred in this continuation. The old baseline/R1
readbacks match the original empty-matrix selected context apart from exact
attributable source Usage increases.

The final guard refused `Final matrix audio tracks are not all mono`. Actual
A1 is stereo; added A2/A3 are mono. This was an incorrect probe assumption
about the preexisting default track, not an unavailable Resolve capability.
The raw completed checkpoint is
`capture-20260930T221137.773286Z-failure-postflight.json`, SHA-256
`e68f682b2f0b73bbf8ee883fd375ecd5325061c50c1cd2615fb9ee72e386e0d9`;
the continuation journal SHA-256 is
`a67bbafcadc5cac195fc6b93e95abb6382f1a2adb5bdf6a2186ec25d8330a20b`.
Public copies and raw/public bindings are retained in
`evidence/matrix-track-refusal/`. Keep the matrix intact.

The next bounded action, `matrix-finalize`, pins this completed checkpoint,
the original empty matrix-context capture, continuation journal and original
baseline. It requires a fresh complete two-pass observation equal to the
completed checkpoint, validates the 114-item layout and preserved old timelines,
rechecks the exact selected matrix, then calls only `SaveProject`. Saved
readback must equal the checkpoint. Any difference refuses and retains evidence
without appending, creating, cleaning up or rerunning. Stereo/mono/mono describes
the observed formats, not complete audio routing. No speech-omission or
program-visibility conclusion follows from this preparation.

## Saved full matrix

At 22:33:13 UTC the reviewed save-only action succeeded. Its journal contains
one `SaveProject` request returning true and no other mutation. Fresh preflight
and saved captures both have equal adjacent reads, no recorded getter failure,
and passes exactly equal to the hash-pinned completed matrix checkpoint.
`VERA 141 Batched Matrix` remains selected with all 114 verified occurrences
across 19 sections. `matrix-layout.json` retains actual coordinates/formats.
See `evidence/matrix-finalize-success/` for raw/public hash bindings, captures,
layout, journal, dispatch and injected result. No new editorial survival,
speech deletion, complete routing or compositing claim is established by save.

At that checkpoint, the next bounded calibration used four known frames and
documented native playhead/still-export calls. That calibration and the later
named picture cases are retained below; their findings apply only to the
inspected samples and do not settle the remaining R3 visibility/structure work.

## Known-frame still-export calibration

At 22:44:56 UTC, native `ExportCurrentFrameAsStill` returned true for
four PNGs on the Edit page. Host FFmpeg decoding confirmed base-slate
pixels at frames 0 and 198; frames 199 and 200 contain identical all-black
RGB pixels. The known synthetic labels are visually retained. The probe
restored initial timecode `00:06:08:00`; all preflight/content-before/content-after
passes equal the saved 114-item matrix. No clip/content setter was called.

`evidence/picture-calibration-success/` retains the PNGs, captions/metadata,
raw/public hashes, captures, native/dispatch journals and injected result.
This bounds the tested base-video end at 199; do not extend the result to
audio samples, still duration, arbitrary effects or compositing. A working
program-frame candidate is now available for the separately reviewed
opaque/transparent/Inspector-opacity experiment.

## Opaque, transparent, and Inspector-opacity samples

At 23:17:20 UTC, the guarded `picture-cases` action completed on the pinned
matrix. Its journal records eight content setters and 14 successful
`ExportCurrentFrameAsStill` calls. The run retained 21 equal-adjacent state
captures, restored the three target items and initial playhead, and ended with
both raw final passes byte-for-byte equal to the saved matrix pass. The 14
export SHA-256 values match the native result record.

Host inspection of representative samples showed the synthetic cutaway at
opaque local frames 50 and 98, with the base image sampled at 49, 99, and 100.
The transparent-overlay samples showed the overlay at local frames 75, 198,
and 199; the 200 sample was black. The named Inspector Opacity 25 samples
showed a reduced green overlay. These are observations of the listed samples
only. They do not establish arbitrary effects, sound, general visibility,
which exact timeline sample Resolve rendered, or atomicity.

`evidence/picture-cases-success/` retains the redacted result and journals, all
21 raw captures, all 14 PNGs, and raw/public SHA-256 bindings. The pinned saved
matrix remains separately retained under `evidence/matrix-finalize-success/`.

## Native audio state and retime observations

At 23:41:22 UTC, the bounded `audio-cases` run completed with 14
equal-adjacent captures and six successful setters: residual occurrence enable
and disable, Audio 2 track disable and enable, and the linked V1 retime to 50%
and restoration to 100%, both with `RippleTimeline` false. The final two raw
passes equal the pinned saved matrix pass. At 50%, V1's record end and duration
were unchanged; its source end changed from frame 199 / 7.96 seconds to frame
99 / 4.0 seconds, and its right offset changed from 1 to 201. The captured
linked A1 occurrence had no field changes. These observations do not establish
program mix, routing, output-audio behavior, or deletion.

`evidence/audio-cases-success/` retains the redacted native result and
journals, all 14 captures, and raw/public hash bindings.

## Reopen attempt and later read-only observation

At 23:44:37 UTC, SaveProject, CloseProject, and LoadProject returned
successfully. Resolve's automatic handoff was read twice with unchanged
metadata: a distinct `Untitled Project` with zero timelines and empty root
clip/subfolder lists. The returned and current project identities after load
matched the approved synthetic UID. The immediate reopened capture was refused
as unstable: its two adjacent reads differed in six `Usage` leaves on the
inactive baseline timeline (four 20-to-21 readings and two 40-to-42 readings).
The reopen action retained this refusal and did not retry or repair state.

A later read-only capture at 23:47:11 UTC produced equal adjacent raw passes.
Compared with the saved matrix pass, the only four differences were
`perfCacheClipsLocation` readbacks on the project and its three timelines,
which read `CacheClip`. This later read does not establish an atomic reopen
snapshot or exclude ABA changes.

`evidence/matrix-reopen-refusal/` retains the failed immediate reopen evidence;
`evidence/after-reopen-read-only/` retains the later stable observation. Both
directories include redacted results/journals, raw/public hash bindings, and
the relevant captures.

## Read-only output-capability enumeration

At 00:05:58 UTC on October 1, the corrected `output-discovery` action reached
all eight bound capability getters. Each returned: 23 render formats, 77 MOV
render codecs, seven audio render formats, one WAV audio codec, current MOV/H264,
render mode 1, an empty render-job list, and `IsRenderingInProgress` false.
The result status is `equal-read-only-capture`; before and after each contain
equal adjacent reads, and the two pass pairs are exactly equal to the pinned
23:47:11 UTC stable capture. The journal records getter reads only; no render,
setting, job, or other Resolve mutation was requested.

`evidence/program-output-discovery-success/` retains the redacted result,
before/after/report captures, journal, dispatch, installed binding, summary, and
raw/published SHA-256 hashes. This establishes enumeration and current-state
readback only. It does not establish that a render or output job can be created,
configured, or completed. The earlier preflight refusal remains separate and
provides no capability-getter evidence.


## Restore of the pinned cache-folder setting

At 00:09:41–00:09:51 UTC on October 1, the guarded cache-restoration action
read the project before and after one `Project.SetSetting` request for
`perfCacheClipsLocation`. The setter returned true. The preflight matched the
reopen observation's `CacheClip` value in that setting for the project and its
three timelines; the postflight passes exactly equal the original saved matrix
pin. The journal records no save, import, render, or timeline-content mutation.

`evidence/cache-restoration-success/` retains the redacted pre/postflight
captures, original saved pin, result, journal, dispatch, installation binding,
and raw/published SHA-256 hashes. This records restoration of the pinned
setting in the active session. It preserves, rather than revises, the earlier
reopen evidence: Resolve had read back `CacheClip` after reopen, and this
bounded action explicitly restored the original owned cache-folder setting.

## R4 initial media-pool inventory refusal, October 1

At 00:18:24 UTC, the guarded `r4-availability` launch refused during its initial
complete media-pool inventory with `Media-pool item identity/properties are
unreadable`. It stopped before any R4 mutation journal or `ImportMedia` request;
no availability transition was attempted. The configuration was disarmed to
observe afterward. This metadata-read refusal did not indicate whether import, relink, offline
status, replacement, removal, or any other R4 capability was available. Later
read-only checks successfully enumerated the unchanged original pool; this
first refusal remains specific to its initial inventory attempt. Keep it
separate from the later path-list import/append partial result below.

`evidence/r4-pool-inventory-refusal/` retains the redacted launcher result,
dispatch record, staged binding, summary and raw/published hashes. Later
read-only inventory and the path-list attempt are retained in the subsequent
R4 entries.

## R4 dictionary-item import refusal and unchanged read-only follow-up

At 00:27:44 UTC, `ImportMedia` refused the request containing the approved
`FilePath`/hash record. The attempt stopped. This result applies to that input
shape only; it does not show that path-list import, relink, unlink, or other R4
operations are unavailable. At 00:27:56, a read-only check retained two equal
media-pool inventories (eight entries) and two equal timeline passes. A second
read-only check at 00:29:32 also retained equal pool passes with the same eight
pre-existing entries and an equal-adjacent state capture. No retry or mutation
occurred during those observations. See `evidence/r4-dictionary-import-refusal/`.

## R4 path-list import and append partial state

At 00:31:28 UTC, the separately staged path-list `ImportMedia` request returned
an imported media item. The action created `VERA 141 R4 availability`, selected
it, and appended the imported item to V1. The returned IDs are media-pool item
`81d81dc0-4c37-478b-8079-03debba5e780`, timeline
`64de8a4c-86bd-4f19-9d20-47b8940f610b`, and occurrence
`af55478a-0ba3-458a-a6e1-e47b2544111d`. Its post-append proxy-handle/equality
guard then refused with `R4 contains an extra or unreadable track item`. No
`SaveProject` request occurred. The exact partial mutation is retained; neither
ImportMedia nor AppendToTimeline was retried. See
`evidence/r4-path-list-import-partial/`.

At 00:33:10 UTC, a read-only follow-up retained equal-adjacent project captures
and two equal pool inventories with ten entries. It verified exactly one
enabled `base.mov` occurrence on V1 of the new timeline, with record/source
bounds 0–199, and a readable source path pointing to the generated
`relink/base.mov` whose SHA-256 matches the approved source. The three preexisting
timelines remain equal to their pinned records; the new R4 timeline contains the
single appended item. This verifies the observed partial state only. It does not
establish unlink/relink, offline, wrong-byte replacement, removal, or generic
availability behavior. Save-only continuation, pinned to this retained state,
is the next bounded step. See `evidence/r4-post-append-read-only/`.

## Source PCM ranges and clip-getter boundary arithmetic

A full PCM16 decode of the manifest-bound generated `repeated.wav`
(SHA-256 `832dd31cc46b9f4b4fdb7cbde18b4edc09ec249885634fba43da2a7b87dc768e`)
confirmed that all nonzero samples lie in the four half-open support ranges
`[19210,36258)`, `[115210,132258)`, `[211210,228258)`, and
`[307210,324258)`. The first and last included samples of each range are
nonzero; no nonzero sample falls outside these ranges. At 48 kHz and 25 fps,
one frame is 1,920 samples. Each start lies 10 samples after a frame boundary;
each exclusive end lies at frame `+0.884375`, or 222 samples before the next
boundary. The four ranges begin 50 frames apart.

The selected Matrix `R2-retime` captures report Video 1 before the retime as
source frames 0–199, source times 0.0–7.96 s, `GetEnd(True)=5699.0`, and
`GetDuration(True)=199.0`, at 100% speed. At 50%, it reports source frames
0–99 and 0.0–4.0 s while record end and duration remain 5699.0 / 199.0. Linked
Audio 1 remains at source frames 0–199 and 0.0–7.96 s, `GetEnd(True)=5699.0`,
`GetDuration(True)=199.0`, and 100% speed. Raw inputs, exact getter values and
capture hashes are summarized in `evidence/source-timing-analysis/analysis.json`.

These clip getters do not directly expose individual word-support ends. The
sample/frame arithmetic does not establish fractional-unit semantics or
sample-exact edited-audio behavior, and no program omission is inferred. R2
word edits, output/routing checks and derived-end validation remain pending.

## Isolated availability setup saved

The 00:50 UTC save-only continuation succeeded once with a literal True
SaveProject return and unchanged complete two-pass timeline/pool inventories.
Raw preflight and postflight SHA-256 are both
`13ad0d61c8c32d54dfc67a8b9ab6d5eaa5d14cd4c3b52b12cede412d4d8256f0`.
This establishes a saved preparation checkpoint for the distinct imported
source, not an unlink/relink capability result. R4 availability tests remain
untested; original shared-source identity and all four timelines are retained.


## 2026-10-01 01:21 UTC — R4 unlink offline-prefix refusal

The native `r4-transitions` action targeted only the imported synthetic media UID
`81d81dc0-4c37-478b-8079-03debba5e780`. `UnlinkClips` returned literal `True`.
The first post-unlink timeline observation retained occurrence
`af55478a-0ba3-458a-a6e1-e47b2544111d` on V1 of R4 timeline
`64de8a4c-86bd-4f19-9d20-47b8940f610b`, with record/source bounds 0–199,
`Online Status: Offline`, and locator `OFFLINE - <approved relink/base.mov>`.
The full media-pool inventory then refused with
`Media-pool item identity/properties are unreadable`; its retained diagnostic
identifies the same imported UID, filename, offline status and `OFFLINE -` prefix,
with `sourceBytes.status: unapproved-locator-not-accessed`. Only one complete pool
read was retained, so the action refused before relink or save. This is a probe
prefix-handling/incomplete-read gap, not evidence of occurrence disappearance or
unlink capability failure. Do not retry unlink.

A later complete read-only capture and pinned comparison are retained at
`evidence/r4-offline-prefix-read-only/`. The comparison reports only the target
media item's two intended offline-property changes plus the new not-accessed
source-byte evidence shape; the original timelines, shared source and remaining
pool entries match. This distinguishes an offline-but-present item in the read
state. No relink or sampled picture-output check has occurred. Keep R4 working
pending the separately bounded read-only capture/relink-only recovery; do not
claim full R4 or R3-offline completion. The compact refusal evidence bundle binds
the original raw files by SHA-256 and publishes path-redacted exact-UID extracts.

## 2026-10-01 01:45 UTC — relink-only restoration verified

The separately reviewed relink-only recovery ran once through the named
Hammerspoon observation menu. Fresh complete two-pass timeline/pool preflight
exactly matched the 01:24 offline pins. `RelinkClips` targeted only imported
UID `81d81dc0-4c37-478b-8079-03debba5e780` and returned literal `True`.
Both complete postflight reads exactly match the original 00:33 online
timeline state and media-pool inventory. The same pool/occurrence IDs,
record/source ranges, markers, settings and unaffected content are retained;
every manifest-bound source file still matches its original bytes and size.
No unlink, save or retry occurred during recovery. The launcher returned to
read-only observation. Native result
`vera-issue-141-observation-result-20261001T014545.827951Z.json` has raw SHA-256
`5ebbc0b18a124d9f88aac6b716f9c4eadd3348a95b7dfbf9e444e9a285d03c90`;
the independently checked comparison is retained as
`r4-recovery-independent-comparison.json` in the owned output directory.

This supports distinguishing the tested offline-but-present occurrence from
deletion and observing exact same-byte relink restoration. It does not prove
program visibility or arbitrary-source relink behavior. R4-unlink/relink are
complete; wrong-byte replacement and removal remain pending.

The offline picture preparation has a separate range defect: R4 reports
`GetStartTimecode=01:00:00:00`, `GetStartFrame=90000`, and `GetEndFrame=90000`,
while its one occurrence is at record0..199. The occurrence lies outside the
program range, so no output/visibility claim can be drawn from this setup.
The planned frame0/frame50 picture action was not launched; a focused fake
now rejects this arrangement before playhead setters or export. This is a
test preparation defect, not a reproduced Resolve visibility failure.
R3-offline remains pending a reviewed in-range synthetic arrangement.

## 2026-10-01 01:59 UTC — audio preset export shape refusal

The selected-Matrix checkpoint passed at01:52 UTC, with equal complete
timeline/pool pairs and historical Matrix/Baseline/R1 records matching the
saved same-context pin. Its raw observation SHA-256 is
`0220a23be312aea5906900dd094c8e21b363294bb11f9b0f1201ab23f40c4cbf`.
Before the audio launch, a source review corrected ExportRenderPreset to the
documented Resolve object, and every literal native call owner was checked
against the installed stubs. The 01:59 UTC live action then called
SaveAsNewRenderPreset and Resolve.ExportRenderPreset once each; both returned
True. Resolve created a directory at the export path and one named XML inside
it. The probe expected a file at that path and refused with
`Could not retain owned render-preset recovery copy`. No render settings,
queue, or rendering mutation followed. The refusal is a probe representation
gap, not an unavailable export or audio capability.

The exact prior-state journal, preflight and generated XML are retained; the
XML raw SHA-256 is
`1b3b21a728c3216f9782d87aa2feae977747c377901eb6b81ed5a83a2da06595`.
A separately reviewed continuation will reuse that snapshot/export after
fresh complete state and preset-list checks. No audio-only WAV, complete
routing, sample-exact output or speech-omission result has been observed yet.

## 2026-10-01 02:12 UTC — audio settings and preset restoration gap

The separately reviewed continuation reused the existing snapshot/XML without
replaying snapshot save/export. Fresh complete selected-Matrix preflight
matched the pinned pair, with MOV/H.264 readback, mode1, an empty queue and idle
render state. The one audio-only SetRenderSettings request returned True;
GetCurrentRenderFormatAndCodec then reported `{"format":"unknown","codec":""}`.
The post-settings guard refused before AddRenderJob or StartRendering. A
single LoadRenderPreset request returned True, but the format getter stayed
unknown, so restoration was not accepted and the owned preset/XML remained
retained. The action was disarmed to read-only observe. See the compact bundle
`evidence/audio-settings-restoration-refusal/`.

The exported XML contains MOV/avc1 format fields and audio-enabled/24-bit
settings, but no explicit ExportVideo field. The installed API does not
document the getter's unknown behavior in audio-only mode or independently
expose every setting restored by preset loading. This is an observed
restoration/readback gap; it is not a reproduced unavailable audio render,
because no job was queued or run. A separately audited ImportRenderPreset of
the exact owned XML is a documented recovery candidate, not a proven fix.
Until recovery and an actual output check are retained, unattended temporary
program-audio verification remains unestablished. No speech deletion or
complete routing conclusion follows, and no core script-to-timeline failure
has been reproduced by this output-settings test.

## 2026-10-01 02:30 UTC — recovery page preflight refusal

The one-shot import recovery refused its Edit-page precondition before any
ImportRenderPreset request. Native result
`vera-issue-141-observation-result-20261001T023017.194070Z.json` is
`preflight-refused-no-import`; the journal contains only Capture/Recovery
events. A separate read-only capture at02:32 reports selected Matrix UID
unchanged, current page `deliver`, unknown/empty format, mode1, idle empty
queue, and the original presets plus only the owned snapshot. Both complete
timeline passes exactly equal the selected-Matrix checkpoint. This is an
incorrect page assumption in the recovery guard, not an import failure.
The corrected action must pin this no-import refusal and diagnostic capture,
require the observed Deliver page, and retain all full content/pool/source and
render preconditions. No page switch or other mutation is authorized by this
correction; the XML import remains unattempted.

## 2026-10-01 02:38 UTC — exact XML import recovery refused

Corrected Deliver-page recovery passed fresh complete Matrix/pool/source and
render-state preflight. It called Resolve.ImportRenderPreset on the exact
original owned XML once; the return was False. Complete postflight timeline
and pool pairs exactly equal the selected-Matrix checkpoint; source checks and
XML hash remain unchanged. The preset list remains exactly original plus the
owned snapshot, mode1, queue empty and idle, and format unknown/empty. Native
result `vera-issue-141-observation-result-20261001T023844.795069Z.json` and
`audio-render-recovery-20261001T023845.073023Z/journal.jsonl` retain the actual
refusal. The launcher disarmed to read-only observe; no retry, setter, queue,
render, save or cleanup followed. This proves only that this exact import-based
recovery refused with the owned preset already present. It does not establish
why it refused or whether importing an absent preset or audio rendering works.

The next proposed recovery is a separately reviewed one-field documented
SetRenderSettings({"ExportVideo": True}) request, requiring the pinned current
state and complete postflight. It will test whether the explicit False setting
from the audio experiment accounts for unknown current-format readback. No
import/settings replay, mode/format setter, job/render, save, delete or cleanup.
A restored MOV/H264 getter is a bounded visible readback result; equality of
all original hidden render fields, including the original ExportVideo boolean,
remains unobservable and must not be claimed.

## 2026-10-01 02:46 UTC — one-field video toggle did not recover format

The separately checked action requested SetRenderSettings({"ExportVideo": True})
once. It returned True, but format/codec remained unknown/empty. Full Matrix
and pool pairs still equal their accepted pin; source checks and owned XML
are unchanged, mode1 and an idle empty queue persist. Native result
`vera-issue-141-observation-result-20261001T024627.450485Z.json` is retained.
No import/load/render/job/save/cleanup followed; the launcher disarmed.

A separate original-format-selection recovery now pins this toggle outcome
and requests only documented SetCurrentRenderFormatAndCodec("mov", "H264")
once. It reuses the full Matrix/pool/source and exact render-state guards and
captures every resulting delta. This selects the observed original format;
it does not repeat the previous WAV selection or audio-settings request.
No mode setter, queue, render, save, cleanup or retry. Known-format restoration
will not be described as equality of every original hidden setting. Focused
fake checks cover true/false/throw/unknown outcomes and pinned-state refusals.

## 2026-10-01 02:50 UTC — known format readback restored

A separately guarded original-format selection requested
SetCurrentRenderFormatAndCodec("mov", "H264") once and returned True. The
postflight reports MOV/H264, mode1, idle empty queue, and unchanged original
preset list plus the owned snapshot. Complete before/after timeline/pool pairs
exactly equal the selected-Matrix pin; source checks and XML hashes are
unchanged. Native result
`vera-issue-141-observation-result-20261001T025040.116106Z.json` is
`format-selected-content-unchanged`. No queue/render/save/cleanup occurred.
The prior accepted video toggle had left format unknown; both outcomes remain
in separate redacted evidence bundles. No hidden render-setting equality is
claimed, and no audio output or complete routing has been verified. Known
format/idle state and complete content checks now permit the separately
prepared R4 range correction; render tests need their own fresh settings pins.

## 2026-10-01 02:54 UTC — R4 start-timecode repair preserves the invalid offset

One SetCurrentTimeline selected existing R4 and one SetStartTimecode00 returned
True. Both complete pre/post pairs are stable. The exact seven timeline deltas
are R4 start/end90000→0, timecode01→00, and occurrence record start/end
0..199→-90000..-89801, including fractional getters. The same occurrence UID,
source UID, source ranges and duration persist. Six pool deltas are the mapped
R4 timeline proxy's Start/End/Slate TC in its item and mapping; source/pool and
other timeline data are otherwise unchanged. This empirically shows the start
setter also shifts occurrence record coordinates by the timeline timecode
change. It does not move the invalid occurrence into the program range.

The probe refused its postconditions and retained the partial state without
rollback under unreviewed non-range drift. Native result
`vera-issue-141-observation-result-20261001T025403.420310Z.json` and full raw
`r4-range-repair-20261001T025403.645518Z` evidence are retained; the installed
configuration is disarmed to observe. No save/render/source mutation occurred.
This is another preparation assumption, not a Resolve offline-output failure.
The next bounded proposal is to exercise R4 occurrence removal with full
before/after evidence, then reprepare that isolated source at absolute frame0
on the now-zero-start R4 timeline. A new occurrence must receive and retain its
actual new UID; it cannot be described as the old identity restored or as an
R1 move test. Keep removal and preparation captures separate, review exact
native timeline-proxy/source-Usage deltas, and pin a valid in-range arrangement
before any offline-output/wrong-byte test. No deletion or appending action is
staged or authorized by this note beyond the existing issue's approved tests.

## 2026-10-01 03:13 UTC — occurrence removed, source retained

One `Timeline.DeleteClips([af55478a-0ba3-458a-a6e1-e47b2544111d], False)` returned `True`. Stable adjacent timeline and pool reads before and after show exactly two state changes: the target R4 occurrence disappeared, and the retained source item's `Usage` changed from `1` to `0`. The source media-pool UID `81d81dc0-4c37-478b-8079-03debba5e780` remains online with the same SHA-256 `c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942`. The independent comparison and compact raw-hash inventory are in [r4-removal-success](evidence/r4-removal-success/). No media-pool deletion, append, save, render, restoration, rollback, or retry occurred; output and restoration remain pending.

## 2026-10-01 03:26–03:28 UTC — new R4 occurrence recovered by read-only capture

One AppendToTimeline returned new occurrence UID `65a7bcd1-f211-4dee-9726-8c7e0b89cc84` for the exact isolated source, source0..199, V1, absolute recordFrame0. The journal retained the request and returned UID; the postflight page guard then refused because it required Deliver. Installed result `vera-issue-141-observation-result-20261001T032648.191508Z.json` remains a launcher refusal. The action was explicitly disarmed; no append retry or rollback occurred.

A separate read-only launch at03:28 retained complete equal timeline/pool pairs (`capture-20261001T032801.656424Z.json`, SHA `6d70868e701b3c011372d3f06ff26236d6c8fffed5d2fea552280d22cbace98b`, and its associated pool read-only file). Context is selected R4 on Edit, playhead00:00:07:24, MOV/H264, idle empty queue. The actual new occurrence/source IDs and source/record0..199 are verified; timeline start0/end199 places frames0/50 inside the program range. All manifest bytes remain exact. Exact deltas from append preflight: timeline end0→199 and one new V1 item; isolated source Usage0→1; R4 proxy Duration/End/End TC/Frames in the item and mapping change to reflect199 frames. Other captured timeline/pool content is equal.

The native append followed by diagnostic capture supplies source-content re-preparation evidence. It does not preserve the removed occurrence's UID or count as an R1 move. The postflight failure is a page assumption, not failed append/offline-output capability. Removal and new-ID re-preparation remain separate raw checkpoints. No save, render, source-file mutation, pool deletion, relink, cleanup or retry occurred.

## User-requested pause — 18/41 checks complete

Producer requested a good stopping point to preserve usage. Paused after the verified R4 removal and separate new-ID in-range re-preparation. Independent comparison is retained at `evidence/r4-reprepare-read-only/`; exact outside-anticipated delta equality is verified. Launcher is disarmed to read-only observe; no further native action, append retry, render or cleanup is staged. Retain raw continuation checkpoint `continuation-paused-20261001T0333.json`, all source/evidence files and uncommitted investigation work. Last full diagnostic reports R4/Edit, MOV/H264, idle empty queue and source0..199 at record0..199 with new UID65a7bcd1…cc84.

On resume, verify fresh full read-only timeline/pool state against the latest checkpoint before preparing the bounded offline-picture test. Remaining editorial macros lack affirmative approval; no new request or execution occurred. Speech/routing, offline/wrong-byte output, genuine editorial/structural/freshness cases and final External acceptance remain pending. Issue141 stays In progress; investigation and goal are not complete.

## 2026-10-01 03:54 UTC — controlled metadata comparison refuses a change

The audited native R5 comparator probe changed only existing Matrix marker0 customData with `UpdateMarkerCustomData`, captured complete equal-adjacent timeline/pool observations, then restored the original field and verified complete original-state equality. Both setter returns were literal True. The sole before/after difference is that customData field; the pool is unchanged. The existing consistency comparator returned `inconsistent-refused`. Raw result `r5-freshness-20261001T035403.810952Z/result.json` and independently compared redacted evidence in `evidence/r5-controlled-metadata/` are retained.

This demonstrates detection of an actual metadata difference between two separate stable observations. It does not exercise `probe.capture()`'s internal two-read loop, a simultaneous UI race, a revision token, or exclusion of ABA changes. Marker-note/move and the actual capture-loop probe remain pending; the full R5 concurrent-capture step is not completed by this result.

## 2026-10-01 04:00–04:01 UTC — offline-picture guard refusal

One fixed-menu launch of the reviewed offline cycle exported online frames0/50, then called `MediaPool.UnlinkClips` once for isolated source81d81dc0-4c37-478b-8079-03debba5e780 and returned True. Complete offline timeline and pool pairs are equal-adjacent. Each pair differs from the online preflight only in seven leaves on that exact source: the locator now has Resolve's exact `OFFLINE - ` prefix, Online Status is Offline, and sourceBytes reports `offline-locator-not-accessed` with the approved locator/expected hash instead of reachable hash evidence. Occurrence/source UIDs, track, source/record ranges, every other source and timeline/pool field are unchanged. No original source bytes were changed.

The cycle refused because its allowlist omitted the already-observed offline prefix. No offline still, relink, save, render, second unlink or automatic retry followed; R4 remains selected on Edit at frame50, and the isolated source remains offline. Launcher is disarmed to observe. Retain `offline-cycle-20261001T040030.565871Z/` and native result `vera-issue-141-observation-result-20261001T040029.331895Z.json`. The executed module is preserved separately under its SHA-256.

This is a probe-guard omission, not unavailable offline program output. A separately reviewed continuation must pin the exact refusal and full offline pair, export frames0/50 from that existing state, relink only the same isolated source to verified original bytes, and require full original timeline/pool equality plus original playhead00:00:07:24 restoration. Do not repeat unlink or mask unrelated-source differences.

## 2026-10-01 04:17 UTC — offline output and exact relink restoration

A separate hash-bound continuation performed no second unlink and reused the retained online frames. Native offline exports at0/50 show Media Offline (both raw PNG hashes are identical); the inspected online frames show the VERA141 BASE SYNTHETIC slate. One isolated-source RelinkClips returned True. Independent comparison verifies both complete relinked and final timeline/pool pairs exactly equal the original03:41 online checkpoint; the original playhead00:00:07:24 is restored. The occurrence/source identities and ranges survive the offline transition. Raw directory `offline-cycle-continuation-20261001T041700.891099Z` and compact evidence `evidence/offline-cycle-continuation-success/` are retained.

This completes the named R3-offline sample check and supports distinguishing offline-but-present from occurrence removal. It does not establish arbitrary compositing/effects, program audio, byte identity from a locator, or clip lineage. Dashboard is19/41. No source-byte mutation, save, render job, editorial macro or retry occurred. The separate actual R5 capture-loop check is staged only after this verified full online restoration.

## 2026-10-01 04:20 UTC — real capture loop visibly refuses interpass drift

The controlled wrapper called the real probe.capture and changed only Matrix marker0 customData after the first observation. Its retained raw capture has two passes differing solely in that field, zero getter/capture failures, and status inconsistent-refused. Independent comparison verifies complete stable preflight/after/restored pairs, unchanged pool state, successful marker restoration and exact original-state equality. The temporary observer was restored in finally. Raw `r5-freshness-20261001T041958.897531Z` and compact `evidence/r5-capture-loop-success/` are retained.

This completes the bounded edit-during-capture refusal step. It supports refusing a capture with observed differences; it establishes no atomic token, exclusion of ABA changes, simultaneous UI-race protection, or guarantee that state remains unchanged after capture. Marker-note/move remains pending. Dashboard is20/41; no save, timeline selection or editorial macro occurred.

## 2026-10-01 04:26–04:28 UTC — wrong bytes survive unchanged identity/status readbacks

The one audited R4 cycle replaced only generated relink/base.mov with the manifest-bound different candidate, retained stable full mismatch observations, refreshed the exact isolated source through one RelinkClips, sampled frame0, restored the verified original bytes, refreshed once and retained full original-state equality plus a restored frame0 sample. Both refresh returns are True. Independent comparison verifies all final timeline/pool pairs equal the03:41 original checkpoint and every synthetic manifest file has its original hash. Shared original source was not modified. `r4-wrong-bytes-20261001T042632.944184Z` raw files and compact `evidence/r4-wrong-bytes-success/` are retained.

While the file had wrong SHA-256771b4bbb…62c88b instead of expectedc54ed675…b7942, source UID81d81dc0, occurrence UID65a7bcd1, the same locator, Online status, ranges and every other captured field persisted. Only the explicit sourceBytes mismatch changed. The wrong-byte frame0 export after refresh is byte-identical to the earlier original online frame0 and the restored frame0; both inspected samples show the original VERA141 BASE SYNTHETIC slate. This does not establish displayed replacement, explain cache behavior, or predict a reopen result.

For #101, source byte verification must accompany locator/ID readback. For #102/#103, a mismatch needs an explicit stale/ambiguous asset reason and manual review; never call it asset deletion or infer edit lineage. #104 must refuse an apply that relies on this unverified source. These are evidence constraints for #131/#139 and future design, without amending accepted contracts or roadmap state. This limits automatic reconciliation of a mismatched source; it does not supply evidence of failure to build a fresh script-generated timeline. Dashboard is21/41.

## Bounded visibility interpretation completed

`evidence/visibility-interpretation/` binds the current interpretation to the
retained native picture samples and independent RGB decoding. All39 published
bindings, all14 exported PNG hashes, four raw capture bindings and exact final
content equality were reverified. The still's reported125-frame range agrees
with nonblack local199 and black local200 exports; audio endpoints and exact
exported-sample synchronization remain unproved. The planned visibility
interpretation step is complete; Graphic and section/crossing-bed edits remain
pending. No Resolve launch, editorial macro or settings mutation was performed.

## Approved editorial menu calibration and genuine R1 razor

The producer approved the bounded editorial macros. Native preparation selected
Matrix, retained the original locks/playhead, locked V2/V3/A2/A3 and positioned
frame1600. The first selection reader refused because it incorrectly expected
a dictionary; the installed API documents a list. The original refusal remains
retained, and corrected readback confirmed empty selection with unchanged full
state. This was a helper error, not a Resolve selection capability failure.

Select All Clips Under Playhead selected five case-local items, including
locked V3/A2/A3. The exact-pair guard refused before split; complete content
remained unchanged. Deselect All and the narrower installed Select Nearest →
Clip/Gap then selected exactly the pinned reciprocal-linked V1/A1 pair. Full
before/after selection pairs matched preparation; frame1600 read back before
the single Split Clips command at05:15:54 UTC.

The actual split retained the original left IDs and produced new right IDs:

| Track | Left UID | Right UID | Raw record ranges | Raw source ranges |
| --- | --- | --- | --- | --- |
| V1 | `33270bc5-52d0-4361-a6e3-96eb2b6d4a91` | `43a86094-c5b5-40f0-b781-a419923f25fe` | 1500–1600;1600–1699 | 0–100;100–199 |
| A1 | `4d08e64a-85fd-4dfe-ac80-77e4d9d28835` | `9b7c5a04-8349-4a68-aa4b-9fcc81065cc8` | 1500–1600;1600–1699 | 0–100;100–199 |

Each track reports durations100 and99 and source-time boundaries0/4.0/7.96s.
The left linked pair and right linked pair each have reciprocal links. Both
halves preserve identical parent marker names, notes and custom data, so those
fields alone cannot uniquely bind an occurrence. The independently reconstructed
full postflight equals the actual two-pass timeline/pool pair after only these
splits and a +1 source-Usage increment for base.mov/repeated.wav. Other content,
markers, settings, timelines, source bytes and locked occurrences are unchanged.
This is one observed split, not a general lineage or sample-exact audio claim.

`evidence/r1-razor-success/` retains redacted complete prepared/split pairs,
selection/refusal records, ordered macro/native journals, the exact executed
macro source versions, hashes and independent comparison. The runnable
`r1-razor-evidence-check.py` verifies original raw file bindings and full equality.
At05:33 UTC, the separately pinned restoration returned `restored-unsaved`.
Independent comparison verifies that only V2/V3/A2/A3 lock flags changed
True→False; the recorded playhead00:06:07:24 read back. The actual split and
all source bytes are preserved. `evidence/r1-razor-context-restored/` binds the
complete before/after pairs, native and launcher journals, result and comparison.
No save, undo or editorial command was dispatched. Dashboard is23/41.

## Approved R1 linked-pair trim — 2026-10-01 05:57–06:00 UTC

The 05:48 fixed-launch refusal remains separately retained and was not retried
as an edit. A read-only focus check followed by a fresh full-context readback
matched the restored razor state before the first actual R1-trim preparation.
The 05:57:13 preparation recorded the original unlocked track state and
playhead, then locked only V2/V3/A2/A3 and positioned the Matrix playhead at
frame674. Complete selected-pair snapshots through 05:58:56 match that prepared
content exactly. At 05:59:14 the approved `Trim → Resize → End to Playhead`
macro dispatched once after the native selection read exactly the two pinned,
reciprocally linked V1/A1 UIDs.

The 05:59:15 complete two-pass readback changes exactly eight range fields on
each target item: GetEnd 699→674, GetDuration 199→174, source end frame
199→174, source end time 7.96→6.96 seconds, and right offset 1→26, each with
its integer/subframe getter where present. Both occurrence UIDs, starts,
source starts, source IDs, reciprocal links, markers/custom data, all other
timeline and pool content, and settings are unchanged. Independent full-object
normalization verifies that these eight fields per item explain the entire
capture delta.

At 06:00:04 the separate restoration action changed only V2/V3/A2/A3 lock
readbacks from True to False and restored playhead `00:06:07:24`; the observed
trim remains in the unsaved project. No save or undo was dispatched. The raw
and redacted evidence, native/macro journals, readbacks and hashes are retained
in `evidence/r1-trim-success/`; `r1-trim-evidence-check.py` independently checks
both full comparisons. This demonstrates the named 25-frame trim and bounded
identity/marker preservation for these two synthetic occurrences. It does not
establish sample-accurate audio endpoints or rendered output. Dashboard is
24/41; R1 move/copy and repeat remain pending.

## Approved R1 linked-pair move — 2026-10-01 06:07–06:18 UTC

The R1-move preparation pins the same Matrix and isolated move-case V1/A1 pair,
starting at frame1000, with original track locks and playhead recorded. Its
before-state equals the prior trim restoration; preparation changes only the
recorded locks and playhead. The first context readback retained a pre-existing
selection from the earlier case, so the driver explicitly deselected and then
selected only the pinned R1-move pair before moving. The retained menu journal
records25 successful `nudge-right` dispatches, each followed by a complete
readback. All28 complete state checkpoints have equal adjacent timeline and
pool passes.

Across those25 checkpoints, only the linked target items' GetStart/GetEnd
integer and subframe fields advance one frame per command: V1 and A1 start
1000→1025 and end1199→1224. Target occurrence/source IDs, source start/end
ranges, metadata, markers and reciprocal links stay fixed; all other timeline,
pool and settings content matches the prepared state. The final independently
verified pair SHA-256 is
`1124201a733b74e487e44d53b9bbac99a89c2f7131af347f7169d565df84f1cc`.

The separate restoration changed only V2/V3/A2/A3 locks True→False and returned
playhead `00:06:07:24`. Status is `restored-unsaved`; no save or undo occurred,
so the observed move remains in the synthetic project. Compressed redacted
readbacks for all28 states, raw-to-public hash bindings, driver/menu journals,
Resolve readbacks and independent checker are in `evidence/r1-move-success/`.
This establishes the tested 25-frame linked-pair move and bounded ID/metadata
preservation; it does not establish general edit lineage or an accepted
reconciliation rule. Copy and full repeat remain pending.

## AV output attempts stopped — 2026-10-01 06:20 and 06:32 UTC

The 06:20 save/export attempt stopped at its snapshot guard: observed
`RecordAudioBitDepth` was 16 while the pinned snapshot expected 24. The
separately pinned 06:32 continuation called `SetRenderSettings` once; Resolve
returned `True`, but the complete-pair guard then refused on four media-pool
`Out` leaves. Matrix proxy UID
`de8efefa-310d-451c-863c-d6b847e8b82e` and its Matrix timeline mapping changed
from empty to `00:00:08:00` in both pool passes. All other captured timeline,
pool and source data matched. Pair 001/002 SHA-256 is
`35f7132f331a8ecf0f1685dd1167c636add1aea3118bfbf2f2e7896ae348c1c3`; pair 003
SHA-256 is `dc66efb49729dfc0b40efd35a3fa02d94cacd91e1ddfbaa62e97efcf656467ca`.

Neither attempt dispatched `AddRenderJob`, `StartRendering`, `Load` or
`Delete`; no render output or exact audio timing evidence was produced. The
settings and recovery preset remain retained, and the launcher is disarmed.
Await the producer's decision on a bounded queue-from-settings test; do not
replay the setter or snapshot or stage another action. These guard refusals do
not establish an unsupported Resolve capability. Independent R1 trim, move
and razor findings remain valid.

## R1 copy page preflight refused — 2026-10-01 07:07 UTC

The R1-copy native launch stopped at `Exact Edit/known format/empty queue
required`. This was a preflight refusal; it does not establish a Resolve
capability failure. A separate read-only media-pool capture at 07:08 returned
`equal-read-only-pool-inventory`. Its context was stable on Deliver with MOV/H264,
an idle empty render queue, Matrix UID
`29ae8331-b86e-4041-a548-960695cc7b24`, and playhead `00:06:07:24`. Complete
read-only timeline and pool passes exactly match the AV continuation's
`full-pair-003.json` capture. The summary had incorrectly assumed Edit; no
native mutation, selection, copy or paste occurred. The user renewed bounded
editorial approval, but this refusal did not stage or perform an edit. The
separate audio queue-from-settings decision remains pending.


## Genuine R1 Copy/Paste retained with pool-Out drift — 2026-10-01 07:20–07:25 UTC

Producer renewed the bounded editorial macro approval. From the verified
post-settings state, one journaled `OpenPage("edit")` preserved the complete
timeline/pool pair. Preparation locked only V2/V3/A2/A3 and set frame2100.
Separate full native captures verified Deselect All, exact R1-copy V1/A1
selection, and unchanged complete state after one Copy. A helper path check
was corrected before paste positioning: selected and post-Copy snapshots
may use different owned filenames when their verified complete bytes match.
A focused fake exercises that real snapshot shape. No native operation was
replayed for this local correction.

One guarded playhead setter moved to2250 (`00:01:30:00`); another full capture
verified the same two selected source IDs and the reserved empty destination.
One Paste created V1 UID `7dc4a98b-33cb-4feb-9727-b2bca434138e` and A1 UID
`a9175c87-6bc0-4c07-a167-3b7c9de70fba`. Both have raw record bounds2250..2449,
raw source bounds0..199, reciprocal new links, and copied marker/custom data.
Original occurrence IDs and contents survive; the expected source Usage+1
appears in the complete paired observations. Copied markers are therefore
ambiguous binding rather than unique occurrence identity or lineage proof.

The strict complete-pair guard refused one additional observed change:
Matrix proxy `de8efefa-310d-451c-863c-d6b847e8b82e` and its Matrix mapping
cleared `Out` from `00:00:08:00` to empty in both pool passes, exactly four
leaves. The explicit stopped-case review verifies the complete modeled copy
plus those four changes, with no other timeline/pool/byte delta. Their
render-range meaning remains unknown. Do not infer that a future render is
correct or that render capability is unavailable. The old audio queue
checkpoint no longer matches and cannot be staged as-is.

Raw pre-Paste pair SHA-256:
`0ab69c1eeaa7dffe2d6a63bc02c73823b9fe12af2134be74b204c4f1e81a6435`.
Raw post-Paste pair SHA-256:
`b8a12d66415ed2cef4ab1922ac1c764ec42aa41aad58cfa40d4435c24c75b9a7`.
Published redacted evidence,46 raw-to-published hash bindings, version stamps,
actual menus/native results, helper-source archives and the runnable review
are retained in `evidence/r1-copy-paste-stopped/`. Run
`python3.14 -S docs/investigations/issue-141/evidence/r1-copy-paste-stopped/review.py`
for this bounded comparison; it makes no Resolve calls.

Under the producer's stop-on-unrelated-drift instruction, no retry, undo,
save, render or temporary-context restoration followed Paste. The four
secondary tracks remain locked and the playhead remains2250. The launcher is
read-only. A hash-pinned restoration of only the recorded locks/playhead is
reviewed in `installation-r1-copy-restore-review.json`, not staged; its
separate continuation approval is pending. The pasted clips, pool-Out
readback and evidence would remain intact. The actual Copy/Paste observation
is complete (dashboard26/41), while context restoration and the remaining
R2/R3/R5/output probes remain pending.

For #131/#139 and future #101–#104, this supports bounded recognition of new
copied occurrences with inherited metadata; ambiguous copies still require
manual binding or narrower automation. Public API endpoints remain raw until
output calibration, and this test establishes neither speech deletion,
complete routing, general visibility, asset deletion nor general lineage.
No contract, fixture, golden, production implementation or dependency changed.

## Independent R2 continuation checkpoint — 2026-10-01 11:16 UTC

After the producer authorized continuing independent synthetic tests while
preserving the stopped Copy/Paste state, a fresh read-only R2-linked capture
retained two matching full passes, empty selected-item lists, Matrix playhead
`00:01:37:24`, and the pair SHA-256
`4743b0d4c53566580523ce6db2ca555d8d8544bfecba6627b9d4a192cc26cb0d` at
`r2-linked-context-20261001T111624.097432Z/pair.json`. Compared with the
retained post-Paste pair, the complete diff contains exactly four leaves: the
Matrix proxy `Out` and its Matrix mapping `Out` in each pool pass changed from
empty to `00:01:37:24`. Timeline content, source evidence, and track locks
otherwise match. The recorded diff is `independent-current-state-diff.json`.

This is a new read-only starting checkpoint, not a speech edit, output result,
or explanation for the `Out` changes. Preserve the stopped Copy/Paste clips and
metadata; do not retry, undo, or clean them up. The previous audio queue
candidate remains stale and must not be staged from this checkpoint without a
newly reviewed, hash-bound action. No new edit has completed, so the dashboard
remains 26/41.


## Independent R2 selection attempts — October 1, 11:25–11:34 UTC

The11:25 source-pin refusal preceded any preparation setter; a concurrent local A3 guard review had changed the helper. After the reviewed helper was frozen and registered, R2-linked preparation succeeded twice with unchanged complete pairs, fixed playhead2560, unlocked V1/A1 and four held secondary locks. Deselect All and Select Nearest Clip/Gap each dispatched once per attempt; both selected readbacks returned zero clips in two adjacent lists. No split or deletion occurred. Between attempts, the exact named Workspace > Active Panel Selection > Timeline focus command was verified available and dispatched; its immediate full-state pair was unchanged. Focus before preparation did not resolve the empty selection. Each new preparation was restored to its own recorded four locks and playhead00:01:37:24, preserving the stopped Copy/Paste content and current Out values. These are bounded selection-mechanism refusals, not evidence that Resolve cannot cut clips. Native directories and menu audits are retained in the operator record. Investigation continues independently; count remains26/41.


## R2-linked physical interval removal — October 1, 11:41–11:48 UTC

Setting Auto Select scope explicitly through named menus made the nearest-selection command return exactly the intended V1/A1 pair. Each split used independently verified selected IDs and complete unchanged preflight data. The first blade at2560 retained original left IDs and created distinct right IDs; after the second blade at2570, guarded non-ripple DeleteClips removed only the actual linked middle interval. Full timeline/pool/source-Usage postflight matched exactly, and original four secondary locks/playhead00:01:37:24 were restored. The stopped Copy/Paste pieces and current Out metadata remain preserved. Native deletion pairSHA256 `1be6a4fe8f6f98e31b9cac544e7251c74e24f7e07aaa0668985d2ae753e66e48`.

One intermediate guard refusal came from two source-end seconds values differing only as7.96 versus7.959999999999999. The shared guard now matches the observed start-seconds-plus-duration arithmetic; raw frame bounds remain exact and no tolerance was added. Retained R1 and focused numerical checks pass. No blade was repeated. The physical removal is sufficient to recognize this specific editorial delta, but it is not evidence of word omission from the program mix. Audio output remains required, so this complete planned R2 check remains in progress.

## Actual queued-render settings — October 1, 11:53 UTC

A newly reviewed fresh-checkpoint continuation reused the retained recovery preset and prior SetRenderSettings provenance without replay. AddRenderJob returned one owned job, `9c4f9ad9-9acf-4c60-bac2-fb7cc9269ebd`, with the correct MOV/H264, audio/video flags, PCM24/48k, output destination and name. Actual dimensions1920x1080 and MarkOut2449 differ from the earlier requested640x360/200. The job-metadata guard refused before StartRendering. Journal/final native result retain full actual settings; the owned job remains unstarted with recovery retained. This establishes that earlier setter success alone is insufficient to authorize a render and queued settings must be verified. It does not establish an unavailable render capability, complete routing, program silence or sample precision. Independent testing continues after bounded recovery of the owned unstarted job.


### 12:07 UTC queue recovery and harness interpretation

The sole owned unstarted job was removed with exact full before/after state equality; recovery preset/XML and edited timeline remain retained (`evidence/av-owned-unstarted-job-recovery/`). The preceding metadata refusal came from a queue-only path checking current render settings against stale dimensions/range. It is not a PCM capability failure. A fresh full-Matrix output probe must derive range from current timeline endpoints and check actual job metadata before rendering.


## R2-unlinked physical audio-only cut — 12:54 UTC

Actual A1 interval3060..3070/source60..70 was removed through two real blades and one non-ripple deletion while V1 remained unchanged. Complete state/Usage and own context restoration passed, final pair SHA6b047339f81bab349ff3e95928bebda192a73e251b7e3989b8fd9d893a882d45. The pre-cut speed record omits video PitchCorrection after unlink; the earlier null description is corrected to absence. A one-frame owned playhead discrepancy was retained and corrected by one guarded Playback step before the second blade. Geometry recognition is supported for this case; final program word omission/routing remains unproved.

## Producer transcript lead — documented, not yet tested

Installed21.1 stub lines1206–1230 defines transcript segments with timed words. MediaPoolItem.GetTranscription(useNestedClipTranscription=False), lines2098–2099, returns available source/nested transcription. Timeline.GetMediaPoolItem, lines2272–2273, supplies its pool proxy. These give a bounded API candidate for testing how words survive edited source/timeline observations; a read-only source/Matrix getter probe is being prepared. Documentation alone does not establish edited-timeline transcript semantics, speech deletion, routing or sample accuracy. Source transcripts must be intersected with observed uses; repeated words and copied uses still require explicit identity/ambiguity handling.


## R5 manual marker note and no-effect menu diagnostic — 13:07–13:13 UTC

Operator replied “done” after the requested marker-editor action. The before
pair SHA6b047339…d45 and noted pair SHA55770110…6242 differ only in Matrix
marker0 Notes, nowIssue 141 R5 marker-note observation. Both full timeline
and pool passes agree; IDs, ranges, sources and all other markers are unchanged.
The operator’s actual playhead remained00:01:37:24, so no frame0 position is
inferred from the request.

The reviewed fixed Playback > Go To > Timeline Start command reached00:00:00:00.
After explicit V1/A1 Auto Select scope and actual nearest selection, both
selected lists contain exactly calibration UIDs3f2de461…e38b and22561398…e4cf.
One Trim > Nudge > One Frame Right dispatched. The13:13 moved readback is
byte-identical to the noted pair: no move and no unrelated content delta.
The move checker visibly refused its unmet expected delta; this is a no-effect
menu observation, not an unavailable Resolve capability. No retry/undo/save
occurred. Ordered wrapper/menu/native records and exact comparison are retained
in r5-marker-move-sequence.json and r5-marker-move-exact-difference.json.

The operator was asked to try that exact one-frame move manually once; native
launches are held during this action. Local documentation/guard work continues.
R5-marker-and-move remains in progress and dashboard26/41 remains truthful.


## Producer save checkpoint and pause — October 1, 13:26 UTC

Producer corrected the continuation request to “Reach a checkpoint and stop
and I’ll check it.” The pending manual calibration move is cancelled; do not
interpret its lack of reply as a completed edit. Fresh pre-save native pair
SHA5577011075fc73b400c9a5b3afe5b9e5795673836eba8c6eb03a826129896242
matches the noted/no-effect state. One guarded File > Save Project command
was accepted; subsequent complete timeline/pool captures match exactly.
No reopen or disk-persistence repeat is claimed. Actual current context: Edit,
Matrix selected, playhead00:00:00:00, calibration pair selected, render queue
empty. Original stopped Copy/Paste clips/metadata remain retained.

Evidence: out/issue-141-observation-20260930-01a0f318/producer-stop-checkpoint.json.
Dashboard remains26/41 and is marked paused, with no pending operator action.
Managed goal and hourly evidence follow-up are paused at producer request.
Investigation remains incomplete; no test, render, reopen, duplicate, commit,
push, cleanup or issue closure follows this checkpoint without resume.
Prepared transcript and AV candidates remain local-only, unregistered/unrun.
Source pins must be reviewed/refreshed before any later staged action.


## Manual move reported; readback launcher timeout — October 1

After the bounded manual instructions, producer replied “moved”. One read-only
r5-edit-moved launch timed out in the bundled Hammerspoon CLI after10seconds.
No new injected result appeared; the prior13:25 saved checkpoint is not moved
evidence. Local process inspection found Resolve but no Hammerspoon process.
No nudge, save, reopen or edit was replayed. Timeout/config evidence is retained
in independent-action-20261001T134214.581624Z and r5-manual-move-report.json.

Disarmed the timed-out config, then staged only the read-only moved capture for
one operator Workspace > Workflow Integrations > VERA Issue 141 Observation
launch. Full manual move verification is pending; dashboard remains26/41.
Goal/hourly follow-up and all other testing remain paused. No unavailable
Resolve capability or speech/lineage claim follows this launcher failure.

## Resumed authority and post-restart readback — October 1, 14:22 UTC

The producer reported running Observation and restarting Hammerspoon, then
authorized automated testing again. Routine tests and comparisons use cheaper
subagents; ten-minute status updates are enabled. The investigation remains
incomplete at26/41.

Delayed injected calls finally returned. Three editorial readbacks refused
an unknown current render format; the independent full observation captured
zero getter failures but unequal adjacent fingerprints and visibly refused
consistency. All retained launcher progress records now terminate. These
results bound current capture readiness, not Resolve timeline capability.
The reported manual move still lacks a verified stable full moved-state pair.
No speech deletion, lineage, asset deletion or program visibility conclusion
is added. Retained compact evidence: evidence/bridge-readiness-stall; raw
capture SHA256211eb7be3ce91f56b16f5fe6eb68135626c82b5d60c36175cec92f08e62bee55.

## Manual move observed incompletely; restart — October 1, 15:59 UTC

Independent comparison confirms the requested record1..200/source0..199
geometry for both linked calibration clips in both latest timeline passes.
IDs, links and marker note are preserved. The capture still refuses changing
Baseline Usage readbacks, retains changed cache locators and lacks pool
passes, so the full R5 step remains unverified. No move retry is appropriate.
Publication: evidence/r5-manual-marker-move and r5-fresh-move-review.json.

After the producer-reported machine restart, process inspection finds Resolve
and Hammerspoon closed. Retained evidence is intact. Native work waits for the
exact synthetic project to reopen; local helper repair remains bounded to
read-only diagnostics with all identity/full-state guards preserved. This
adds no unavailable timeline or transcript conclusion. Dashboard remains26/41.

## Producer pause — October 1, 16:20 UTC

Investigation paused at producer request,26/41 complete. The restarted bridge
responded promptly but again refused Usage-only adjacent differences. Local
read-only helper repair is checked and registered; the subsequent Edit-page
return was refused at exact-project window identity before menu selection.
No further native collector/edit/save/render followed. Retained-data checkpoint
producer-pause-20261001T1620.json binds the terminal result and refusal. It does
not establish a newly saved Resolve project. Manual move/full R5 capture,
transcript getters and remaining R2/R3/output/repeat cases remain pending.
Resume starts with exact open-project identity and complete readback; the
manual move is not replayed. This pause leaves the full investigation open.

## Producer requirement: transcription coverage before transcript-based analysis

For the proposed Resolve-transcript approach to be used by VERA, the producer
requires Resolve transcription of all clips and requires VERA to enforce that
prerequisite. Absent or incomplete coverage must visibly block transcript-based
word/cut conclusions rather than make the application silently blind or turn
missing words into deletion evidence. This is a conditional adopted requirement,
pending the two producer-authored timeline results; it is not an implemented
coverage gate. The enforcement surface, freshness/version checks and treatment
of clips without transcribable audio remain unresolved. Coverage alone will
not establish complete mix routing or actual audible speech without evidence.


## Supplemental producer transcript test — first launch retained

On October 1 at16:55 UTC, the read-only probe dispatched once for transcription test1 and2. The named menu returned success, but the probe failed before transcription or occurrence geometry getters: AttributeError: NoneType has no attribute __name__. Original result SHA25670aa937fb7f17ccbe64719a2ca48b064154e3cde4471716809c68afd8e6ddeba is retained in the local dispatch review. The private configuration was restored exactly. Neither word sequence was observed; this is a probe serialization failure, not a reproduced unavailable Resolve capability. A checked serializer repair precedes any new read-only launch. No transcription, real-media file read/hash/export, timeline edit, save or render occurred.


The conditional all-clips transcription requirement is tracked as [Inbox design issue#146](https://github.com/mbelinkie/vera-script-to-timeline/issues/146), blocked by#141. It defines future coverage enforcement and explicit missing/stale states; this investigation does not implement it. See [coverage requirement](transcript-coverage-requirement.md).


## Supplemental producer transcript result — October 1,17:03 UTC

A repaired one-shot injected read completed on Resolve Studio21.1.0 build14 with unchanged project, current-timeline identity and page. Both timeline media-pool proxies returned None on two reads of GetTranscription(False) and GetTranscription(True). This bounds direct access for these two already-created timelines; it does not establish that every possible nested/transcribed timeline would return None. The shared source returned stable word-level transcription in both modes. No source-file read/hash, retranscription, edit, save, export or render occurred, and the private launcher config was restored exactly.

Combining retained source word times with enabled audio occurrence ranges yields these conditional source-aligned sequences:

| Timeline | API source-aligned words | Compared with producer expectation |
| --- | --- | --- |
| transcription test1 | Kai is three Finns singing in Swedish, playing out the stereotypes that Swedes have for Finns. Specifically, that Finns really like saunas. |22 words; producer accepts Kai as KAJ and confirms Specifically; only minor up/out transcription error |
| transcription test2 | Kai is three Finns playing out the stereotypes that Swedes have for Finns. Specifically, that Finns really like saunas. |19 words; only minor up/out transcription error; singing/in/Swedish omitted from selected source ranges |

Test1 has one enabled A1 occurrence; test2 has two at100% speed with the intervening source phrase excluded. This is useful evidence for transcript-based source-range reconciliation. Source29.97fps and start timecode14:57:30;11 have approximately two-frame endpoint uncertainty. Edge-word completeness and final audible mix remain unproved; enabled clips and source word timings alone do not establish track routing, mute/solo, effects or residual speech. The producer corrected the supplied expectation: Specifically is correct, and Kai is an acceptable rendering of spoken KAJ. The test succeeds at identifying the intended phrase removal, with only the minor up/out wording error. Independent timing/boundary review passes for the source-range mapping; source-derived text is not final-mix proof.

Local raw-to-derived bindings and ordered words/times are retained in out/issue-141-observation-20260930-01a0f318/producer-transcript-range-comparison.json (SHA256d4912a85ffea6f85854a2507cba3903b822261d720c06ee01cbac5e4a940fb6c), with native result SHA25619984e2f10e25e644cdbd565e17d19c2c4d64050433d4323f5d598986c8c1cae and raw readback SHA25608de0f64f2ae928b9fe7c81f47edb4e7f9776b0d89f909dc7590ee0666569355. The first failed launch remains separately retained. This supplemental test is additional to the unchanged41-check matrix; original count remains26/41.


## Producer correction and acceptance of transcript comparison

Producer clarified that KAJ sounds like Kai, Specifically is correct, and the originally supplied Namely was mistaken. Against this corrected expectation, both source-aligned sequences support the intended retained/removed phrase, with only out versus up as a minor Resolve transcription wording error. The producer considers this test successful and the approach workable. Original raw readbacks and the original supplied expectation remain immutable historical evidence; this correction governs the current interpretation. Complete transcript coverage remains a required future VERA gate (#146). This acceptance does not establish precise word-edge or final-mix behavior beyond the tested source-range comparison.


## Source-item loop proposed by producer

The proposed TimelineItem.GetMediaPoolItem().GetTranscription() loop reads the same source-level transcription exercised above. Its default argument is False. Both pieces of transcription test2 refer to the same source item, so that loop can return the same complete source transcript twice, including words excluded by the edit. The cut-aware result comes from applying occurrence source ranges. A video-track loop alone does not account for audio-only occurrences, surviving sound under picture-only cuts, repeated use, source-range exclusions, disable/mute/routing or speed. For the tested source-range text recovery, retain source-word timings and intersect them with the enabled audio occurrences in timeline order. The accepted injected Workflow Integration uses its supplied resolve object; no external scriptapp fallback is needed or authorized. This explains why source transcript access succeeds while direct timeline-pool GetTranscription returns None for these two timelines.


### Independent transcript timing review

Independent offline comparison confirms22 mapped words in test1 and19 in test2, omitting exactly singing/in/Swedish. Nominal29.97 semicolon conversion agrees with source frames within about1.06frames under the exclusive-end convention, or2.06frames for raw labels. Test2 first end is only0.874frames after the Finns word end: partial edge clipping cannot be ruled out. The next range starts2.091frames after Swedish. The intended phrase omission is supported and producer-accepted; fully preserved edge pronunciation and exact endpoint convention remain unproved. This limits the earlier derived artifact statement about silent boundaries. No real-media file or native application access occurred during review. Retained independent review SHA2564285f81a2db030fe6d895d8949cd2f6d9381fcb34bd32932923897fa5b59d55f. Supplemental test is complete for this bounded source-range behavior; original matrix remains26/41.


## Protected six-timeline stable observation — October 1, 18:08 UTC

The renewed native read-only capture returned equal complete adjacent timeline reads and equal pool reads with unchanged Edit/test1 context, idle rendering and an empty queue. Reusable pair SHA2565131589527428829afe6e1503e245609a4f17bb3207a2fe61a874db4289601b3 binds capture dd4c8c0e911e0bceec7379196d15c7e0c69eaa20b181e061b50cfbb025b0146f and pool82069be60e83da4c578e42231f3c88d9b99575c44d5c42649a04b66c988c8d9d. All six exact timeline identities are included; seven real-source records explicitly report protected-locator-not-accessed, and134 generated reachable records match their allowlisted hashes. This supplies stable full observation after the producer additions, not a new editorial result or universal atomic snapshot. Protected real media was not read/hashed/exported. The prior activation refusal and wrapper-summary/self-disarm handling failures remain retained; offline verification repaired the wrapper without another capture. R5 manual-move comparison and remaining synthetic case continuation use this fresh evidence.


## R5 manual marker-and-move verified — October 1, 18:17 UTC

Producer-confirmed manual move is now boundedly verified by fresh complete stable timeline/pool observations. Against the noted baseline, linked video3f2de461-d510-46f8-939f-0c794d48e38b and audio22561398-bce0-4c22-b55f-a73d3ad5e4cf have record start/end0/199 to1/200 in both passes, including subframe getters. Source bounds, IDs, links, enabled state and calibration marker identity/note are preserved. Comparison r5-independent-fresh-comparison-20261001T181642Z.json SHA256cf0704b9582f24060dd7ce9837c74d676b0c3388cb763762ac84c73537ea452c retains all unrelated changes: protected producer timelines/source additions, cache readback, selected-timeline context and omitted audio property keys. Existing source Usage values are stable. No atomic revision, ABA exclusion, independent menu-mechanism proof, all-fields-unchanged or audibility claim. R5-marker-and-move is complete for this named observation behavior; original matrix advances27/41. No manual action or move replay is required.


## R2 derived-end comparison complete — October 1, 18:28 UTC

Independent comparison r2-derived-end-independent-comparison-20261001T182834Z.json SHA256114516222043be335b59373088184c555de80b0a9ab79bc38620beb0e0d45c48 covers21 retained native pairs,42 stable passes and2776 audio-item observations. Verified48kHz source support ends are36258/132258/228258/324258 samples, or18.884375/68.884375/118.884375/168.884375 frames at25fps. The tested frame-grid clip edits report integer source frame boundaries, source times on a0.04s grid and integral record subframe values; word2 lies within source frames60..70. These clip-boundary observations do not supply per-word nonzero-waveform endpoints or prove complete program omission. The comparison check is complete with a bounded insufficient-evidence result. No fractional source edit was exercised: do not generalize integral observations into an API inability to represent fractional input. At that checkpoint, endpoint convention and edited output awaited PCM/routing evidence. Later completed PCM reviews establish the named normal-speed waveform findings, and endpoint calibration establishes exclusive ends for the tested integer cases. Complete routing, per-word native waveform endpoints and generalized fractional/retime precision remain unproved. Original matrix advances28/41; no test is declared successful merely from rounded/inferred ends.


## Matrix selected; context-dependent getter differences retained — October 1, 18:30 UTC

One journaled SetCurrentTimeline returned True and read back Matrix UID29ae8331-b86e-4041-a548-960695cc7b24. Before pair5131589527428829afe6e1503e245609a4f17bb3207a2fe61a874db4289601b3 and after pair59d4b9bde36af0c0a2c06a126f426fefd1e6dd1a76ddbf562574e70b535ff2b0 both have complete equal timeline/pool passes. The selection probe correctly refused its all-state-equality criterion: selected-context track-enabled/locked values and eight AudioDialogueLeveler/AudioVoiceIsolation property-key presence readings change. Independent review matrix-selection-delta-review.json SHA2564bd7d13b480662a170f72258f2263adb646fd23ce0f7c08372a4ab238e4b32a2 enumerates all differences and verifies no geometry, occurrence identity, settings, marker, link or pool/source metadata changes. Protected source metadata/no-file-access status is identical. Do not infer actual muting, locking or effect removal from inactive-timeline getters. The refused probe is retained; its fresh stable selected-Matrix after-pair is accepted as the current baseline for a NEW independent R2-picture case under prior producer authorization. No reverse selection, edit or cleanup is implied by that review.

The fixed observation launcher activation check now waits1s and uses one mainWindow object after activation. Exact project/frontmost/menu checks remain; fake missing-window-after-activation refusal passes. The next repaired named launch ran the selection helper, proving this observed launch path proceeded. Source hashf92cc1b6e5bd7e0611bf94aa9a7262f3c14936de03fc5072e1c0100593cd461d and original refusal evidence are retained. This is a launcher readiness repair, not a new Resolve capability failure.


## R2 picture-only harness refusal — October 1, 18:56 UTC

The guarded case preparation succeeded and retained two matching full-state
reads. Auto Select none, Auto Select V1 and deselect menus were dispatched once.
The subsequent injected editorial readback refused before getters because
probe.py retained the old editorial-readback.py hash dba56a71…ce32d22 rather
than the reviewed current d9df7622…e93690354. The executor terminated with exit
code 1; no split, deletion, retry or restoration was performed. Final protected
state after those selection menus remains unverified. This is a harness
registration failure, not a Resolve capability result; R2-picture stays pending.

The original terminal record is retained in
`out/issue-141-observation-20260930-01a0f318/r2-picture-native-executor-result.json`
(SHA256 bfc31c095fa21dedf8233b6a3b20db9cfd9c475be0df658821f6bf126e5dec59). Local repair must validate dispatcher-owned module pins before
any menu action and resume only from a fresh exact readback of the successful
prepared state; it must not replay preparation or discard the refusal.
Original matrix remains 28/41.


## Repaired dispatcher and exact prepared-state readback — October 1, 19:20 UTC

The dispatcher readback pin was corrected to the previously reviewed module.
The native helper now compares its expected child hash to the actual dispatcher
AST table and child bytes before any menu or native dispatch. Local helper,
cut-sequence boundary, editorial-readback and probe checks pass; current probe
SHA1125c66db1f902eef2ab0e09de195c8f75179b38edb7f3c8acc69e84c4fe7ffa
is registered with observe/protected-six. An initial root read-only invocation
used an unapproved label and refused before getters; its raw launcher failure
is retained unchanged. Corrected approved r2-picture-context readback completed
without edits. Full stable timeline/pool pair SHA4d21b54fa3fa855ee65a9d8af54a3be206927b6cafa87af7dc979d92ae4f3329
exactly matches the earlier successful preparation, and both selection passes
are empty with playhead00:02:22:10. The retained wrapper
r2-picture-resume-context-verified.json has SHAdc762e9398da4d5c5de8e9e8df9340ea0c62b9a685c6d2f5d6eaf0a750483e39. No split/deletion is
claimed; the cheaper executor owns the guarded continuation from that original
preparation, without preparation replay.

Parallel local PCM readiness confirms the existing source waveform support and
output metadata checks can be reused, but no existing program-PCM comparator
was found. pcm-analysis-readiness.json specifies a generated-source-only
comparison after an actual verified full-Matrix output exists; no output or
word-omission result is inferred. Original count remains28/41.


## Picture-only native cut complete; final audio pending — October 1, 19:34 UTC

Root-approved prepared-state continuation returned exit0 and
`single-track-sequence-complete`; no preparation replay occurred. Exact selected
V1 occurrence was split at3560 and3570, then actual middle UID
401f8da9-0a5c-4694-93f5-0d388348d0b4 was non-ripple deleted. Native deletion
record is3560..3570/source60..70, deleteReturn=True. Complete readbacks passed
the sequence's comparisons. Original five temporary track locks and playhead
00:00:00:00 restored; Auto Select reset followed by full stable final pair
90c4ad9a1cebcf1918165e1e62e4343ae225635012331afd56a9385ab8187661.
Sequence evidence is r2-picture-native-sequence-success.json and original
terminal execution record r2-picture-resume-executor-result.json. Independent
read-only review is running; final audibility and waveform word-support
observations remain pending actual PCM output. R2-picture is working, not
complete; original count stays28/41. No save, render or speech-deletion claim.


## Partial-word native cut complete; final waveform pending — October 1, 19:40 UTC

The approved R2-partial driver executed once and returned0 with
`single-track-sequence-complete`. Retained exact verified A1 middle UID
ffccdd65-ac26-4f02-ac8a-3dff69bb586d was non-ripple deleted at record4065..4070,
source65..70; DeleteClips returned True. Original track locks and playhead
00:00:00:00 restored. Full final pair
6ab9ed7028222f9a3fb0773ed66f86265b77a6035bdbbc4ebb0f7414c6bc9807
is stable; no save/render or complete word-omission claim. The execution
record r2-partial-native-executor-result.json has SHA8401366b28ffc1ac520ba241d41bd8c91822970a436b7024568162fdf43f67b0 and
r2-partial-native-sequence-success.json retains its parsed sequence.

The executor's final narrative incorrectly said the result file was absent;
root exact-path inspection found the retained returncode0 result and all actual
native captures, independently verified their bindings and final readback.
The narrative is retained; no run replay is needed or permitted. Final audio
comparison and independent complete-state review remain pending. R2-partial
is working and the original full-check count stays28/41.

Picture independent review verifies all result index bindings. Root's separate
complete raw pair comparison (picture-full-pair-independent-delta.json) confirms
that, outside the two final V1 target pieces, every timeline/pool field matches
the prepared state except23 shared generated-video source Usage leaves and its
one pool Usage leaf24→25. Both complete adjacent passes match. No unrelated
geometry, identity, marker or protected-source/timeline drift is present in
these captured states; this supplies no final audibility or lineage proof.


## Graphic enable refusal before split — October 1, 19:44 UTC

One R3-Graphic preparation attempted SetClipEnabled(True) on pinned V3 graphic
ea448c37-4821-419d-8fbf-112790cc0499; it returnedFalse. Native complete
before/after pair6ab9ed7028222f9a3fb0773ed66f86265b77a6035bdbbc4ebb0f7414c6bc9807
is exactly identical, V3 is locked and the target disabled. No split, lock or
playhead change, save, retry or cleanup occurred. Refusal analysis is retained
in graphic-preparation-refusal-analysis.json and original execution in
r3-graphic-native-executor-result.json. Setter ordering is the current
hypothesis: preparation enabled the layer before unlocking its locked track.
A bounded local fix will temporarily unlock only the exact target layer for
its enable call and use existing audited protected-lock setup afterward;
original-lock recording and full-state checks remain. This requires native
confirmation; it does not reproduce an unavailable SetClipEnabled capability.
R3-Graphic stays pending, goal remains active and independent cases may continue.


## Graphic native split and restored context retained — October 1, 20:07 UTC

The repaired locked-layer ordering enabled the pinned Graphic, restored its protected lock, and retained the actual linked V1/A1 split at Matrix8600. Raw ranges are8500..8600/source0..100 and8600..8699/source100..199; the enabled V3 Graphic remains distinct. Native split result20261001T195730.190697Z has SHA256 f86d8391359cdfc092105d8aa8742bdac867e5082175a160249908cf6cca3207. Initial restoration refused before setters because stale R2 second-position evidence remained in shared configuration. The shared fresh-case staging now clears case-owned references; the separate restoration did not replay the split. A final deselect-only operation retained two empty selections and playhead00:00:00:00. Final pair r3-graphic-context-20261001T200750.808432Z/pair.json has SHA256 b45c1e45ace27f59052618536cd0121646b4995297b6eb2628d87b3686d7e78b. Original refusals remain retained. Independent complete-state review is pending; no general visibility, lineage or ScriptDocument row mutation is claimed. Original complete count remains28/41 pending that review.

The next guarded boundary-base native test overlaps local Graphic evidence review and residual-driver checks. Only one agent may control Resolve; reviewers do not dispatch native actions or modify shared sources.


## Graphic structural check independently complete — October 1

Read-only independent review graphic-full-pair-independent-review.json verifies both complete raw pairs. Outside the expected V1/A1 split, only generated base.mov Usage25→26 and repeated.wav Usage47→48 differ. Enabled V3 Graphic is unchanged; protected timeline/pool state matches. Final deselect/readback gives zero selections and playhead0 twice. The initial restoration wrapper mismatch remains retained beside successful separate context recovery. This satisfies the R3-merge-graphic structural checklist criterion, without claiming general visibility, lineage or product row mutation. Dashboard now29/41.


## Boundary preparation refused; captured-schema mismatch diagnosed — October 1

Single boundary-base attempt refused with Exact enabled R3-boundary A3 crossing bed changed before any journaled mutation. Result20261001T202103.928483Z SHA256 f3307cfad904ff7c2dfe35976bcb973ed3e9c08269369f313228d44e6429f22e is retained. Root inspected the exact preceding stable Graphic pair: source UID0438f3a0-b58f-4d6f-a36d-81e02cdeaf3f, bed.wav Clip Name, start9000/end9199/source0..199, enabled item/track and empty links match. The guard instead requires source.GetName, which that captured source schema does not contain. Structural offline check exercised Graphic rather than boundary, so it missed this discrepancy. Bounded shared predicate repair plus real-capture-schema check is local only; no native replay has occurred. Executor originally mislabeled a stale live-config R2 afterPair reference as final current state; that historical reference cannot establish postflight equality. No fresh final-state equality is claimed for this refusal. Count remains29/41; the goal is active.


## Boundary captured-schema repair reviewed and registered

Root reviewed the bounded Clip Name predicate, the matching fake source schema, and actual retained-pair regression with wrong-name refusal. Actual-schema regression and fake base+A3 split checks pass. Dispatcher-owned module pin and native-driver source pins were synchronized before dispatch; native helper and both structural/residual local checks pass. Registration boundary-source-pin-registration.json retains the hashes; current probe SHA2562a6a3b1c40f80f98617a43c2ed08e925a4a9668b146c481f270de0e9a047e057. Configuration remains disarmed observe/None until the approved bounded actor stages its case. The first refusal remains retained; no final-state equality is inferred from a historical config reference.


## Boundary base split retained through final context — October 1, 20:39 UTC

The corrected exact-path executor invoked the driver once, then its own 30-second wrapper timed out. Root inspected authoritative process state and found original driver PID38693 still alive; it was monitored without replay until terminal. Actual preparation, authored-marker split-ready, linked split-review and restoration files exist. Root hash/phase validation retained boundary-base-native-phase-recovery.json. Successful base review is independent-structural-sequence-20261001T203741.675640Z/split-review.json SHA256ad691ead1c4d6b18f1a5feb2cf70a5ce239f45d802ac7a4ab2fd74c649b5036c; restoration SHA2562bcfef93a1f4bdda29fbfcd2630538ff2d1fcbd66ed7434529debabf8f084927. Final pair r3-boundary-context-20261001T203933.206631Z/pair.json SHA256b0f128efef59738307b6977872aa528f03761e11cd0dd14b7081d03f15743a65 matches restoration and gives empty selection/playhead0 twice. Process exit code is unavailable; native phases provide the actual operation evidence. No save/render or split replay. Separate A3-only native actor uses these exact base split/restoration pins while a read-only agent compares complete base raw deltas. Overall boundary check remains working until A3 evidence is complete.


## Separate A3 native split and context complete — October 1, 20:45 UTC

Reviewed ignored driver254e6c591bfc0ae3f6e029ed3e76124d651ec32ec19a12bf9c51dd809a544640 executed once with returncode0. Exact successful base split/restoration pins were required before preparing A3. Named A3-only selection/split-ready and complete split-review retain ranges9000..9100/source0..100 and9100..9199/source100..199. A3 split review independent-boundary-a3-20261001T204409.297455Z/split-review.json SHA25698a2b5047564f3d7faac0009a0120c960bed7fc09a8f8390e1536fc91a93cbc7. Final pair r3-boundary-a3-context-20261001T204545.218134Z/pair.json SHA256a6e02b7cfab4006e2494af652d7c76f52c41c8a1e5104a0ccc2e405245da2e66; original playhead0 and zero selections twice. Original executor summary mistakenly used preparation deselection at9100 as finalcontext; root verified/corrected index and retained originalwording without native replay. No save/render. Independent full raw comparison remains pending; authored marker supplies separate section evidence, disabled V3/A2 crossings remain preserved, and no all-crossings-gone or general visibility claim is made. Residual native continuation now uses this exact final pair while local review and offset work overlap.


## Boundary structural check independently complete — October 1

The retained read-only review `boundary-complete-independent-review.json`
(SHA256 `4f92d067db306939efcf1e2bf3d7adf8a7b55d557fd4acbe9c30f75445ecc90d`)
reports every boundary verdict true, including the whole structural criterion.
It binds both the base and A3 final readbacks to their manifest pairs, verifies
the authored 9100 marker, the two adjacent A3 pieces and their source ranges,
the expected Usage leaves, and the restored locks/playhead/empty selections.
The enabled V3 and A2 crossings remain unchanged. This completes the named
R3-boundary structural observation and advances the original matrix to 30/41.
It does not establish general program visibility, clip lineage, audibility or
that every crossing occurrence disappeared.


## R2 offset native sequence complete; output evidence pending — October 1

The R2-offset native sequence returned exit0 and retained the final readback
`r2-offset-context-20261001T205629.518751Z/pair.json` (SHA256
`7a7d0db1be976dd4e3463e1231a7e00923318742188c0a107c8fc0962085b40d`). The
approved edit shifted the unlinked A1 target one record frame later, from
5000..5199 to 5001..5200, while its source bounds stayed unchanged. The
complete pair comparison passed; both final selection reads are empty and the
original playhead `00:03:02:10` was restored. After unlinking, the related V1
`PitchCorrection` key is omitted by the established unlink readback model; this
is not evidence that pitch correction was reset. The native result is complete
for the record/source mapping observation, but output/audio evidence is still
pending, so R2-offset remains working. No save or render was dispatched.


## R2 residual first cut retained; review stopped on harness refusal — October 1

The residual driver retained the genuine first split at record frame 4560 in
`independent-residual-sequence-20261001T204911.843675Z/006-r2-residual-first-split.json`
(SHA256 `3e1b80af040b207a3f59323fffc4bafbb0a339a359392c21d2802511363b78ec`),
with the two selected items and playhead 4560 read back twice. The enabled A2
occurrence was preserved. Before a second cut at 4570, the driver invoked the
named full-state review too early; the retained review record
`first-split-review.json` (SHA256
`bef2efa0afe4bb253a40293af6da6b9db6c0cc6aa4b371737d74ad7b0611b786`) refused
with `A relative approved-output evidence pin is required`. The executor
record (SHA256
`43f83557be12d06be373756d568bb91cdf2efb10c608a825c67e5e685ada8e8b`) records
that no second cut, deletion, final readback, save or render occurred. This is
a bounded harness sequencing refusal, not a reproduced Resolve capability
failure. The first cut is retained and will be resumed from its verified state;
it must not be replayed. R2-residual remains working and the original matrix
count stays 30/41.


### Residual continuation checkpoint — 2026-10-01 21:49 UTC

The fresh read-only result `vera-issue-141-observation-result-20261001T214059.349190Z.json` retained an actual Matrix pair byte-identical to the offset checkpoint (SHA256 `7a7d0db1be976dd4e3463e1231a7e00923318742188c0a107c8fc0962085b40d`), with empty selection twice and playhead `00:03:02:10`. The earlier unknown-label refusal is a harness failure, not a Resolve capability result.

The one residual resume driver attempt reached actual second-position checkpoint `independent-residual-resume-20261001T214559.089529Z/second-position.json`, then stopped locally because its second deselection label was outside the approved readback list. Resume preparation, the position setter to `00:03:02:20`, and temporary menus ran; the second razor and interval deletion did not. The corrected executor index retains its original misleading wording separately. Do not replay the first cut, preparation, or position setter. `residual-position-continuation-record.json` binds the genuine completed phases for a bounded continuation; its repair/checks are local and not native completion evidence.

The offline PCM comparator is locally checked against the actual full-pair schema and pinned generated `repeated.wav`. Its generated self-checks and metadata parsing establish harness readiness only; no real Resolve-rendered output has been analyzed. Residual, offset, routing/audibility, duration calibration and other incomplete checks remain open. No speech deletion or project completion is inferred from these facts.


### Verified residual second cut; deletion pending — 2026-10-01

`independent-residual-resume-20261001T215903.877120Z/second-split-review.json` records the genuine second linked cut and its complete derivation check. The three V1/A1 ranges are `4500..4560 / source0..60`, `4560..4570 / source60..70`, and `4570..4699 / source70..199`; the residual A2 occurrence remains enabled. The subsequent menu selected the right tail at the boundary, so the caller stopped before deletion. `residual-position-native-executor-result.json` retains actual dispatched phases and the missing deletion/restoration. This is a harness selection mismatch, not unavailable Resolve editing.

The scoped harness repair uses the existing explicit `Timeline.DeleteClips` interval handles as deletion authority, retaining observed UI selection as diagnostic data. All exact UID/source/range/link, full-state, protected-data and live-context guards remain required. `residual-two-cut-continuation-record.json` pins the actual two-cut history; no cut or position setter may be replayed. Local preparation remains pending review and native execution.

The Resolve21.1 developer README Audio Mapping section and API stubs document `MediaPoolItem.GetAudioMapping()` and `TimelineItem.GetSourceAudioChannelMapping()`, including source channel layout, clip-attribute mute flags and linked-audio sample offsets. Copies/search results are retained locally. A guarded read-only getter probe is being prepared; these candidates are untested in retained141 captures and do not establish final Fairlight bus/solo/program routing. The earlier missing installed README path does not establish absent API capabilities.


### Retained audio-mapping evidence correction — October 1

The existing injected full-pair capture already includes successful `GetAudioMapping()` and `GetSourceAudioChannelMapping()` reads. `retained-audio-mapping-independent-review.json` verifies stable raw and parsed mappings for the two originally marked residual items on both passes. The earlier statement that these getters were untested was incorrect; no extra getter module is needed. This evidence exposes the tested source-channel selection and clip mapping mute attributes, but does not prove Fairlight track mute/solo, bus routing, final audibility, or linked-audio offsets (the observed linked_audio mapping is empty). A broader retained-pair review is underway.

Local residual deletion checks now demonstrate that wrong-tail UI selection is diagnostic only: deletion targets remain the two derived middle IDs, and wrong source/range or live-state drift refuses before deletion. The continuation driver also required a local variable-scope repair before execution. These are harness issues, not Resolve capability failures. Native deletion/restoration and rendered-output evidence remain pending.

Full retained mapping review (`retained-audio-mapping-full-review.json`, SHA256 `84aa3045878b06d735833a556bb26bba132bb7855950d85ac7b631db4f13a58f`) extends this observation to all132 Matrix items per pass: timeline mapping getters succeed132/132 twice. Pool getters succeed for7 of13 entries and are missing on6 timeline assets, with no errors. Identities and parsed mappings are stable twice. No linked-audio offsets are exercised. This strengthens source-channel inspection evidence, while leaving final mix/routing conclusions pending.


### Residual exact interval deletion and context restoration — October 1

The bounded continuation completed without replaying preparation, either cut, or the position setter. `residual-bound-driver-local-result.json` binds the successful phase index `residual-bound-delete-continuation-r2/execution-index.json` (SHA256 `f99dd45c35ad0b22dc510f6bdb70279680b10fc666d0155da09bad80d93cfdb1`), exact middle deletion, restoration and final readback. Final pair SHA256 `1616fa7f512b1a23d4c2756d2246bef51ee9d085ba8c443170ad060c385949a4`; original locks/playhead and empty selection were read back. No save/render was dispatched. First attempt evidence is preserved separately: it refused before deletion due to an absolute evidence path. Independent raw-pair review and program PCM remain pending; residual speech omission is not inferred.

Read-only full-pair verification is complete: `residual-bound-final-review.json` (SHA256 `8716d30850189fcf861f677d1c9e7afa39c5df3a81cba0eef4b4b6bd46c48f41`) validates14 referenced hashes, exact middle deletion without replay, restored own controls, both empty selection/playhead0 reads, unchanged protected tracks/pool/inventory, and enabled residual A2. The original first attempt index is retained with a correction: fresh capture succeeded, but absolute-pin validation refused before DeleteClips or its journal. Rendered audio remains pending; the structural result alone does not prove speech omission.


### Full-Matrix queue attempt retained; settings-display delta — October 1

The first fresh queue-only attempt reached recovery preset creation, XML export and successful SetRenderSettings, then refused before AddRenderJob/StartRendering. The executor summary incorrectly said no recovery files existed and called the refusal preflight-only; the actual journal in `av-output-20261001T231540.921062Z` proves the completed phases. Root diagnosis `av-full-matrix-settings-delta-diagnosis.json` compares full-pair004/005: only four pool leaves changed, the selected Matrix proxy Out display `00:01:37:24` became empty in both item/mapping copies on both passes. Timeline passes are identical; after timeline/pool passes agree. No clip-range edit or render capability failure is inferred.

The original recovery preset/XML, settings and failure evidence remain retained. A cheaper verifier checks that complete delta independently before a deliberately new queue-only test against the after-settings checkpoint. It will preserve the first recovery preset for final restoration. Second-attempt cleanup must not be described as restoring the original pre-first-attempt render settings; that outer restoration is still required. Actual program output and endpoint convention remain unproved.


### Full-Matrix job queued from verified after-settings state — October 1

`av-full-matrix-settings-delta-independent-review.json` independently confirms exactly the four Matrix-proxy Out display changes, unchanged timeline content/source identities, and stable after passes. The next deliberate queue-only attempt succeeded; `cli-av-queue-after-settings-result.json` binds owned job `0460d82a-3436-4efc-be12-b57c8523ebf5`, actual MarkIn0/MarkOut9199, recovery preset/XML, and checkpoint. `av-full-matrix-owned-continuation-config.json` was validated offline against that exact job. Queue metadata alone does not prove endpoint inclusivity or audio output. Fresh AV captures do not include selection/playhead readback; that limitation is retained, while SelectAllFrames binds render extent to the verified job.

One cheaper actor now starts this exact job once and polls it through the reviewed continuation; any subsequent poll uses resumeExistingJob=true without a second start. The first attempt's original recovery preset/XML remains outstanding after second-attempt cleanup. Outer render-state restoration is staged locally, not yet performed. No rendered PCM or speech-omission claim is made yet.


### Completed full-Matrix render and retained execution defects — October 2 UTC

The registered continuation initially passed validation but lacked its runtime dispatch route, silently returning observation only. The shared dispatcher now includes that route and refuses non-observe actions without a route; dispatch-registration-check.py covers all27 owned aliases and the missing-route regression. Earlier failed CLI invocations and observation-only dispatches did not start a render. These are harness defects, not Resolve capability failures.

The actual owned job0460d82a-3436-4efc-be12-b57c8523ebf5 started once. A later poll could not find the approved Observation menu during rendering and stopped without restarting. The resume-only call subsequently observed Complete/100% (267684ms). cli-av-owned-render-resume-result.json binds the original start and resume journals: one StartRendering request total, none on resume. Native output metadata reports9200 video frames,368seconds at25fps and PCM24/48k. Post-render and restored pair SHA256 equals the queued checkpoint d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14; those retained file hashes were checked directly and independently reviewed.

Owned job and second preset cleanup succeeded. The first attempt recovery preset remains present and restoration is still required; hidden render-settings equality is not exposed. Selection/playhead were not captured by these AV reads. The full-timeline render extent is observed; generalized item endpoint semantics and speech audibility remain pending. The first PCM analyzer ended with upstream502/503 connection failures before extraction/comparison, with no result artifact. A cheaper replacement resumes only offline generated-output analysis; the completed render is not repeated.


### Mute failure evidence and outer restoration review — October 2 UTC

The cheaper mute-helper executor added retained before/target pairs, exact setter requests/returns/errors and partial readbacks, with focused fake coverage for setter refusal, capture failure, restore refusal and unrelated drift. Root added a final read-only pair after restore refusal so a false setter is not mistaken for an observed mutation; that regression passes. The registered audio-mapping-mute action is limited to the existing generated A2 residual occurrence, one mute transition and own exact restoration, with no unlock/render/retry. The28-route dispatcher consistency and native caller offline guards pass. One cheaper native actor is assigned; native acceptance and audibility remain pending.

Independent outer-recovery review rejected registration because the helper never read format/mode after loading the preset, despite counting original journal reads. Its fake client lacked those getters. The correction now binds stable original journal format/mode, compares two post-load reads and a final read, and refuses wrong format/mode before preset deletion. Focused fake checks pass. The first correction CLI worker failed terminally on upstream502 connection errors without editing or calling Resolve; root performed this exceptional diagnosis fix. Outer restoration is still not dispatched. No source bytes, contracts, fixtures, production code or new dependency were touched.


### Actual rendered R2 waveform findings — October 2 UTC

Generated-only analysis pcm-real-render-analysis.json (SHA256 2d279ac63bfcc3d680ff8adbaf7d18bcc48b84b0fe13fa610d0390e74b88054d) binds the unchanged owned MOV, losslessly extracted PCM24 stereo48k WAV, actual queued/post-render/restored full pair, and six marked R2 cases. MOV contains9200frames and17664000audio samples, both368seconds with audio PTS0. The six findings are awaiting independent completion review before dashboard transitions.

- Linked and unlinked cuts: retained first/later spoken supports correlate strongly at zero lag (about0.998); the removed second-support window has correlation0.081 and low-level gap energy. This is bounded evidence that the known generated waveform is absent there, combined with separately retained physical edit geometry; it is not a general silence/routing conclusion.
- Picture-only cut: all four supports remain strongly correlated, including the audio through the removed-picture interval. Picture deletion alone must not be treated as speech deletion.
- Partial cut: the first9590samples of the second support remain strongly correlated before frame65; its tail falls in the low-level65..70gap. Word-edge decisions require partial-word handling/manual review rather than whole-word deletion inferred from a partial overlap.
- Residual A2: known speech remains strongly correlated inside the primary A1/video cut gap. The program waveform is observed; bus/track origin is not independently proved by correlation. Reconciliation must account for all relevant enabled audio occurrences rather than infer deletion from the primary pair alone.
- Offset: actual A1 frame5001 aligns at zero lag; frame5000 prediction requires+1920samples, one frame. This uses the current output and retained moved metadata, not an invented previous rendered baseline.

These observations support the tested100percent-speed source/range mapping path. They do not establish universal routing/audibility, time-warp behavior or generalized item endpoint semantics. Full-timeline render extent alone does not settle every GetEnd/GetDuration/source-bound convention. Protected real-media bytes were not accessed.


### Six R2 tests reviewed; native mapping mute restored — October 2 UTC

Independent completion review pcm-r2-independent-completion-review.json (SHA256 ff7ed203d8f14c627d853eb9b7a571eca11850de6f9545e3723ac588290c3cb2) confirms all six R2 cases performed with bounded structural and actual generated-program findings. Dashboard advances30→36 of41; duration calibration stays incomplete because whole-timeline extent does not establish all item/source endpoints. Broad routing/audibility claims remain open.

Native mapping mute result4eca5296df82b71cb80212ccb102c8c55df8451ab0b1a05427c29c80d8e9c1cd records muteTrue and exact originalFalse restoration on the pinned residual A2 item; both setters returnedTrue on its existing locked track, with no unlock. The full original before/restored pairs are equal, and after changes only the target mapping. Playhead00:00:00:00 remains. The subsequent held-mute render completed and its extracted PCM24 stereo48k WAV SHA256 d2581dc047a348a104821cbd53c7b84e4a47b80fd4443ebf52f6fbd3382362a7 exactly matches the unmuted baseline WAV. The retained comparison binds occurrence UID f4e9f649-894a-42f2-9f54-a8321ae7c163 and finds both channels unchanged across [4500,4699), the [4560,4570) speech gap and frame4570; the held mapping flag therefore does not establish mute of program speech on this build/case. This is not evidence of a universal API failure. Fairlight Solo and bus routing remain untested. See mute-pcm-comparison-result.json and cli-mute-native-once-result-reviewed.json. The CLI compact summary has a trailing literal newline escape; original is preserved and cli-mute-native-once-result-reviewed.json retains a parsed derivative plus raw hash and verified original native result/pair references. This formatting defect affects the summary artifact, not the native result.


### Original render snapshot restored and cleaned — October 2 UTC

cli-outer-native-once-result.json (SHA256 08cfdf5636d1a49b7158c933eb2452ed0e8e0d2e0e5dfbaea53839dfe3e5c267) records original-render-settings-restored. Root verified native result, journal and final-pair hashes. The journal has one LoadRenderPreset and one DeleteRenderPreset request, both scoped to original owned preset VERA141_AV_OUTPUT_20261001T231540.921062Z; actual post-load formatMOV/H264 and mode1 were observed twice and again after deletion. Final full-pair hashd8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14 remains equal to the verified content checkpoint. All XML/output/original evidence remains; hidden render-settings equality is not exposed. No render, clip edit, save or extra Resolve action was dispatched. The first-attempt recovery obligation is now satisfied.

Next audio work needs explicit held-mute and bound restore phases, tested locally before registration; the already-passing immediate roundtrip mute is not treated as a muted program-output test. Final R1adapter and getter-specific endpoint evidence review proceed locally in parallel.


### Endpoint calibration independently verified — October 1 UTC

`endpoint-calibration-corrected-review.json` and
`endpoint-calibration-independent-verdict.json` retain the corrected separation
between base-only picture frames 199/200 and the later transparent-overlay local
frames 199/200. The independent verdict is **PASS**. Its rerun of
`analyze-endpoint-audio.py` under CPython 3.14.7 `-S` rechecked the manifest-bound
generated `bed.wav` and rendered PCM: timeline frame 9198 is nonzero and
correlates with source frame 198, while frame 9199 is exactly silent although
source frame 199 is nonzero. Full-pair getters are item-scoped: the tested 100%
audio tail reports start 9100, end 9199, duration 99, source 100..199, with
matching float overloads.

This completes the duration-convention calibration dashboard entry only for the
tested 100% integer-valued cases, advancing the dashboard 36/41 to 37/41.
Fractional precision and generalized retime endpoint semantics remain untested;
the retained 50% capture is a raw observation and does not broaden the result.
The full-pair metadata retains 14 `protected-locator-not-accessed` records, and
the independent verifier records `protectedMediaBytesAccessed=false` and
`protectedMediaHashAccessed=false`. Corrected-review SHA-256 is
`9e6379e11ea3918f8fa4c88c0639b03803b67c8c94ff49db2642c13c0322260f`; independent-verdict
SHA-256 is `6b89f04893b693a76464464bac8157a8e3ac7f451c2ce829c08bba688fd5ad37`.
Current activity is held A2 mute already verified, local render-plan preparation,
and no native test running. The four remaining entries are final R1
repeat/second duplication, mute/Solo/routing output, report consolidation and
External review.

### Held-mute output and exact restoration — October 2, 02:33–02:39 UTC

The preceding activity statements describe earlier checkpoints. The held-mute
job `c5b1925b-f5aa-49d5-850a-be7a64c5cd29` is now Complete/100%. The same-job
continuation issued no new StartRendering request. Its MOV hash is
`7c69f239a3a8e08f5617c4e72f843c345d91bf3baef813f7c43501efccbcbbf4`.
`mute-render-existing-job-completion-summary.json` binds the native result,
owned terminal-job cleanup and restored render context; hidden render-settings
equality remains unexposed.

`mute-pcm-comparison-result.json` binds the completed generated-only output and
the unmuted baseline. Both extracted PCM24 stereo 48 kHz WAVs have SHA-256
`d2581dc047a348a104821cbd53c7b84e4a47b80fd4443ebf52f6fbd3382362a7`.
The entire waveform is identical, including the targeted [4500,4699) interval
and [4560,4570) speech gap. This reproduces a limitation of treating the observed
channel-mapping mute flag as proof of program silence in this case; it does not
establish the cause or a universal API failure. For #131/#139 and #101–#104,
speech-omission classification must therefore require stronger output/routing
evidence or manual review rather than relying on that flag alone.

The first post-render restoration readback refused the Edit/empty-queue guard
while Resolve was on the render page. After one approved Edit-page menu action,
a fresh readback permitted exactly one A2 mapping restoration. The native
result hash is `4f373da796ea36e07abace6c3cc5429df5cfff4580a699f25e09139421806ea6`;
the restored complete pair hash is
`d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14`,
exactly equal to the original pre-mute pair. `audio-mapping-restore-summary.json`
retains the original refusal, successful setter, playhead and complete readback
bindings. No protected real-media bytes were accessed.

Reviewed R1 repeat actions are registered locally with passing focused checks;
registration is not a native test result. Fairlight Solo/routing operator
evidence, final R1 repeat/second duplication and closeout remain pending.
Progress remains **37/41**.

### Fairlight Solo-on preflight and queue — October 2, 03:19–03:30 UTC

The operator reports A1/A2/A3 initially had Mute/Solo off, then A2 Solo on.
Output/bus labels were not visible; this leaves routing unknown, rather than
establishing absent routes. `fairlight-operator-solo-on.json` retains these
statements. Native preflight verifies the named project/Matrix and two complete
equal reads; the pair hash remains
`d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14`.
Thus the current collector does not distinguish the reported Solo states.
The installed-documentation audit `output/r1-fairlight-api-doc-audit.json`
finds documented source mapping/mute getters but no matching Fairlight Solo or
bus/output-routing getter in the searched README/stub; this is limited to those
documents and does not establish global API absence.

`fairlight-queue-only-summary.json` binds the queue-only native result SHA256
`24092845ecfd4d457138fcb62f55e5c9b036c7e2b155c46a7debfb10a65f7ca6`
and job `a6ed7f33-9ad4-4d82-bfac-ff72903f4567`. Before/after pairs match the
checkpoint; recovery XML and requested PCM24/48k settings are retained.
Queue setup issued zero render starts. The result arrived after the caller's
wait expired and was recovered from that same action without replay.
Exactly one separate render start is authorized next, followed by same-job
observations and generated-output comparison. A2 Solo stays on; later manual
Solo-off restoration is pending. No Solo-output conclusion is available yet.

### Solo render started; observation menu disabled — October 2, 03:37–03:42 UTC

The separate start issued exactly one StartRendering request and received True
for job `a6ed7f33-9ad4-4d82-bfac-ff72903f4567`. Native result SHA256
`a1a06c6c17481915614cc3c3456e42071d904a750fa5c661216e74e4ebb90482`
reports Rendering at1%. The same-job follow-up with `resumeExistingJob=true`
refused before native dispatch because the menu was unavailable. A subsequent
read-only check of the existing launcher finds the exact menu present but
disabled. `fairlight-render-stop-summary.json` and
`fairlight-menu-disabled-check.json` retain the observations. The last native
status remains nonterminal; no second start, output comparison or Solo
conclusion occurred. Wait for the menu to become enabled before observing this
same job. A2 Solo remains on and later operator restoration remains pending.

### Verified completed-render pause checkpoint — October 2, 03:51 UTC

The already-issued same-job observation settled successfully after the pause
request. Native result SHA256
`7b19db15cbdf37ba852243387b5165e082725beba49c91ad46dfc8fbc7f3efed`
reports Complete100% and `render-complete-restored`. The journal records zero
additional render starts, successful owned job/preset cleanup and an idle
renderer at recovery end. Final complete pair SHA256
`d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14`
matches the original queue checkpoint. The368-second,9200-frame generated MOV
has native-reported SHA256
`8af6fb6916afa4c1bc674617ad52460928582a3dbc22dd2af8550786bd28020c`.
`fairlight-render-completion-summary.json` and `pause-render-checkpoint.json`
retain the terminal and resume bindings. A2 Solo stays on; generated-audio
comparison and operator Solo-off remain unperformed. Progress stays37/41;
the goal, dashboard and ten-minute monitor are paused. Resume by comparing the
retained terminal output, never by issuing another render start.

### Retained Solo output comparison — October 2, resumed investigation

The active goal resumed from the completed-render checkpoint. A subagent ran
the existing local comparator exactly once after verifying the terminal
handoff and output binding. `solo-output-comparison-result.json` has SHA256
`d111349ccce1b8dbf0592bff624f8208646104a2f245df43f5530fea4bbd7996`.
It binds the Complete job, native-reported MOV hash, generated PCM extraction,
original complete pair and operator Solo-on report. No new Resolve call or
render occurred during comparison; no protected real-media bytes were read.

Both output channels have RMS/peak exactly zero in the tested A1-only speech
window [4339210,4356258) and A3-only control [7804800,7814400). Baseline RMS
there is respectively0.13276585 and0.00763862. The A2 speech-plus-bed control
[8755210,8772258) has Solo RMS0.09399102 versus baseline0.09457784. All four
tested generated A2 source supports correlate at approximately1.0, zero lag
and gain0.70794576, with negligible residual. Whole-program Solo RMS is
0.00583994 versus baseline0.03788207; the files differ as expected for this
control-state change. The A3 comparison measures energy, not bed-source
correlation.

These observations are consistent with retained A2 speech and exclusion of
the named A1/A3 output controls under the operator-reported A2 Solo state.
They demonstrate a bounded Solo-sensitive rendered output on this build,
not complete routing, bus origin, live monitoring audibility, speech deletion
or lineage. The current collector still cannot distinguish the Solo states.
For #131/#139 and #101–#104, structural/transcript observations alone cannot
authorize general spoken-omission adoption without mixer/output evidence or
manual review. This limit affects reconciliation of existing edits; it does
not demonstrate a failure of the core script-to-timeline authoring workflow.

One operator Solo-off restoration request is pending. After the reply, obtain
fresh unchanged full state before the final R1 repeat. Progress stays37/41
until restoration and the named remaining evidence checks are reviewed.

### Solo-off restoration reviewed — October 2, 12:11 UTC

The producer replied exactly “solo off” to the existing restoration request.
`solo-off-restored-state-20261002T121158.440922Z.json` retains independent
verification of one fixed Edit-page action and one fresh injected readback.
The fresh pair and post-selection pair both equal the prior complete checkpoint,
SHA256 `d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14`.
All six protected timelines, protected media metadata, Matrix context, original
locks, playhead zero and empty selection remain unchanged; the renderer is idle
and the queue empty. Solo/Mute state remains operator evidence, and complete
routing remains unknown. The preceding Edit/empty-queue refusal is retained;
no render was repeated. R2-disable-mute is complete within these limits,
bringing progress to38/41. Final R1 repeat/second duplicate, report consolidation
and External evidence review remain.

### Final reopen and duplicate preflight — October 2, 12:13–12:22 UTC

The final save/close/load ran exactly once. All three calls returned success,
with the exact project identity after load. Independent retained review
`output/r1-reopen-final-independent-review.json` classifies the result
`PASS_WITH_TRANSIENT_READBACK_REFUSAL`: the first post-load capture refused
exactly eight Usage differences between adjacent timeline reads, with stable
pool reads; the next retained pair is stable. Before-to-stable comparison has
only eight Resolution readings changing from0x0 to1920x1080 for the two producer
transcription timeline proxies across both pool passes. IDs, content, source
metadata, markers, geometry and selected context are preserved. These getter
changes remain explicit; no save/reopen replay occurred.

The second-duplicate invocation stopped before DuplicateTimeline. Native result
SHA256 `c8558ade1c6ad39d48181f86b8be77f0d4f4b836ce9bdab8e203c563d99fe61c`
records `selected R1 source signature changed; no duplicate attempted`.
Its complete preflight/selected-source captures are retained in
`r1-repeat-duplicate-20261002T122220.047704Z`. The last observed project still has
six timelines, with R1 selected. Changing selection changes inactive versus
active track enabled/locked getters and eight audio dialogue/voice properties;
the helper wrongly included these contextual readings in its structural
identity equality. This is a harness refusal, not duplication-capability failure.

The local comparison repair retains every raw field, excludes only those exact
context-sensitive getters from the cross-context structural signature, and
preserves all other identity/source/range/marker/property guards. A replay of
the actual refusal failed before the correction; the existing fake checks and
real-capture regression now pass, including refusal of changed IDs, source
bounds, record bounds, clip enablement, markers and an unlisted audio property.
`output/r1-selected-context-local-repair.json` binds the local candidate hashes.
No registered pin was changed and no native continuation was dispatched.
Independent repair review and guarded Matrix-selection restoration precede the
actual final duplicate. Progress remains38/41; no native test is currently running.

For #101–#104, observations used for control/effect preservation must be obtained
in the same selected-timeline context. Inactive getters are unknown for those
claims; the structural projection does not make them reliable or infer speech
absence. This is a reconciliation observation constraint, with no reproduced
failure of the core authoring workflow.

### Reviewed selection restoration registration — October 2, 12:53 UTC

The bounded structural-signature correction passed independent review. The
standalone `r1-repeat-restore-selection` action also passed independent review
(`output/r1-selection-restoration-independent-review.json`). It binds the exact
selected-R1 refusal pair/context and original Matrix pair/context, permits one
selection setter, then requires exact Matrix readback equality. Registration
and focused route/pin checks passed in
`out/issue-141-observation-20260930-01a0f318/r1-registration-20261002T125156.968930Z`.
The installed action remains `observe`, with protected-six inventory and
External Scripting None. No live restoration result is yet claimed here.
One bounded restoration is authorized before the final duplicate; no reopen,
render or editorial operation is repeated. Progress remains 38/41.

### Restoration launch refused before injected dispatch — October 2, 12:54 UTC

The executor attempted the registered restoration once. The fixed menu macro
passed its initial project-window guard, activated Resolve, then refused with
`Project changed; stop: <no main window>` before selecting the integration menu.
No injected result or selection setter followed; no duplicate was attempted.
The terminal menu refusal is retained in
`independent-action-20261002T125424.498570Z/launch.json`, and the executor state is
`output/r1-final-native-executor-20261002-state.json`. The launcher returned to
`observe`/protected-six. Resolve and Hammerspoon processes remain running; this
does not establish why the window was unavailable or a Resolve API failure.
The bounded operator action is to bring the exact project window forward with
no dialog open, leaving clips/controls unchanged. R1-repeat remains pending its
actual restoration/duplicate readbacks; progress remains 38/41. No test is
running while that action is pending.

Independent review `output/r1-restoration-menu-refusal-independent-review.json`
confirms the pre-integration exit, no native restoration result, no duplicate
attempt and the current registered probe pin. This launch refusal remains a
window-availability blockage, with no API-capability conclusion or automatic
retry.

### Fresh window readiness and bounded continuation — October 2, 13:05 UTC

The unchanged pinned macro's read-only `check()` returned the exact project
title and found the enabled observation menu, with `triggered=false`; no
activation, staging or native dispatch occurred. Evidence:
`output/r1-current-window-readiness.json`. This supplies the missing window
availability information without another operator confirmation. The prior
terminal refusal remains unchanged. The coordinator authorizes one new
restoration invocation under the existing bounded producer approval, reusing
the reviewed helper and original exact pair/context guards in a separate
continuation record. See
`output/r1-window-readiness-continuation-decision.json`. No duplicate is
authorized until actual restoration equality is independently reviewed; any
new refusal stops this invocation without retry. Progress remains 38/41.

### Native selection restoration succeeded — October 2, 13:10 UTC

The bounded continuation completed `r1-repeat-restore-selection` once. Its
native result, `vera-issue-141-observation-result-20261002T131042.182117Z.json`
(SHA-256 `4b7de4d96c27ee7bd43ec592a85b56a3e47e80a6c68e6644143ab8093b22ee19`),
reports exactly one `SetCurrentTimeline(Matrix)` and complete target pair/context
equality. The executor wrapper is
`r1-final-executor-restore-20261002T131040.592207Z/result.json`, SHA-256
`faa5da4d6e775b6ccf7e259895aa71bc53881991b038fac68c12fb7683dca576`.
Original terminal refusal/state/readiness files are unchanged; no save, render,
clip, lock or playhead mutation was performed. Independent restoration review
is required before the actual final duplicate. Progress remains 38/41.

### Final native duplicate retained — October 2, 13:16 UTC

Independent restoration review passed in
`output/r1-selection-restoration-native-independent-review.json`. The final
native sequence then retained a fresh exact Matrix checkpoint and invoked
`r1-repeat-duplicate` once. Native result
`vera-issue-141-observation-result-20261002T131625.143034Z.json`, SHA-256
`117fcc6ae0f432b9160436faf3053982df7c3f5417a51fa2efd922fa661d92dd`,
reports `local-r1-second-duplicate-result`. It created
`VERA 141 R1 identity repeat`, UID `1835476c-8bc1-48fc-bb78-99906490480a`,
with six new occurrence IDs and shared source IDs, restored Matrix selection,
and retained protected-seven captures. Wrapper:
`r1-final-executor-duplicate-20261002T131605.126740Z/result.json`, SHA-256
`8f2e2328a2416af43aa0dbd60967446c79300fd9de1141d353a6eae024235652`.
Independent complete original-six/pool, duplicate-signature and context review
remains pending, so R1-repeat is not yet counted done. All native testing has
stopped: no further shared collector, save, cleanup, render, rename, deletion
or launcher invocation is authorized after this seventh timeline. Retained
captures are the authority for remaining local review/report work.

### Final seven-timeline independent review passed — October 2

`output/r1-final-seven-independent-review.json` is
`PASS_WITH_EXPLICIT_LINEAGE_LIMIT`. All four checkpoint-bound before/source/
immediate/final pairs are stable. The exact seventh timeline/name is verified;
six new occurrence IDs are disjoint from every original occurrence, and copied
signature/media multisets match in the same Matrix-selected context. Original
six non-Usage fields and original pool non-Usage fields are preserved. Only
expected source Usage changes and one duplicate proxy/mapping appear; no
unknown unrelated delta is found. The journal records one duplication and R1
selection followed by Matrix restoration, with no save/render/cleanup. Final
Matrix context equals the original target. R1-repeat is done; progress 39/41.
Copied signatures and shared media do not establish editorial lineage. Final
report consolidation and External review remain; no native action follows.

### Consolidated report ready for External review — October 2

`final-findings.md` records all R1–R5 bounded results, the supplemental accepted
transcript reconstruction, the required #146 coverage/freshness gate, retained
collector limits and safe downstream handling/owners. The unchanged 41-title
evidence index is reconciled: 40 done, zero working, one pending; every named
reference exists. Existing independent reviews are reused without a raw full
test rerun. No native action was taken for consolidation. The sole remaining
gate is the operator's final review as specified in `operator-checklist.md`:
`Issue #141 External evidence confirmed`, or a named discrepancy. Standing
scripting/synthetic-scope attestations are retained and not requested again.
The investigation and active goal remain unfinished until that response is
retained; no issue closure or readiness change is made.
