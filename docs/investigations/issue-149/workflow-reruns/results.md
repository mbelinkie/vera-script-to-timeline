# Issue #149: Workflow Integration confirmation of W1–W7

Status: all seven Phase10 test procedures have retained outcomes. W1, W2, W4, W5 and W7 reproduce their required named gates; W3 and W6 are adverse. All seven row records are independently reviewed and published on both issues. Extra neutral-X rendering stopped on later unrelated TC/Out-mark drift; that unrun extension is distinct from W2's completed required criteria. This report does not accept or close #149 or #141.

The producer requested confirmation of [codex-rerun.md](../codex-rerun.md) through the injected Workflow Integration path in a new disposable project. [verdict-review.md](verdict-review.md) reconciles every independent verdict with #141, including the exact source/object differences for mapping mute and linked-audio retime. Historical observations remain attributable to their original build and setup.

## Boundary and retained setup

- Intended project: `VERA Issue 149 Workflow Reruns 20261002-kit-01`.
- Native context confirmed Resolve `[21, 1, 1, 10, ""]`; Studio edition is producer-reported. Native captures confirm CPython 3.14.7 on x86_64 macOS 15.1.
- External Scripting remains `None` by producer instruction/attestation. This is not an API getter result. The boundary matters because VERA must work through its injected integration without asking the producer to enable an external connection.
- New synthetic media: [fixture-record.md](fixture-record.md), regenerated from the retained #149 word recordings. W6 replacement retains both video and mono audio stream layout. Protected producer media and the prior projects are excluded.
- Exact dispatches, hashes, before/after captures and restoration records will be bound below. Render queue additions are retained and reported; no queue or timeline cleanup is authorized by this experiment.

## Execution gates retained before W tests

See [execution-record.md](execution-record.md). The new menu was unavailable before a Resolve restart and became available afterward. `context-01` and `context-02` stopped in harness serialization of native objects, before project creation. These are logger bugs, not failed Resolve capabilities. The corrected `context-03` returned `ok`, confirmed the version, and reported the startup `Untitled Project`. The first preparation verified that startup project was empty and created the named disposable project, UID `1a05ff3a-8b04-43e3-95ab-c970b93b6415`. `SetSettings` returned true; readback was timeline frame rate `25.0`, resolution `1920×1080`, and sample rate `48000`, while read-only `timelinePlaybackFrameRate` remained `24`. The guard stopped before media import. That preparation capture contained zero media items, timelines and occurrences. This is a preparation precondition mismatch, not a W verdict or a general retime capability failure. The producer then requested a stop at the next checkpoint; the exact save checkpoint is recorded below. No automatic preparation replay or settings correction is authorized by that checkpoint.

## W verdict table

| Row | Claim | Current classification |
|---|---|---|
| W1 | Timeline subtitles follow linked cut, picture-only cut and disabled A1; agree with renders | **Reproduced** for all three cases; [record](w1-result.md) |
| W2 | Current-timeline OTIO Mute/Solo fields agree with rendered output | **Reproduced:** X Mute and Y Solo flags/output agree; Y Solo-off export and baseline-equivalent output restored. Extra neutral-X render unrun. [Record](w2-result.md) |
| W3 | Exact mapping mute silences A2 and restores | **Adverse:** flag changed, A2 audio unchanged; restoration verified. [W3 record](w3-result.md) |
| W4 | OTIO constant retime and rendered click timing; embedded versus separately sourced linked A1 | **Reproduced:** scalar 0.375 and 5/5 clicks within one sample; embedded A1 follows, separate A1 does not. [Record](w4-result.md) |
| W5 | Audio track enabled getters depend on current timeline | **Reproduced:** independent current/inactive getter review complete and published. [Record](w5-result.md) |
| W6 | Same-layout byte replacement, pre-relink output and successful relink; restore | **Adverse:** all four renders completed with original source ID 1, including after relink True. Original bytes/mtime and PCM restored. [Record](w6-result.md) |
| W7 | Track locks refuse selected UI deletion and clip-disable setter; unlock | **Reproduced:** exact selected UI Delete and API disable guarded, four item identities/content preserved, locks restored and saved. [Record](w7-result.md) |

