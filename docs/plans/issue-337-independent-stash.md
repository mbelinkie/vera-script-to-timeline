# #337 — independent Stash restore and sections: supported-limit handoff

## Persisted model

`ScriptDocumentV2.stash` remains the source of saved rows and their supporting
items. The additive, optional `stashSections` field stores flat headings as
`{ id, title, rowIds }`. Section membership refers to rows already saved in
Stash; it does not copy or wrap row content. Stashing a row does not create a
section. Empty sections remain after their last row is restored, and older
documents without `stashSections` remain valid.

The normal document serializer persists this metadata. Validation requires
unique section IDs, existing saved-row IDs, and at most one section per row.
Stash row IDs and section metadata share the document's existing identity and
reference checks.

## Public operations

All operations go through `applyRowEditV2(document, expectedRevision,
command)` in `@vera/contracts/authoring-v2`:

- `restore_stash_rows` restores an explicit set of saved row IDs to an exact
  current Draft gap. A selection can span saved bundles; restored rows follow
  visible Stash order. Selected rows leave their prior section membership.
- `create_stash_section` adds an empty section with a caller-supplied ID and
  title.
- `move_stash_rows` assigns selected saved rows to an existing section, or to
  the unsectioned Stash area with `sectionId: null`. It changes organization,
  not row content or bundle storage.

These commands use the existing immutable row-edit transaction, revision
check, local Undo session, and refusal behavior. The original bundle-level
`restore_stash` remains supported. Sorting trials accept these operations and
persist them through the existing serialize/resume flow; trial content edits
remain refused. Acceptance still compares the complete starting document and
installs one complete result, while discard leaves the canonical document
unchanged.

When an independent restore splits a bundle, supporting items move only when
their supported row anchors identify one side unambiguously. Unanchored items
and items spanning selected and still-saved rows refuse atomically with
`ROW_REFERENCE_REVIEW_REQUIRED`. Restores that alter the coverage of an
existing audio span refuse with `AUDIO_REVIEW_REQUIRED`; this issue adds no
audio migration policy. Moving saved rows between Stash sections leaves row
content and row relationships in place.

Timed supporting items include every saved row between their endpoint anchors
in the split check. A duration-ended timed item has no proved row endpoint, so
partial-bundle restoration refuses rather than guessing its coverage.

## Consumer boundary and evidence

Stash headings and saved rows remain outside active Draft consumers until rows
are restored. The executable coverage is in
`packages/contracts/test/row-edits-v2.test.ts`,
`packages/contracts/test/row-edit-consumers-v2.test.ts`, and
`tests/test_row_stash_v2_consumers.py`. These exercise section persistence,
partial restore, local Undo, actual consumer exclusion, and the Python bridge.
The work was also checked with the contracts workspace typecheck. The final
`validate:fast` result is tracked by the parent task/PR rather than asserted
here.

## Supported limits

This proves independent saved-row restore and optional, flat Stash sections.
It does not add nested notes/clips/rows, note-to-row or clip-to-row conversion,
content editing during Sorting, or selective edit/sort acceptance. Those are
separate #340/#342 work. Stash remains a saved-row container; this does not
define broader archival behavior or repair ambiguous attachment anchors.

Resolve assessment: this is a document-state change with no Resolve runtime
delta. No Resolve launch or live application test is required for #337.
