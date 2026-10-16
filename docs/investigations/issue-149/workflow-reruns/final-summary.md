# Issue #149 Phase 10 — final Workflow Integration outcomes

The seven required re-runs were exercised on Resolve 21.1.1.10 through the injected Workflow Integration object with External Scripting None, in the new disposable project `VERA Issue 149 Workflow Reruns 20261002-kit-01` (UID `1a05ff3a-8b04-43e3-95ab-c970b93b6415`). Five named gates reproduce; two produce adverse results. Completed tests include adverse outcomes: this does not mean seven supported capabilities or producer acceptance.

| Row | Result | VERA consequence |
|---|---|---|
| W1 | Reproduced: linked cut removes charlie, picture-only cut retains it, disabled A1 leaves numbers; subtitles and renders agree | Edited speech is accessible by CreateSubtitlesFromAudio on disposable duplicates. Phrase captions are not word-exact timing. |
| W2 | Reproduced: X A2 Mute removes numbers, Y A2 Solo leaves numbers only; current OTIO flags agree and Y Solo-off restores baseline audio | Current-timeline Mute/Solo are observable for these controls. Bus routing/sends remain unknown. |
| W3 | Adverse: mapping mute true reads back, yet all eight numbers and pilot 0.01986 remain; PCM equals baseline, including Edit-page repeat | Do not infer program silence from the mapping flag. The same-build Console/WI contradiction remains unexplained. |
| W4 | Reproduced: OTIO scalar 0.375;5/5 clicks within one sample. Embedded linked A1 follows, separate-source linked A1 stays at 100% | Use exact tested OTIO time maps and handle source/link topology explicitly. No general curve/29.97fps claim. |
| W5 | Reproduced: X current [true,false,true], X inactive all false, Y current all true; X restored | Select and verify the intended timeline before active-only getters. |
| W6 | Adverse: same-layout byte replacement and RelinkClips True still render original source 1; expected decode failure/source 2 switch do not reproduce | API Online/path/date/returnTrue cannot prove byte identity or displayed replacement. Hash and verify actual output. |
| W7 | Reproduced: four locks guard selected Delete and SetClipEnabled(False); item identities preserved; unlock/save verified | Bounded lock guard works; atomic apply and universal setter protection remain unproved. |

Mapping mute’s contradiction is not explained by version alone: the new WI run uses the same 21.1.1.10 build as Claude. Linked retime’s concrete difference is embedded shared source versus separately sourced linked audio, reproduced in one project/build. W6’s OS atomic replacement changed inode while retaining mtime; Claude’s exact byte replacement procedure is not established, so this is a recorded difference rather than a causal explanation. Copied stamps still do not prove ancestry, sampled/simple visibility is bounded, and database timestamps/locks do not establish atomicity.

The last verified save returned True, retaining13 timelines / 64 items / 23 media items and intentional W4 retimes. A subsequent read-only resumed guard found timecode and Out-mark drift; its cause is unknown. We retained it and stopped the extra neutral-X render without correcting or saving that changed state. W2’s required S-off export/output gates were already complete. Neutral-X output remains explicitly untested.

All raw pairs, journals, configs, exports, media and analysis are retained locally in `out/issue149-workflow-reruns-20261002-kit-01/`; the local reports/harness are under `docs/investigations/issue-149/workflow-reruns/`. Public issue summaries do not imply that those large raw artifacts have been uploaded. The #141 handoff’s current limitation list cites #149’s superseded scopes while preserving historical evidence.

Producer review remains pending. **Do not close #149.** This addendum does not accept or close #141.

## Published row evidence

- W1: [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5963986370), [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5963986555)
- W2: [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5965021351), [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5965021531)
- W3: [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5963821842), [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5963823005)
- W4: [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964033332), [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5964033458)
- W5: [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964921838), [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5964921987)
- W6: [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964191971), [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5964192100)
- W7: [#149](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5964227757), [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141#issuecomment-5964227952)