Each completed row will use the #141 new-result fields: challenged claim, run/host/runtime and docs, exact object/source IDs, preconditions, ground truth, expected result/counterexample, exact operations/returns, raw pair/journal/terminal hashes, output extraction/state binding, measured result, restoration or partial state, independent comparison, classification, remaining alternative explanation, and effect on VERA.

## Saved producer pause checkpoint

`save-checkpoint-01-20261002-kit-01` called `ProjectManager.SaveProject()` exactly once and returned `True`. Terminal result SHA-256: `d3b6612878ec9cdcbf7a68102dde5a2049029b438745c04e2cfb4490822b531a`. Complete pre/post captures were byte-identical, SHA-256 `ab8cedc21293de77bb12e8835dfd0d420edb6af411393f38e99144e9b46eb0c9`. The verified project UID is `1a05ff3a-8b04-43e3-95ab-c970b93b6415`; both captures contain zero media items, zero timelines and zero occurrences. Configuration is disarmed. Verification is retained at `out/issue149-workflow-reruns-20261002-kit-01/pause-checkpoint-verification.json`. At that historical checkpoint no W test had run; W1–W7 were pending.

This was the producer-requested historical pause. The later explicit resume and subsequent setup/test results are recorded below; neither issue is accepted or closed.

## Producer resume

The producer explicitly resumed after the verified save checkpoint. Continue in the same disposable project, preserving the partial preparation and save evidence; do not recreate the project. Autonomous cases precede operator-dependent Mute/Solo actions. No W verdict is established by the preparation checkpoint.

## Resume setup interpretation

Installed scripting stub documents `ProjectSettings.timelineFrameRate` as writable and `timelinePlaybackFrameRate` as read-only. The W handoff specifies a 25 fps timeline and render; it does not require changing the read-only project playback field before timeline creation. Retain the mismatch, validate the created timeline at 25 fps, and verify the first render’s encoded rate, duration and frame/source mapping before deriving W verdicts. This interpretation does not assert that playback 24 has no effect in every context.

The first continuation import used `ImportMedia([{"FilePath": ...}])`, returned `None`, and left the full project capture unchanged and empty. It did not reach SaveProject. This method invocation is an adverse import result under the named setup; it does not establish a general inability to import media. A fresh bounded action uses the path-list form previously exercised by #141, after verifying the same empty project and hashes.

## Successful continuation import

`import-media-02-20261002-kit-01` invoked path-list `ImportMedia` once, returned all 10 hash-pinned synthetic items, and called SaveProject once with `True`. Terminal SHA-256: `d6566cedfeea24ec1a24be8aadd0d87c1ac7b49e06b74940b4853ea3aa45dd06`. Project UID remained `1a05ff3a-8b04-43e3-95ab-c970b93b6415`; pre pool 0, post pool 10, timelines 0. Project settings retained frame rate 25.0 and read-only playback 24. The configuration was disarmed. This is preparation evidence, not completion of a W row.

## First native timeline

`build-pilot-01-20261002-kit-01` succeeded and saved `W3-mapping-mute`, timeline UID `8c67340f-2428-407c-86f7-ce553152a86c`. Native timeline settings are 25 fps, 1920×1080, 48 kHz; default V1/A1 were preserved and mono A2/A3 added. The complete post capture contains four occurrences; AppendToTimeline for AV returned the V1 handle only, so its return list alone is not the full occurrence inventory. Terminal SHA-256: `0ab40c85caa91e99dbf50e1199e9e3a26ba5de7dfcefd2d64a9788ae23dabf53`. Mapping mute and rendered output remain pending.

## Verified baseline render

