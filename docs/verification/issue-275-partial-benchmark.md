# Issue 275: script-to-Resolve turnaround results

**Status: all three guarded Resolve runs passed.** Cold media preparation and optional rendering remain unmeasured, so the stage sums below are partial workflow estimates rather than complete cold-build wall times.

## Inworld benchmark (2026-10-24–25)

The selected Inworld TTS-2 / Arthur route ran on a MacBookPro16,1 (Intel) with DaVinci Resolve Studio 21.1.1. The unchanged sample is 1,143 frames at 24,000/1,001 fps (about 47.7 seconds), with two narration rows, 102 words, 11 timeline events and 17 package media artifacts. The one-row edit is 1,149 frames (about 47.9 seconds).

Each case used a fresh attestation, release, request, evidence directory and disposable Resolve target. All three normal v2 deliveries saved and reopened their project, verified 11 events and 11 imported media items, and reported zero discrepancies. No provider call was made during these final Resolve runs. Two earlier attempts through the 60-second caller were retained and excluded; the recoverable parent added by #302 completed these runs. No competing media workload ran during the timed Resolve stages.

Six existing media-preparation receipts were reused from #300; no cold media-preparation duration was recorded for this benchmark. Resolve startup, attestation/release/request preparation, manual authoring and optional review rendering are also excluded.

| Case | Narration generation/cache | Automatic timing | Compile / media-needs | Package build and verification | Resolve delivery (reserve to verified exit) | Sum of measured stages* |
| --- | --- | --- | --- | --- | --- | --- |
| Fresh narration assets | 2.805 s and 6.782 s on the prior fresh-miss run; no new provider calls for this completion. | Retained audio remeasured with networking disabled: 2.976 s and 7.130 s. Both rows passed `qualified_linear_transform` verification with zero sample correction. | 0.353 s / 0.046 s | 74.051 s; verified | 76.667 s; verified, zero discrepancies | About 2 min 51 s |
| Unchanged rebuild | Cache hits: 0.961 s and 0.277 s; no provider calls. | Reused verified timing evidence from the fresh case. | 0.385 s / 0.038 s | 83.222 s; verified | 74.235 s; verified, zero discrepancies | About 2 min 39 s |
| One-row change | Changed row generated and normalized in 15.252 s; unchanged row reused. Reserved estimate: $0.011575; actual billing is unconfirmed. | Changed row measured in 10.935 s and passed verification with zero sample correction. | 0.334 s / 0.026 s, including one recompile to align timeline duration | 75.183 s; verified | 69.033 s; verified, zero discrepancies | About 2 min 51 s |

\* These are sums of recorded stage observations, not continuous stopwatch runs. Narration, timing, compile, package and Resolve stages were captured in separate executions. The sums omit media preparation, so a fully cold end-to-end time is still unknown. These are single observations, not production percentiles, and the roughly 48-second segment does not establish a 5–10-minute estimate for a longer video.

The longest measured stages were package build and verification (74–83 seconds) and the Resolve delivery path (69–77 seconds, including connection, guarded bootstrap, package rechecks, assembly and save/reopen verification). Compilation plus media-needs checks took about 0.36–0.42 seconds. The compiler itself is not the source of the multi-minute sample turnaround. A separate successful #302 run took 250.95 seconds; it is not averaged into these three #275 cases, and no cause for the difference is established.

The retained Inworld spend ledgers reconcile to $0.162960 reserved across #289, #293 and #275, against the existing $5 allowance; actual account billing is unconfirmed. This completion made no provider calls.

The first Inworld attempt used the older verifier: row 1 was refused at 0.895 correlation (below the 0.900 threshold), row 2 was refused because its estimated correction was -7 samples, and compilation then reported STALE_ANCHOR for five events. No marks were shifted or clamped. The retained assets were remeasured after #301; the accepted evidence now uses the qualified 48 kHz transform with zero sample correction.

The timing verifier accepts both retained fresh rows and the edited row. The earlier guarded attempts returned at the 60-second call limit and are excluded from the successful run count. A prior #300 Studio proof took 72.93 seconds; the recoverable parent lets the caller wait for longer operations without retrying or replacing a live target. Failed disposable targets remain retained.

The provider-stage observations came from earlier fresh-miss and edited-row runs; accepted timing evidence and compile/package stages were measured after the #301 repair. This is a resumed measurement, not one continuous stopwatch run.

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

The Fish sample-rate and distinct-native-start repair is complete in [#285](https://github.com/mbelinkie/vera-script-to-timeline/issues/285). The Inworld sample-alignment repair is complete in [#297](https://github.com/mbelinkie/vera-script-to-timeline/issues/297). The recoverable Resolve invocation is implemented in merged [#302](https://github.com/mbelinkie/vera-script-to-timeline/issues/302). #275 can close after this sanitized report merges and its External evidence is recorded.
