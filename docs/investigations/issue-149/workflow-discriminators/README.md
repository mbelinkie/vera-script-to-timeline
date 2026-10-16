# Issue 149 — Workflow Integration discriminator follow-up

## Producer acceptance — October 3, 2026

The producer accepted #149 and directed its roadmap card to **Done**. The accepted evidence is [PR #150 commit e020bd1](https://github.com/mbelinkie/vera-script-to-timeline/blob/e020bd1b15b6294cc6a9e8c0c2fa330d71ede0c4/docs/investigations/issue-149/README.md), the published WI confirmations, and [Claude’s same-project Console setter comparison](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5971577666). Earlier pending-review/open instructions in this record are historical and superseded by that explicit acceptance. The #141 report now adopts hash/timestamp/relink/render reload, excludes WI mapping mute as an output control, uses edited-mix transcription/render for program words, and maps remaining limits to #131/#139/#144–#146. #141 remains open for separate sign-off. No additional Resolve work was run.

This follow-up tests the producer's five discriminators against Claude's [commit 67c0115](https://github.com/mbelinkie/vera-script-to-timeline/tree/67c01157a20716a63a265ce9213afd9b4d948b02/docs/investigations/issue-149/evidence/discriminators) and [summary comment](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5965294977). The earlier W1–W7 results remain separate historical evidence. This document does not infer producer acceptance or close #149.

## Current result

**5/5 cases reviewed: two reproduced replacement outcomes and three adverse mapping-mute outcomes.** All restoration/output checks and the final save are complete. Native work has stopped; no operator action remains. See the [final comparison](results/final-summary.md) and [independent checkpoint review](results/final-checkpoint-review.md). Earlier pending/paused entries below are historical checkpoints. #149 remains open for producer review.

## Execution boundary

Use the new disposable project `VERA Issue 149 WI Discriminators 20261003-kit-02`, synthetic fixtures with matching video and audio layout, External Scripting `None`, and Resolve's injected object through the existing Workflow Integration menu. The retained #141 project and `semi1b.mp4` are excluded. The [plan](plan.md), [task brief](task-brief.md), [source evidence review](evidence-review.md), and [independent preflight verification](verification.md) define the exact guards, media geometry, calls and output gates.

Each native action has a unique dispatch receipt, disarmed configuration, journal and captured pair. A pending render is collected by its original job ID. It is never started again. W3 restores the exact original mapping and compares the final state with the actual pre-mute capture; render queue and context changes must be attributed explicitly. W6 retains runtime hashes, inode and modified time in nanoseconds, then restores the original owned bytes and time and verifies the restored rendered source.

## Required case results

| Case | Required discriminator | State |
| --- | --- | --- |
| D6-kept | Atomic replacement, original modified time, relink: decoded source ID 1 | [Reproduced; restoration independently verified](results/d6-kept.md) |
| D6-changed | Atomic replacement, new modified time, relink: decoded source ID 2 | [Reproduced; restoration independently verified](results/d6-changed.md) |
| D3-direct | Never-rendered target: Workflow Integration mute and render | [Adverse; mapping restored and saved](results/d3-direct.md) |
| D3-console | Workflow Integration mute, operator Console render without remapping | [Adverse; restored output/state verified](results/d3-console.md) |
| D3-operator | Workflow Integration mute, operator opens Fairlight, Workflow Integration render | [Adverse; restored output/state and final save verified](results/d3-operator.md) |

W3 silence requires the A2 1500 Hz pilot to be at most 0.001 and all eight number words to be absent, with the A1 NATO and picture controls intact. Getter readback and setter success alone do not satisfy the output gate. Every completed result uses the #141 new-result fields and be classified as reproduced, adverse, unknown or harness failure.

## Retained preparation refusal

The first context action, `context-01-20261003-kit-02`, refused before menu selection or native execution because the current window was Claude's actual disposable project `VERA 149 Discriminators 20261002-b`, which was absent from the initial name allowlist. That exact name was verified against commit 67c0115's README, summary and runner. The repaired guard permits only that known synthetic name or the prior #149 synthetic name, requires the observed project UID before creation, and retains the refused receipt. This is a harness setup failure, not a Resolve capability result. A subsequent context action has its own unique identifier.

The Console command explicitly binds its source filename while preserving the injected `resolve` object. Its configuration pins both Console helper and adjacent harness SHA-256 values before disarming or performing native actions. It uses the documented `SetCurrentRenderMode(1)`; Claude's earlier discriminator script called unavailable `SetRenderMode(1)`, so entry point remains a hypothesis until these output comparisons are complete.

The unique second context action, `context-02-20261003-kit-02`, reached the Hammerspoon menu-selection call but returned a receive timeout. No launcher progress, native journal or result was observed, and its configuration initially remained armed. Missing start evidence does not establish that the menu was never selected. The action is an uncertain dispatch/observation failure, not a W3 or W6 outcome. Recovery must preserve its receipts and disarm the configuration before another native action is staged; the menu action is not automatically replayed.

Recovery archived the armed configuration (SHA-256 `19fcf7444fbd3a4dc31c6afb613743846e7a163e3680496c051bbe975b9e81e3`) and atomically disarmed it (SHA-256 `d23d415936fa6d2b03ee80b207ed623678b9781c1ab1e6014cde155b2952f8db`). The read-only window query responded, but the exact menu lookup also timed out. The operator was asked to select the registered menu once with this disarmed configuration, expecting only a retained refusal. All further native dispatches are held for that observation and the operator reply.

The operator replied `selected`. The launcher consumed the disarmed configuration and wrote the expected `unknown or disarmed action` terminal refusal. Unique action `context-03-20261003-kit-02` then succeeded through the automated menu, reporting Resolve `21.1.1.10` and the expected Claude disposable project name. This does not identify the cause of the earlier menu timeout. The context collector omitted the project UID required by the known-disposable creation guard; preparation therefore stopped before project creation. A subsequent source revision adds only the read-only `GetUniqueId` getter to the context action, with independent focused verification before a new unique context observation. Earlier source archives and action results remain retained.

`context-04-20261003-kit-02` observed the prior disposable UID `14375719-513e-456a-9aed-3a2baa54c01a`. `prepare-01-20261003-kit-02` then refused before `CreateProject`: the creation guard expected `JobStatus` in `GetRenderJobList`, whereas the actual returned rows contained job IDs and settings without status. This is another retained harness failure. The correction queries each listed job through `GetRenderJobStatus(JobId)` and requires terminal status plus `IsRenderingInProgress()` returning `False` before creating the new project. It does not delete jobs, infer status from missing fields, or change the old project.

With the corrected queue guard, `prepare-02-20261003-kit-02` created the fresh project UID `0591bb41-d645-4af7-a2ee-ff75f8f43162` and applied the requested settings. It stopped before media import because the timeline rate read back as 25 but the separately read-only playback rate remained 24. The complete `post-partial.json` and subsequent read-only observation retain this empty-project state. The operator was asked to change only Playback frame rate to 25 under Project Settings → Master Settings → Timeline Format, then Save. All launches are held for that reply and a fresh settings readback. No new project creation is needed for this continuation.

After the operator replied `25 set`, a fresh read-only observation and synthetic import completed; seven source media items were imported and `SaveProject` returned `True`. The first build created `D6-kept-20261003`, UID `9ce8ac2d-bd57-4740-9c19-044d3df53347`, then stopped in `_link_v1_a1`: its AV append returned a one-element list containing V1, while the full partial capture contained four items on V1, A1, A2 and A3. The harness expected both V1 and A1 in the append return. The partial timeline is retained for exact layout/link verification; no build replay, cleanup or test-output inference is authorized by that return alone.

## Producer-requested pause checkpoint

The successful second build used separate picture and audio append calls against the same embedded AV source, then explicitly linked V1/A1. It created five fresh `r2` timelines and preserved the earlier partial timeline. This construction detail must remain in the eventual W3 results as a potential setup difference from an AV append; it does not establish entry-point causality.

At the producer's `stop at checkpoint` request, native actions stopped before any render, source replacement, relink or mapping-mute test. One owned `SaveProject` call returned `True`; its complete before/after captures were equal. The project has six timelines, 24 items, seven imported source files and six timeline proxies (13 pool objects), with an empty render queue. Current timeline: `D6-kept-r2-20261003`, UID `70aee9bd-5928-4e3b-9f0e-f45897773337`. Timeline/playback are 25 fps, resolution is 1920×1080, and audio is 48 kHz. The installed action configuration is disarmed. All five case classifications remain pending.

Save result: `save-checkpoint-user-stop-20261003-kit-02`, SHA-256 `0ba02bdd3b87180d8f43b392718518e43624234a5e691ad0ab9a3ed3120770f2`. Read-only checkpoint observation SHA-256: `39ebeb290cdee5c37f3a1d250e0cc10fb862832ee1147076e92bdc08531507dc`. See the retained [checkpoint note](../../../../out/issue149-workflow-discriminators-20261003-kit-02/checkpoint-user-stop.md).

On an explicit resume, first verify the saved state and frozen source hashes. The kept-time case's actual source is `media/base.mov`; the changed-time case's source is `media/swap.mov`. Bind each replacement, hash/stat record and relink call to that case's actual source item. Restore shared `base.mov` bytes/time and verify output before any W3 case. Do not replay failed setup/build actions, reuse the original partial timeline as a completed test, or start a baseline render of a W3 target before its mute.

## Design decision gate

Only if both W6 required outcomes reproduce may #141 adopt the bounded rule: detect replacement by content hash; force reload with changed modified time → `RelinkClips` → render verification. Online status and the API's Date Modified field do not establish source-byte identity.

For W3, silence in Console or after the operator step alongside audible direct output would be consistent with a deferred mix update. Audible output in all three would establish an adverse result for these tested Workflow Integration contexts. Neither pattern establishes a universal internal mechanism or a general Resolve inability to mute audio.

## Autonomous continuation after resume

The producer authorized proceeding as far as possible without them. The kept-time comparison completed through its original render job: the atomic replacement changed the file hash and inode, preserved modified time `1790976491073030271` ns, and `RelinkClips` returned `True`. All 399 decoded frames remained source ID 1. Restored output also decoded source ID 1 and matched baseline audio measurements; independent full restoration review is pending before final case classification. The changed-time case is running on its separately owned `swap.mov`. The two operator-dependent W3 stages will remain pending until their exact actions are staged and the producer returns.

Both replacement discriminators are independently reviewed and restored. Kept modified time rendered source ID 1; changed modified time rendered source ID 2. The bounded #141 design input is now supported: **detect replacement by content hash; force reload with changed modified time → `RelinkClips` → render verification**. This remains scoped to the tested media/layout/cache context and does not make a relink return sufficient.

The [complete W6 discriminator records](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5966033331) are posted on #149 and [linked from #141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5966036845). The #141 handoff now distinguishes this explained reload discrepancy from the remaining metadata inference limit.

## Fresh native AV shape for W3

Three additional, never-rendered `D3-*-av-20261003` timelines were built using one AV append for the embedded V1/A1 source, matching the native construction shape of Claude’s fixture. Full capture—not the append return list—verifies reciprocal V1/A1 links and independent A2/A3. The [independent pre-mute gate](results/d3-av-pre-mute-review.md) passes: prior six timelines/24 items preserved, total nine timelines/36 items, six prior render jobs unchanged and no D3 render job. Original `base.mov`/`swap.mov` hashes and times are restored. Earlier separate-append r2 preparations remain retained and will not substitute for these W3 cases.

## Final producer-requested pause checkpoint

Three of five cases are independently reviewed: D6-kept **reproduced**, D6-changed **reproduced**, D3-direct **adverse**. Direct mapping mute retained pilot 0.01986 and all eight number words despite getter mute:true. The [direct full record](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5966117633) records output SHA, complete pairs, analyzer provenance and limits. Original mapping was restored; save returned True with byte-identical pre/post captures. All seven queue jobs are terminal, Resolve is idle, and Workflow Integration configuration is disarmed. No Console configuration was created. The native AV Console/Fairlight targets remain fresh, never-rendered and **unrun**. No action is requested while paused.

Checkpoint: `out/issue149-workflow-discriminators-20261003-kit-02/recovery/checkpoint-final-user-stop.json`; independent review: `out/issue149-workflow-discriminators-20261003-kit-02/recovery/d3-direct-restored-checkpoint-review.json`. The next resume requires no project recreation or fixture rebuild. It proceeds from a fresh settings/context observation to the separately staged Console case; do not replay completed actions or infer producer acceptance.

The producer subsequently said **resume**. The verified saved checkpoint remains retained; the next bounded activity is WI mute-only and hash-bound operator Console rendering on the fresh AV Console target. The Console and Fairlight cases remain unrun until their actual operator/result evidence is retained.

## Current bounded operator step

The [Console staging gate](results/d3-console-pre-render-review.md) is **GO**: exact AV fixture, target-only A2 mapping change, queue still seven, idle, no case render, valid helper/config/source/UID/path bindings. [Operator instructions](operator-console-step.md) contain the exact command. Native launches are held until this operator result. The planned direct post-restoration render was unrun at the requested stop and remains an explicit closeout check; snapshot restoration does not substitute for program-output evidence.

## Console wrapper decoding recovery

The operator’s command failed in `open(helper).read()` with ASCII decode error at byte 45 before compilation or helper execution. The older runner line was confirmed as earlier Console history. The [local recovery review](results/d3-console-decode-recovery-review.md) reproduces the exact error and confirms explicit UTF-8 read/compile succeeds without changing the helper/config. A fresh injected full capture exactly matches the staged mute post (`ff4ffeca6b63239d6f7faa98f8cf15d84506a8991cdd19a484d6ffbea2badce8`); no Console receipt/job/output exists. Only the operator wrapper now uses `open(helper, encoding="utf-8").read()`. Same bounded action remains unrun, and capability classification remains pending.

## Console render received

The producer ran the corrected command. The single Console job `bca942f4-c4d6-4a8a-9b64-0831b1587312` completed; output SHA-256 `6fb687d847ee6cb5426bae9a5deb35119a0944b441d1d87fb7eb81059ba1376e`. Independent measurements retain pilot 0.01986 and all eight number words with getter mute:true, valid NATO/bed controls and source ID1 in all399frames. Outcome is provisionally adverse while restored output/full-state checks finish. Original A2 mapping restore is captured; no Console replay is requested.

## Console finalized; Fairlight event received

The [Console new-result record](results/d3-console.md) is **adverse**, with restored program/state verified and [published on #149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5970434832), [linked from #141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5970449417). Four of five cases are reviewed. The [fresh Fairlight precheck](results/d3-operator-fairlight-precheck.md) passed; the operator explicitly replied **Fairlight open** to the page-only/no-playback request. Its render and restoration now proceed through Workflow Integration. No additional operator action is requested.

## Final closeout

All five case records and the [final comparison](results/final-summary.md) are complete. The [independent checkpoint review](results/final-checkpoint-review.md) verifies restored media/mappings/output, all 12 terminal jobs, unchanged frozen sources, disarmed configs and the saved idle project. The previously deferred direct restored-output check is now complete. No further Resolve work is running.

Published: [final result on #149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5970657049), [linked summary on #141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5970661013).
