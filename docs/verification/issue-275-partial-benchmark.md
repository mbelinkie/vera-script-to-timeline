# Issue 275: partial benchmark result

**Status:** blocked; no end-to-end turnaround result is available. This report records the measured provider-stage attempts and the reason the build stopped. It does not claim a successful fresh build, cache rebuild, or one-row edit.

## Input and machine

The accepted short #145 segment is 1,019 frames at 24,000/1,001 fps, about 42.5 seconds. It contains two active narration rows with 102 frozen words total, three visual-only blocks, six prepared-media records, and six occurrence resolutions. Narration timing maps were absent at the start. The accepted package's prepared-media records were reused; no fresh media preparation completed, so that stage's cold time is unmeasured.

The machine was a MacBookPro16,1 (Intel x86_64). DaVinci Resolve Studio 21.1.1 was installed but not opened for these attempts. No competing media workload ran during the timed provider commands.

Fish credential resolution succeeded with `FISH_AUDIO_API_KEY` unset by reading the key from this Mac's Keychain. The key is not stored in the repository.

## Timed cases

These are narration generation/normalization command times, not build turnaround times. The command did not expose separate synthesis and alignment timings.

| Case | Observed provider-stage time | Cache state and result |
| --- | ---: | --- |
| Fresh narration | 20.642 s for the targeted repeat; initial-attempt time unavailable | Two rows generated on the repeat. The initial attempt returned one ready row and rejected one because Fish's apostrophe differed from the authored text. The repeat returned both rows, but one row had two word marks at the same start sample. |
| Unchanged rebuild | 0.866 s | Both narration rows reused cached synthesis and normalization. The cached timing still had the collapsed start. |
| One-row edit | 15.055 s | One changed row generated and the unchanged row reused. The command completed, but no valid timeline was produced or reopened in Resolve. |

The edited case's provider preflight took 0.607 s and reported a $0 estimate under the configured $0 cap. That preflight time is separate from the provider-command time above. The provider-stage times are one observation per case; the fresh case also had the single targeted repeat described above. These observations are not production percentiles.

## Why the benchmark stopped

The v2 fresh result was rejected by the existing compiler with `COLLAPSED_BOUNDARY`, and the changed narration durations made the existing preparation dependencies stale (`PREPARATION_HASH_MISMATCH`). The existing #182 measurement path also refuses Fish's 44.1 kHz raw PCM: it requires a whole-kHz input rate and an integer mapping to 48 kHz. The retained provider marks include a genuinely repeated start sample, which must remain a refusal rather than being shifted to make a timeline compile.

The adapter now fails closed on non-increasing native word starts. The cached v2 outputs were retained locally; no private narration, media, identifiers, hashes, or local paths are included here. No package passed the runtime checks, and Resolve assembly, save/reopen, and optional rendering were not measured.

## What these timings can predict

Among the measured stages, Fish generation/normalization dominated an unchanged narration-cache hit: about 15–21 seconds versus 0.866 seconds for two cached rows. End-to-end bottlenecks remain unknown because media preparation, compilation, packaging, and Resolve were not reached. This 42.5-second segment cannot support a reliable 5–10-minute estimate, so none is offered. The numbers describe VERA's current headless route, not a future frontend experience.

Credential setup, adapter debugging, review, and this report are one-off work and are excluded from the provider-stage measurements. No human Resolve operation occurred.

## Follow-up

The bounded repair is tracked in [#285](https://github.com/mbelinkie/vera-script-to-timeline/issues/285). Resume #275 only after that work supports exact 44.1 kHz measurement and a fresh run passes the existing checks through save/reopen in Resolve.
