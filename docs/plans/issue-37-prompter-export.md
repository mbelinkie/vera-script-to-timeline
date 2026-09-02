# Issue 37 — deterministic prompter implementation and verification

## Scope and authority

Implement only [issue #37](https://github.com/mbelinkie/vera-script-to-timeline/issues/37)
from baseline `cf53ceba957af21f026b8c2bca1a8eee0be842f3`, in task
`01a06279-3921-7893-87e0-9dd333f38ba1` on
`codex/issue-37-prompter-export`, routed to `gpt-5.6-sol/xhigh`.
The gate was Ready, unclaimed, with no dependencies before the successful claim.
The [approved contract note](issue-37-prompter-contract-change-note.md), product
specification §6.5, and the Producer's mixed-sentence clarification govern.

The additions are optional narration annotations and performance beats, the
separate `prompter-export/v1` schema, generated TS/Python types, pure TypeScript
export/validation, a local CLI, and fictional slice-owned fixtures/tests.
No UI, browser, synthesis/provider/SSML, collaboration, shoot, transcription,
Resolve, private production script, database, or deployment work is included.

## Dependencies

None. No package dependency or lockfile change is required: existing AJV,
schema generators, TypeScript/Vitest, and Node crypto/filesystem APIs suffice.

## Contracts and compatibility

- Only the approved optional arrays and their definitions are added to the
  existing ScriptDocument schema. Existing field requirements do not change.
- `prompter-export-v1.schema.json` is a new derived artifact contract, not
  stored data in ScriptDocument. TS aggregate and Python exports are regenerated.
- No stored-data migration: omitted arrays behave as empty arrays. A missing
  or empty beat array derives beats for this export, without rewriting input.
- The source `DocumentReference` copies the document ID, project ID, live-head
  sequence, and supplied content hash; it does not calculate or rewrite the
  collaboration-owned `liveContentHash`. Fixture source hashes are fictional
  identity evidence. Artifact hashes are independently calculated from bytes.
- Previously accepted schemas other than ScriptDocument, fixtures, goldens,
  tests, and lockfiles stay byte-identical. All new tests/data are slice-owned.

## Deterministic output rules and judgment calls

1. Traverse `activeDraft.blocks` in array order. Only active narration is
   spoken; section titles become navigation only when enabled. Direction,
   visual and note/draft content, narration notes, and excluded narration do
   not enter either the spoken prose or beat text. Trailing headings with no
   following active narration have no beat to annotate and are omitted.
2. Preserve prose wording, punctuation, interior spacing and authored line
   breaks. Insert initial/change `(OC)`/`(VO)` lines at affected token starts,
   keeping adjacent opening punctuation with its word. At an inserted cue,
   separating spaces/tabs become a line boundary; trailing block whitespace
   is removed. Narration blocks are separated by a blank line; nonempty output
   has one final LF. Exporting no active narration returns empty text/no beats,
   without inventing a camera state.
3. Explicit beats preserve authored UUIDs and token ranges. Otherwise the
   frozen token-aligned sentence rule ends at `. ! ? 。 ！ ？`, with optional
   closing quotes/brackets, whether punctuation is inside or outside tokens.
   Decimal points between digit tokens, the titles/abbreviations
   `Mr Mrs Ms Dr Prof Sr Jr St vs etc e.g i.e`, and uppercase single-letter
   initials do not end a beat. The final token always ends a beat. This rule
   is independent of locale, ICU, provider, and time. It is a deterministic
   default, not general linguistic inference; tokens are atomic, and authors
   can supply explicit merged/split beats for other editorial boundaries.
4. UUIDv5 namespace `a540f252-f01d-5f07-b6a4-88d6f8a02a58` receives UTF-8
   `documentId`, decimal live-head sequence, block ID, first and last covered
   token IDs, joined by NUL. Explicit/derived IDs must be globally distinct
   as UUIDs, including case-equivalent spellings. A live-head sequence beyond
   JavaScript's exactly representable integer range blocks export.
5. Per the Producer clarification, a beat containing any OC token is one
   `on_camera` recording beat, even if some words are covered by B-roll. Only
   an entirely VO beat is `voiceover`. This never replaces the word-level
   visibility markers in the text. Beat boundaries alone never split visible
   prose; optional `[BEAT n]` lines use 1-based document order.
6. Beat `expectedText` uses the exact authored slice with its punctuation,
   excluding surrounding separator whitespace. Navigation attaches to the
   first beat after a section. Annotations retain source array order and
   appear in every beat whose token range they intersect. A visible cue occurs
   once, at the annotation's start token. Shared ranges are permitted.
7. Visible annotations use `[PRONUNCIATION: text = value]`,
   `[PHONEME: text = value]`, or `[PERFORMANCE: value]` lines. Backslashes,
   closing brackets, control/format characters, and Unicode line separators
   are escaped to prevent cue content becoming a spoken line. The sidecar
   retains the original typed value, including opted-out annotations marked
   `visibleInPrompter: false`. Values are metadata only, never executed.
8. The two export settings must be explicit booleans in the pure API; the CLI
   defaults both to false. Annotation inclusion is the authored required
   boolean, not a mutation-time validator default. A future authoring UI can
   default newly created annotations on under D24-14.
9. Sidecar JSON recursively sorts object keys by code-unit order, preserves
   arrays, uses two-space indentation and a final LF. SHA-256 covers exact
   UTF-8 text bytes; the CLI separately reports the sidecar's SHA-256.

## Validation and local output safety

The existing ScriptDocument structural/semantic validation remains the gate,
including token/anchor integrity, visibility and VO visual-coverage checks.
The new entities reuse that anchor resolver and diagnostics. Invalid owner,
missing/reversed/empty token ranges, quoted-text disagreement, annotation
identity/visibility errors, and beat identity/order/overlap/coverage errors
block export. No repair or retargeting occurs. Arrays absent in accepted
documents add no new semantic errors.

The CLI requires distinct input/text/sidecar paths and existing destination
directories. It preflights both outputs and creates each exclusively (`wx`),
never overwriting files or following an output symlink. A validation failure
writes nothing. A race or I/O failure after the first creation is reported as
an incomplete export; any newly created partial artifact is retained, and no
success or complete-export claim is made. Use fresh paths for another export.

## Automated acceptance checklist

The Project's authority is `Automated`; no duplicate producer approval, manual
listening, UI check, or Resolve check is required.

- [x] Pinned Node/npm and frozen Python dependencies recorded.
- [x] Full `rtk npm run validate` succeeds twice on the final implementation,
  including current generated contracts, lint, typecheck, accepted suites,
  and new prompter/schema/CLI/Python type tests.
- [x] Run the real CLI twice on each fictional input, compare both artifact
  bytes to each other and to its goldens, and verify hashes independently.
- [x] Missing camera range blocks the real CLI with stable diagnostics and
  no artifacts. Retain the failing copy and diagnostics as evidence.
- [x] Audit baseline frozen paths and lockfiles; record legacy input hashes.
- [x] Retain exact commands, results, versions, hashes and walkthrough; prepare
  #37's In review handoff without dispatching or implementing another issue.

## Walkthrough

The acceptance fixture reads “Watch the beacon as the fog rolls in.” as a
single recording beat. The prompter switches to VO before “as” while that beat
remains OC in the sidecar, matching a presenter performing the whole sentence
and an editor later covering its second half. The next OC sentence is its own
explicit beat; the closing VO sentence gets a deterministic derived ID.
The alias is visibly non-spoken, the phoneme annotation stays sidecar-only,
and the performance cue appears at the next sentence. The legacy fixture has
no new arrays and derives all three sentence beats without changing its source.
