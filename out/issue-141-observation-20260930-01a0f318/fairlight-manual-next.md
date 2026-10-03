# Task ID issue141 — Manual Fairlight Solo/routing step

Status: checklist prepared only. No Resolve, native, UI, render, source, or
project action was performed.

## Evidence pin and guard

Use only project `97037b5a-aab6-48a9-b7e4-4c5697ae10a0`, selected timeline
`VERA 141 Batched Matrix` (`29ae8331-b86e-4041-a548-960695cc7b24`). The exact
held result is
`audio-mapping-mute-20261002T020031.880586Z/result.json` (SHA-256
`c70a29b0dc7efc4245e57f2929750fc64d342f7611a9609dcc7916ccbc864425`). It is
currently `mapping-muted-held-for-output`; `restoredFullPair` is null.

The target is marker `141 R2-residual item 2`, occurrence
`f4e9f649-894a-42f2-9f54-a8321ae7c163`, source `repeated.wav`, Audio 2, locked.
Its original mapping is the exact raw JSON
`{"embedded_audio_channels":1,"linked_audio":{},"track_mapping":{"1":{"channel_idx":[1],"mute":false,"type":"mono"}}}`.
The held pair is `after-muted-full-pair.json` (SHA-256
`a171acbb58b84753b624b316230455e4b59b78a32e55fdcf04c72c3095292cd3`); the
before/original pair is `before-full-pair.json` (SHA-256
`d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14`).

Do not start the manual Solo step until the reviewed render lifecycle has
finished for the held mapping state and the owner has restored the exact
mapping above. Require a new restored full pair equal to the before hash.
Do not replay preparation, unlock Audio 2, alter buses, or change source files.

## Track inventory to record

Record the actual Fairlight view and readbacks before any toggle:

- A1: `Audio 1`, enabled and unlocked; `repeated.wav` speech pieces.
- A2: `Audio 2`, enabled and locked; full `repeated.wav` residual occurrence,
  the target above.
- A3: `Audio 3`, enabled and locked; full `bed.wav` occurrence.

For each, record the displayed track name/number, Mute and Solo indicators,
visible bus/output assignment, sends/effects shown, and whether the program
meter responds. Record the selected timeline, playhead, render queue state,
and the exact restored mapping before toggling. Do not infer a bus assignment
from a missing API getter; capture what Fairlight visibly shows.

## Minimum operator sequence

1. With all Solo controls off and the restored mapping unmuted, record the
   baseline Fairlight state. Reuse the independently reviewed unmuted baseline
   render when its complete state matches the restored pair; do not rerender
   that baseline merely for this check.
2. In Fairlight, toggle Solo on for **A2 only**. Do not touch Mute, gain, pan,
   bus, send, track enable, lock, or clip mapping. Capture the visible Solo
   state, A1/A2/A3 meters and displayed program output, then run the same
   reviewed render lifecycle once.
3. Toggle A2 Solo off and verify every Solo/Mute indicator and displayed route
   matches the baseline. Retain the exact post-toggle state pair and operator
   confirmation of restored mixer indicators; rerender only if new evidence
   or a mismatch makes restoration uncertain.
4. Restore the original selection/playhead and leave the project on the pinned
   timeline. No save or cleanup action is part of this checklist unless the
   reviewed lifecycle explicitly requires it and its final full pair is equal.

## Expected discriminant and classification

When A2 Solo is active, Resolve's observed Solo behavior should leave A2's
program contribution present while suppressing A1/A3 contributions. A changed
meter pattern or rendered PCM window is the discriminant; exact silence is not
assumed because A2 contains the full repeated speech. Solo-off output and UI
state should return to the baseline. If the output is unchanged, record that
fact with the visible indicators and PCM/output hashes; do not label it an API
failure or infer that routing is unavailable.

A missing or inaccessible Fairlight control is a manual availability
observation only. Stop before changing buses or inventing a route. Preserve
any refusal, partial readback, or UI mismatch as evidence and do not retry.
The test closes only the named A2 Solo on/off observation; it does not prove
universal Fairlight routing, arbitrary buses, or all program-audibility cases.
