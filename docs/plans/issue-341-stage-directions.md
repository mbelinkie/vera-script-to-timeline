# #341 — paired stage-direction editing handoff

## Delivered contract

`applyStageDirectionEditV2` provides `make_stage_direction`, `make_spoken` and
`delete_direction_delimiter` for narration rows in the active draft or Stash.
Commands use UTF-16 offsets aligned to whole frozen tokens. A successful edit
returns an atomic row-snapshot Undo; stale versions and invalid selections
leave the input document unchanged.

Make Direction brackets only the selected spoken range and marks only those
tokens `spoken: false`. A complete existing pair, including a pasted pair, is
classified only when the caller explicitly selects the whole pair and invokes
Make Direction. Make Spoken removes one whole recognized pair; deleting either
recognized delimiter removes both. Brackets elsewhere, parentheses and quotes
do not trigger automatic classification. Incomplete, nested, malformed and
partial-pair selections refuse without changing the document. General typing
and paste-event handling is not implemented; callers submit the bounded edit
commands.

## Consumer behavior and limits

Prompter, projection, timing evidence, compilation and narration measurement
consume only spoken tokens. Classification changes the row revision and text
hash, so old timing evidence is stale; replacement maps must match the current
spoken-token IDs and offsets. Direction-only text supplies no narration audio
or fabricated zero duration. The compiler must obtain duration from an
independently supported route; if none is available, it refuses with
`NARRATION_DURATION_UNKNOWN`.

This API does not convert `NoteDraftBlock` rows or implement a typing/paste UI.
The #340 note-conversion path must create nonspoken direction content
explicitly, without inferring that other bracketed text is speech. #341 adds no
durable origin-return eligibility: when #340 adds that metadata, authored text
or intent edits through this API must clear eligibility, and exact Undo must
restore the prior eligibility.
