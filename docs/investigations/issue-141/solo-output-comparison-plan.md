# Issue 141 — A2 Solo output comparison

This is a local comparison plan for the already-owned, full-Matrix MOV job in
`fairlight-queue-only-summary.json`. It does not queue, start, inspect, or
recover a Resolve job. Read the MOV only after the job has a retained successful
terminal status and its completed-output handoff identifies the exact owned
path and hash. Do not inspect partial output.

## Bound evidence

The pinned fresh full Matrix pair is
`out/issue-141-observation-20260930-01a0f318/editorial-context-20261002T031927.605476Z/pair.json`
(SHA-256 `d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14`).
The queue-only record binds that pair as the checkpoint and retains equal
before/after pairs for job `a6ed7f33-9ad4-4d82-bfac-ff72903f4567`. The job
requests full Matrix MOV/H.264 plus Linear PCM 24-bit audio at 48 kHz. The
operator record says A2 Solo is on; Solo is an operator-held UI state and is
not present in the API pair. Output/bus labels were not visible, so route and
bus origin remain unknown.

After successful terminal proof, extract the first audio stream to a new WAV
inside the job's owned evidence directory, preserving PCM24/48 kHz. Verify the
extracted stream with `ffprobe` and retain its byte count and hash. Then use the
existing `program-pcm-check.py` against the exact fresh pair and generated
`repeated.wav`. Its result is waveform correlation/support only. It reads the
full output PCM and reports all enabled repeated-source occurrences; it does
not establish routing, audibility, or Solo state. Keep the raw MOV, extracted
WAV, comparator result, and handoff references together. Do not compare the
Solo output to the baseline under an assumption of byte equality outside the
target region.

## Verified control windows

The pair uses 25 fps and 48 kHz, or 1,920 samples per frame. Frame intervals
below are half-open. The track and item values below are from the exact pinned
pair, not from UI track labels alone.

| Purpose | Matrix interval | Verified item state | Sample interval / interpretation |
|---|---:|---|---|
| A1-only speech control | `[2250,2449)` | A1 enabled, item `a9175c87-6bc0-4c07-a167-3b7c9de70fba`, source `repeated.wav`, source frames `[0,199)`; no A2 item or A3 bed item overlaps. | The first repeated-word support `[19210,36258)` maps to output samples `[4339210,4356258)`. Compare its correlation to the generated repeated source. |
| A2 speech-specific window | `[4560,4570)` | A2 target `f4e9f649-894a-42f2-9f54-a8321ae7c163` is enabled over `[4500,4699)`; A1 has a gap over this speech support; A3 bed is enabled over `[4500,4699)`. | The second repeated-word support `[115210,132258)` maps to `[8755210,8772258)`. This is A2 speech over the bed, not an A2-only bus observation. |
| A3-only control | `[4065,4070)` | A3 bed item `050ec572-54d8-4025-a1c7-0e625766245a` is enabled over `[4000,4199)`; A1's adjacent items end at 4065 and resume at 4070; the A2 item over this section is disabled. | Inspect only output samples `[7804800,7814400)` for signal energy. This is an A3-only track-activity control; it does not identify output bus or prove route. The repeated-source comparator cannot correlate `bed.wav`. |

The whole-program comparison means analyze all retained enabled repeated-source
support across the rendered timeline with the existing comparator, then report
the three bounded control windows separately. Do not demand equality with the
baseline outside `[4500,4699)`: the API pair cannot expose Solo, bus, or routing
state, and a difference elsewhere is an observation requiring interpretation,
not automatically a failure. Preserve any unsupported or ambiguous metrics as
such.

## Minimal extraction and report fields

Do this only after terminal success has been handed off:

1. Confirm the job ID and successful terminal status from retained Resolve
   evidence; require the MOV path to equal the owned path in the handoff.
2. Extract audio stream `0:a:0` to a new PCM24, 48 kHz WAV in the owned evidence
   directory. Retain the extraction invocation, `ffprobe` summary, WAV size,
   and SHA-256. No source or presenter media is needed for extraction.
3. Run `program-pcm-check.py` on generated `repeated.wav`, the extracted WAV,
   and the exact pair/hash above. Retain all per-item results; tag the document
   and result wrapper as **A2 Solo operator-reported**, without altering the
   comparator's waveform-only labels.
4. For the A3-only control, report per-channel RMS/peak only within
   `[7804800,7814400)` from the extracted PCM; if a generated `bed.wav`
   correlation is later added, bind it to the pinned media hash and exact
   source range. Do not label simple energy as bed-source correlation.
5. Include the operator's Solo/Mute labels, the fact that bus labels were
   unavailable, and an explicit `routing: unknown` in the comparison record.

## Current status

The pair and source pins are verified, and the queue-only result already binds
one owned queued job. This plan contributes no render result. All render-derived
fields remain pending successful terminal handoff; no output bytes were opened
for this preparation.
