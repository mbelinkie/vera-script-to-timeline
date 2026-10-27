# #341 — paired stage-direction editing handoff

## Delivered contract

`applyStageDirectionEditV2` provides `make_stage_direction`, `make_spoken` and
`delete_direction_delimiter` for narration rows in the active draft or Stash.
Commands use UTF-16 offsets aligned to whole frozen tokens. A successful edit
returns an atomic row-snapshot Undo; stale versions and invalid selections
leave the input document unchanged. Undo also refuses atomically if any part of
the row changed after the edit, including a later visual-boundary edit.

Make Direction brackets only the selected spoken range and marks only those
tokens `spoken: false`. A complete existing pair, including a pasted pair, is
classified only when the caller explicitly selects the whole pair and invokes
Make Direction. Make Spoken removes one whole recognized pair; deleting either
recognized delimiter removes both. Brackets elsewhere, parentheses and quotes
do not trigger automatic classification. Incomplete, nested, malformed and
partial-pair selections refuse without changing the document. General typing
and paste-event handling is not implemented; callers submit the bounded edit
commands.

## Regression evidence

The TypeScript tests cover paired edits, both delimiter deletions, stable
references, save/reload and Undo, spoken-only Prompter/projection, stale timing
rejection, a fresh spoken-token timing map and direction-only duration refusal.
The Python tests exercise provider masking, spoken-only timing/measurement
projection and direction-only refusal before synthesis or timing evidence.
These are contract and service checks; they do not establish a finished editor
or Resolve interaction.

## Consumer behavior and limits

Prompter, projection, timing evidence, compilation and narration measurement
consume only spoken tokens. Classification always changes the row revision.
Wrapping or unwrapping changes the text hash; explicitly classifying an
existing pasted pair leaves text and hash unchanged. In either case the row
revision and spoken-token projection checks make old timing evidence stale.
Replacement maps must match the current spoken-token IDs and offsets.
Direction-only text supplies no narration audio or fabricated zero duration.
The compiler must obtain duration from an independently supported route; if
none is available, it refuses with `NARRATION_DURATION_UNKNOWN`.

This API does not convert `NoteDraftBlock` rows or implement a typing/paste UI.
The #340 note-conversion path must create nonspoken direction content
explicitly, without inferring that other bracketed text is speech. #341 adds no
durable origin-return eligibility: when #340 adds that metadata, authored text
or intent edits through this API must clear eligibility, and exact Undo must
restore the prior eligibility.
