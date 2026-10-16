# Issue #149 Workflow Integration discriminator final summary

## Producer acceptance — October 3, 2026

The producer accepted #149 and directed its roadmap card to **Done**. The accepted evidence is [PR #150 commit e020bd1](https://github.com/mbelinkie/vera-script-to-timeline/blob/e020bd1b15b6294cc6a9e8c0c2fa330d71ede0c4/docs/investigations/issue-149/README.md), the published WI confirmations, and [Claude’s same-project Console setter comparison](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5971577666). Earlier pending-review/open instructions in this record are historical and superseded by that explicit acceptance. The #141 report now adopts hash/timestamp/relink/render reload, excludes WI mapping mute as an output control, uses edited-mix transcription/render for program words, and maps remaining limits to #131/#139/#144–#146. #141 remains open for separate sign-off. No additional Resolve work was run.

## Final five-case comparison

All five requested discriminators have independently reviewed native outcomes on Resolve Studio **21.1.1.10**, External Scripting **None**, in the new disposable synthetic project `VERA Issue 149 WI Discriminators 20261003-kit-02`. The protected #141 project and `semi1b.mp4` were excluded.

| Case | Classification | Measured result |
| --- | --- | --- |
| D6-kept: atomic replacement, kept modified time, relink | **Reproduced** | All 399 decoded frames retain source ID 1. |
| D6-changed: atomic replacement, modified time +1 second, relink | **Reproduced** | All 399 decoded frames use replacement source ID 2. |
| D3-direct: fresh never-rendered timeline, WI mute and render | **Adverse** | Getter mute:true; A2 pilot 0.01986; all eight number words remain. |
| D3-console: WI mute, operator Console render without remapping | **Adverse** | Getter mute:true; A2 pilot 0.01986; all eight number words remain. |
| D3-operator: WI mute, operator opens Fairlight only, WI render | **Adverse** | Getter mute:true; A2 pilot 0.01986; all eight number words remain. |

The A2 silence gate is ≤0.001 with no number words. All three W3 cases fail that gate while retaining the A1/A3 controls and valid picture markers. Moving rendering to Console or opening Fairlight did not remedy a Workflow Integration-applied mute. Claude’s **Console-applied setter** remains a different path; the internal cause is unresolved. This does not establish universal mapping-mute failure or a deferred-update mechanism. VERA must not infer program silence or speech removal from this WI mapping flag alone; use output verification or a separately validated control. No core script-to-timeline authoring failure was reproduced.

Both W6 results support the bounded #141 design input: **detect replacement by content hash; force reload with changed modified time → `RelinkClips` → render verification**. Online status, Date Modified and relink success alone do not establish replacement display. Other codecs and cache contexts remain unproved.

Original source hashes/times and all three original A2 mappings are restored, and restored output is independently measured for every case. The direct post-restoration closeout is complete, job `de6df76f-a57b-4642-aafd-75fa30955a2d`, SHA-256 `75170940ae0b2b09e48fc298a2dd8ecd438372b36f5382712f52158134453feb`. Final `SaveProject=True`; pre/post snapshot SHA-256 `c0f8757df49d537d96ec00cbbbba0a80330fbf32a2c3f9dbe1862ae527a99a82` is identical. The saved project retains 9 timelines, 36 items, 16 pool objects and 12 terminal render jobs; Resolve is idle and both bounded configs are disarmed. No further operator action is requested. **#149 remains open for producer review; acceptance is not inferred.**

The initial Fairlight relative-target refusal and Console ASCII wrapper failure are retained as harness failures before native rendering, separately from the five native outcomes. No failed native action was blindly replayed.

Case records: [D6-kept](d6-kept.md), [D6-changed](d6-changed.md), [D3-direct](d3-direct.md), [D3-console](d3-console.md), [D3-operator](d3-operator.md). [Independent saved-checkpoint review](final-checkpoint-review.md).

Published: [final result on #149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5970657049), [linked summary on #141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5970661013).