The first native render completed at 100% (job `531c3325-30ba-4232-9017-11a523b1c787`). Independent extraction verified H.264 640×360 at 25/1 fps, 399 frames/15.96 seconds; signed 16-bit stereo PCM at 48 kHz, 766080 samples. Every decoded frame matched source 1 and its frame index 0–398. All 16 fixture words were detected (scores 0.974–0.996); pilots were 1000 Hz 0.02828, 1500 Hz 0.01986, 2000 Hz 0.02003. See local `out/issue149-workflow-reruns-20261002-kit-01/baseline-analysis.json`. This establishes the output calibration for W3, not mapping-mute success.

## W3 verdict

The exact A2 mapping toggle was accepted/read back, yet all eight number words and the 1500 Hz pilot remained. Baseline, muted and restored PCM hashes are identical. This repeats #141 on Resolve 21.1.1.10 through Workflow Integration, so a version change alone does not explain #149’s Console result. The mapping was restored with no unrelated delta in the immediate restoration pair. Broader baseline-to-final comparison retains a playhead difference and two attributable queue additions; no complete-context equality is claimed. See [W3 record](w3-result.md). Other tests continue.

## Published W3 record

The retained W3 new-result record is posted on [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5963821842) and [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5963823005). Both remain open. W3’s Deliver-page result stands as measured; an Edit-page controlled follow-up is pending.

## W1 partial request recovery

All remaining nine timelines were built and saved (ten total). The first linked-cut duplicate was created once and CreateSubtitlesFromAudio returned True. The immediate SaveProject call returned None while transcription was running; the retained request is a harness checkpoint failure, not a failed subtitle capability. One read-only poll then found Complete plus two subtitle items. A fresh save checkpoint returned True; the existing duplicate rendered Complete. No duplication or transcription request was repeated. Other W1 cases wait for corrected save ordering; local output comparison runs concurrently.

## W1 published verdict

