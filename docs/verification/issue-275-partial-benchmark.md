# Issue 275: partial benchmark results

**Status: blocked at the Resolve delivery step.** Timing, compilation and package verification succeeded for the retained fresh assets, the unchanged cache and the one-row edit. No case completed a successful Resolve save/reopen, so these results do not establish end-to-end turnaround.

## Current Inworld benchmark (2026-10-24–25)

The run used the selected Inworld TTS-2 / Arthur route on a MacBookPro16,1 (Intel) with DaVinci Resolve Studio 21.1.1. The unchanged compiled sample is 1,143 frames at 24,000/1,001 fps (about 47.7 seconds), with two narration rows and 102 words, 11 timeline events and 17 package media artifacts. The one-row edit produces a 1,149-frame timeline (about 47.9 seconds).

The six existing media-preparation receipts were reused from #300. Media preparation therefore remains unmeasured, and these are not fully cold media-preparation cases. No competing media task ran during the guarded Resolve attempts. Optional review rendering was not run.

| Case | Narration generation/cache | Automatic timing | Compile and media-needs | Package build and verification | Resolve |
| --- | --- | --- | --- | --- | --- |
| Fresh narration assets, resumed after the earlier compiler refusal | The two prior fresh-miss generation/normalization observations were 2.805 s and 6.782 s; no new provider call was made for this resume. | Retained audio remeasured with networking disabled: 2.976 s and 7.130 s. Both rows produced verified `qualified_linear_transform` evidence with zero sample correction. | 0.353 s / 0.046 s | 74.051 s; verified, 17 media artifacts and 6 preparation receipts | Two guarded attempts each hit the script tool's 60-second ceiling after creating a disposable project. Neither produced a timeline or final result record. |
| Unchanged rebuild | Both rows were cache hits: 0.961 s and 0.277 s; no provider calls. | Reused the verified timing evidence from the fresh case. | 0.385 s / 0.038 s | 83.222 s; verified, 17 media artifacts and 6 preparation receipts | Not run after the fresh Resolve timeout established the runner blocker. |
| One-row change | One approved row generated and normalized in 15.252 s; the unchanged row was reused. | Edited row measured in 10.935 s; evidence verified with zero sample correction. Reserved estimate: $0.011575; actual billing is unconfirmed. | 0.334 s / 0.026 s, including one recompile to align the longer timeline duration | 75.183 s; verified, 17 media artifacts and 6 preparation receipts | Not run after the fresh Resolve timeout established the runner blocker. |

The first Inworld attempt used the older verifier: row 1 was refused at 0.895 correlation (below the 0.900 threshold), row 2 was refused because its estimated correction was -7 samples, and compilation then reported STALE_ANCHOR for five events. No marks were shifted or clamped. The retained assets were remeasured after #301; the accepted evidence now uses the qualified 48 kHz transform with zero sample correction.

The timing verifier now accepts both retained fresh rows and the edited row. That clears the earlier alignment refusal. The remaining blocker is the Studio invocation: both fresh attempts returned at the 60-second call limit with only start evidence. A previous successful #300 Studio proof took 72.93 seconds end to end, longer than that call limit. The failed disposable targets are retained; no result claims they passed.

The provider-stage observations came from the earlier fresh-miss attempt; the accepted timing evidence and compile/package stages were measured after the #301 repair. This is a resumed measurement, not one continuous stopwatch run. Across prior current Inworld reservations and the authorized edited-row call, the cumulative reservation is estimated at $0.174535 against the existing $5 allowance; actual account billing is unconfirmed.

Follow-up #302 tracks a supported way to wait for or resume the guarded Resolve workflow beyond the 60-second call limit. #275 remains open and Blocked until a fresh disposable target completes save/reopen verification.

## Historical Fish attempt (2026-10-23): input and machine

The accepted short #145 segment was 1,019 frames at 24,000/1,001 fps, about 42.5 seconds. It contains two active narration rows with 102 frozen words total, three visual-only blocks, six prepared-media records and six occurrence resolutions. Narration timing maps were absent at the start. The accepted package's prepared-media records were reused; no fresh media preparation completed, so that stage's cold time is unmeasured.

The machine was a MacBookPro16,1 (Intel x86_64). DaVinci Resolve Studio 21.1.1 was installed but not opened for these attempts. No competing media workload ran during the timed provider commands.

Fish credential resolution succeeded with `FISH_AUDIO_API_KEY` unset by reading the key from this Mac's Keychain. The key is not stored in the repository.

## Historical Fish timed cases

These are narration generation/normalization command times, not build turnaround times. The command did not expose separate synthesis and alignment timings.

| Case | Observed provider-stage time | Cache state and result |
| --- | ---: | --- |
| Fresh narration | 20.642 s for the targeted repeat; initial-attempt time unavailable | Two rows generated on the repeat. The initial attempt returned one ready row and rejected one because Fish's apostrophe differed from the authored text. The repeat returned both rows, but one row had two word marks at the same start sample. |
| Unchanged rebuild | 0.866 s | Both narration rows reused cached synthesis and normalization. The cached timing still had the collapsed start. |
| One-row edit | 15.055 s | One changed row generated and the unchanged row reused. The command completed, but no valid timeline was produced or reopened in Resolve. |

The edited case's provider preflight took 0.607 s and reported a $0 estimate under the configured $0 cap. That preflight time is separate from the provider-command time above. The provider-stage times are one observation per case; the fresh case also had the single targeted repeat described above. These observations are not production percentiles.

## Historical Fish failure

The v2 fresh result was rejected by the existing compiler with `COLLAPSED_BOUNDARY`, and the changed narration durations made the existing preparation dependencies stale (`PREPARATION_HASH_MISMATCH`). The existing #182 measurement path also refused Fish's 44.1 kHz raw PCM: it required a whole-kHz input rate and an integer mapping to 48 kHz. The retained provider marks include a genuinely repeated start sample, which must remain a refusal rather than being shifted to make a timeline compile.

The adapter now fails closed on non-increasing native word starts. The cached v2 outputs were retained locally; no private narration, media, identifiers, hashes or local paths are included here. No package passed the runtime checks, and Resolve assembly, save/reopen and optional rendering were not measured.

## What the historical Fish timings can predict

Among the measured stages, Fish generation/normalization dominated an unchanged narration-cache hit: about 15–21 seconds versus 0.866 seconds for two cached rows. End-to-end bottlenecks remain unknown because media preparation, compilation, packaging and Resolve were not reached. This short segment cannot support a reliable 5–10-minute estimate, so none is offered. The numbers describe VERA's current headless route, not a future frontend experience.

Credential setup, adapter debugging, review and this report are one-off work and are excluded from the provider-stage measurements. No human Resolve operation occurred.

## Follow-up

The Fish sample-rate and distinct-native-start repair is complete in [#285](https://github.com/mbelinkie/vera-script-to-timeline/issues/285). The Inworld sample-alignment repair is complete in [#297](https://github.com/mbelinkie/vera-script-to-timeline/issues/297). The Resolve long-running invocation blocker is tracked in [#302](https://github.com/mbelinkie/vera-script-to-timeline/issues/302); #275 remains open until the actual Studio save/reopen path succeeds.
