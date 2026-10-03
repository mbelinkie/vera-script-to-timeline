# Task ID #149 — completed-row reviewer note

Bounded read-only review of `w1-result.md`, `w3-result.md`, `w4-result.md`,
the retained raw dispatch/evidence bindings, `docs/investigations/issue-149/README.md`,
and `verdict-review.md`, against the Issue #141 new-result protocol in
`issue-141/second-opinion-handoff.md` (two stable reads, exact IDs and geometry,
pre-dispatch journal, complete post-state, hashes, output binding, and limits).

## Substantive corrections

1. **W1 attribution typo.** In `w1-result.md`’s three “Native request identities” bullets, the picture-only and disabled-A1 bullets repeat “linked-cut adverse request retains `post-partial.json`.” That adverse checkpoint belongs only to `w1-subtitle-request-linked-cut-01`; the other two bullets need case-specific wording.

2. **W1 physical geometry.** The record gives exact source/record ranges for the linked cut and says the picture-only case has “same intentional cut semantics,” but does not state the picture-only post-snapshot ranges explicitly. Retain the concrete geometry for both cut cases: source `[0,99]` then `[150,399]`, record `[0,99]` then `[100,349]`, one black frame at 99 and black tail 349–398. This prevents a generic 399-frame checker from being mistaken for a continuous picture result.

3. **Raw evidence attribution.** W1 lists request-result, analysis, and checker hashes but not the request/poll journals, complete pre/post pair hashes, or terminal poll/result hashes. W4 likewise lists action, OTIO, render, and aggregate-analysis hashes but not its raw pair/journal/terminal hashes. The files are retained, but the new-result record should bind those exact files explicitly as W3 does.

4. **Scope, not global capability.** README row 4’s “mapping mute effective here” is an older Console observation. Current W3 is adverse: A2 mapping readback changed only `track_mapping.1.mute`, while PCM and all eight number words stayed identical. Keep both runs as context-bound results; do not claim mapping mute globally works or fails. `verdict-review.md` row 4 correctly labels this a material conflict.

5. **Embedded versus separate audio.** README row 7’s “linked audio follows” is too broad. W4 shows following only for embedded AV occurrences sharing one MPI; the separately sourced linked A1 remained 100% while V1 retimed. `verdict-review.md` row 7 has the safer discriminator and should be the controlling wording.

6. **Verdict row 11.** `verdict-review.md` correctly notes raw `p7-001-aba-signals.json` has `lmt:null`; therefore README’s claim that `SM_Project.LastModTimeInSecs` advances is unsupported by retained evidence. Limit the freshness claim to observed `Project.db` mtime (and retain page/timeline-switch false positives).

No correction is indicated for W3’s explicit Deliver-page context or W4’s measured embedded/separate distinction. No W6 file was read or changed beyond avoiding it; no native operation or broad test was run.