Three edited-mix subtitle cases reproduce the named speech differences and agree with renders. The two cut-case generic frame-index checker failures were checker misuse, not failed speech gates. [#149 record](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5963986370), [#141 record](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5963986555).

## W4 published verdict

[Posted #149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964033332) and [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5964033458). Constant37.5% output timing passed; separate-source linkedA1 stayed100%, unlike embeddedA1. This is concrete source/link setup behavior on the same build, without claiming version causality.

## Current operator checkpoint and additional publications

W7 native selection/lock/Delete/unlock/save is complete and independently reviewed. All native launches are held for the existing request: on the Edit page, W2-X-mute A2 M on; W2-Y-solo A2 S on; all other M/S off, leave Y open and reply both set. No new dispatch is staged while waiting.

W6 full record posted on [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964191971) and [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5964192100). The Edit-selected W3 follow-up and restored PCM verification are posted on [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964195014) and [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5964195159). Producer acceptance is pending; both issues remain open.

W7 full result posted on [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964227757) and [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5964227952). The native configuration remains disarmed and launches are held for the existing operator setup.

## Published verdict reconciliation

The complete row-by-row #149/#141 comparison, updated with all five reviewed W results, is posted on [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964283820) and [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5964284062). W1/W4 issue records now include the final raw journal/pair bindings; this was a documentation update, not another native test. PR150 remains open at head922d9a73a5c7e18b5770193046939191851d3a63, and #149 remains open. The remaining W2/W5 configurations are being prepared offline; native staging/launch still requires the pending operator setup reply.

## Operator controls and final restoration

The producer replied **both set** after setting Edit-page X A2 Mute and Y A2 Solo. Fresh `02` actions verified the expected current-timeline OTIO flags and completed both primary renders. X omitted all eight number words; Y retained those eight words and omitted all NATO words. The producer subsequently replied **both off**. The bounded restoration package now verifies neutral OTIO flags, renders both restored timelines once, restores only its owned timeline/playhead/page context, and saves the final checkpoint. Earlier waiting and preparation sections above are historical; no duplicate operator action is requested.

## Producer pause — 2026-10-03

The producer requested **stop at checkpoint** after replying **both off**. Native work is limited to settling the existing render, restoring owned context and saving; then all launches stop. Six W rows are reviewed, including the locally complete W5; its issue publication remains pending. W2 is not marked complete: retained neutral-output comparison and final checkpoint bindings still need consolidation. The ten-minute recurring follow-up is paused. Resume from retained actions and outputs; do not replay primary tests or restore media again.

## Producer-requested stopped checkpoint

The producer replied **both off**, then requested **stop at checkpoint**. The existing neutral-Y render settled Complete at100%; its output SHA-256 is `3284339a0cd2c675af276d34ff1540c36c784bb34311ed3bd792234c938662b1`. Neutral Y OTIO SHA is `0ca7911b5c4b5b8712e212badcdd153a94ac7e8a43510bb73aa65d7570031379`, with Audio1/2/3 enabled and SoloOn false. X mute-off is producer-attested and its owned context was restored; a neutral X export/render was intentionally not started after the stop request.

Final context is W2-Y-solo UID `bec69cf7-c76e-4820-9e1f-9b425449614f`, Edit page, `00:00:15:24`. `save-checkpoint-w2-restoration-stop-01-20261002-kit-01` called SaveProject once, returned True, and has terminal result SHA `c0673b83c946fbd200fa5c1bd76c325ac9bdc4f141a48faf08766f1fb7301aeb`. The native actor confirms all known render jobs terminal, installed configuration `__disarmed__`, and stopped. Inventory remains13timelines/64items/23media. W4 retime state is intentionally retained. No old #141 project or protected producer clip was modified.

Six W rows are independently reviewed; five published. W5 publication and W2 retained neutral-media analysis/final result consolidation remain pending. Neither issue is accepted or closed. The recurring ten-minute follow-up is paused. Resume from retained evidence, without replaying completed actions.

## Final completion resumed

The producer requested “let’s finish it off.” Completed native actions are retained without replay. A fresh guard precedes only the remaining neutral-X export/render and owned-context/save checkpoint; local neutral-Y output analysis runs concurrently. W5 is now published on [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964921838) and [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5964921987). Producer acceptance remains separate.

## Producer review after final evidence publication

Review the current W verdict table and the row-by-row [reconciliation](verdict-review.md), with the public per-row records linked in this report. Confirm the named supported scopes: edited-mix subtitles on duplicates, current-timeline track Mute/Solo, constant37.5% timing, current-only getters, and the selected lock/Delete guard. Check that the mapping-mute and media-refresh contradictions stay unresolved and that no lineage, routing or atomicity guarantee is inferred. If accepting this evidence addendum, record explicit acceptance on #149; otherwise identify the row and discrepancy. These documentation/test results do not themselves close #149 or accept #141. No new Resolve operation is needed merely to review the report.

## Final bounded outcome

The required W2 procedure is complete: X A2 Mute exports disabled and removes numbers; Y A2 Solo exports true and retains numbers only; its Solo-off export returns false, and a completed neutral render restores all16words and baseline PCM. An extra neutral-X export/render was planned for broader restoration assurance but was not part of the Phase10 pass criterion. A fresh resumed read revealed TC and Out-mark changes since the saved checkpoint, so this extension stopped without editing or saving the changed state. The changes are retained with no assigned cause. Prior matched pairs, attributed renders and SaveProject=True checkpoint remain evidence of their exact times; they do not establish current-context equality.

For VERA, the tested duplicate-subtitle, current-timeline controls and constant-speed OTIO paths can inform bounded reconciliation. Mapping mute cannot safely imply silence in this Workflow Integration setup. Relink success/Online metadata cannot safely imply replacement frames. Both require actual output verification or manual review while their cross-run causes remain unknown. No experiment here proves unique ancestry, all-effects visibility, complete bus routing or atomic apply.

## Final W2 publication

The complete W2 record is published on [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5965021351) and [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5965021531). All seven required rows now have independently reviewed records on both issues. Native work is stopped and the launcher is disarmed. The later drift remains unassigned; no save or correction followed it.

The final supported/adverse summary is posted on [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5965027605) and [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5965027786). The earlier row-by-row verdict comments were updated with all seven final outcomes. Native work remains stopped; raw evidence remains local and available through this worktree.
