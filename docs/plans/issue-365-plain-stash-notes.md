# #365 — Plain Stash notes: public commands, persistence, Sorting, and limits

This is the bounded **domain implementation** for #365, consumed by #125. It is not a production typing UI or a textual script exporter. The sole content field is `NarrationBlockV2.text`: exact user characters, **no injected outer `[` / `]`, escaping, trimming, normalization, or inferred speech**. Literal nested, unmatched, quoted, Unicode, pasted multiline, and zero-length notes are allowed.

## Public authoring commands and serialized representation

Use `@vera/contracts/authoring-v2` (`applyRowEditV2`, `createRowEditSessionV2`, `serializeAuthoringDocumentV2`, `deserializeAuthoringDocumentV2`, `createSortingTrialV2`, `resumeSortingTrialV2`). `applyRowEditV2(document, expectedRowEditRevision, command)` is immutable: success increments `rowEditRevision`; refusal returns the caller's document unchanged. The caller supplies **stable UUIDs and text-exact UTF-16 token offsets**, including during Sorting replay. There are no random IDs or automatic text tokenization in this API.

Example complete creation command (one token deliberately spans the entire eleven-character input):

```json
{
  "kind": "create_stash_note",
  "bundleId": "00000000-0000-4000-8000-000000001f40",
  "sectionId": null,
  "parentRowId": null,
  "afterRowId": null,
  "row": {
    "id": "00000000-0000-4000-8000-000000001f41",
    "type": "narration",
    "orderKey": "1",
    "text": "[literal] ]",
    "tokens": [
      {
        "id": "00000000-0000-4000-8000-000000001f42",
        "value": "[literal] ]",
        "startOffset": 0,
        "endOffset": 11
      }
    ],
    "primaryVisualSequence": {
      "id": "00000000-0000-4000-8000-000000001f43",
      "version": 1,
      "slots": [
        {
          "id": "00000000-0000-4000-8000-000000001f44",
          "kind": "content",
          "relation": { "kind": "base" },
          "boundaryBefore": { "kind": "row_start" },
          "payload": { "kind": "on_camera", "presenterChoiceId": null },
          "playoutPolicy": "match_structural_interval",
          "version": 1
        }
      ]
    },
    "overlayEvents": [],
    "timingPolicy": "narration_spine",
    "state": "active",
    "notes": [],
    "version": 1
  }
}
```

Omitting `mode` (or providing `"mode":"default_direction"`) creates `stashOutline` kind `"note"` and freezes the same row with `"plainDirection":true`; **each present token receives `"spoken":false`** and its exact `text`, `value`, offsets and token IDs remain unchanged. The **saved row** therefore includes this fragment, *not bracket-delimited metadata*:

```json
{
  "type": "narration",
  "text": "[literal] ]",
  "plainDirection": true,
  "tokens": [{ "value": "[literal] ]", "startOffset": 0, "endOffset": 11, "spoken": false }]
}
```

This is a **field excerpt**, not a complete row; real persisted JSON includes required IDs, visual/timing fields, and the Stash bundle/outline. For an empty plain note only, `text:""` with `tokens:[]` is valid. Unflagged narration still requires nonempty text and tokens. An explicit `"mode":"authored"` keeps the caller's complete legacy authored narration representation; it does not automatically classify brackets or add the new flag. Existing valid old documents are read unchanged, not migrated or rewritten.

The other public row commands have these exact fields:

```json
{ "kind": "place_stash_rows", "rowIds": ["<saved-row-id>"], "destination": { "sectionId": null, "afterRowId": "<active-row-id>", "beforeRowId": null } }
{ "kind": "stash_rows", "rowIds": ["<placed-row-id>"], "bundleId": "<fresh-bundle-id>" }
{ "kind": "edit_row", "rowId": "<existing-row-id>", "row": { "...": "complete schema-valid replacement row with same id/type and updated version" } }
{ "kind": "make_spoken", "blockId": "<narration-row-id>", "startOffset": 0, "endOffset": 11 }
{ "kind": "make_stage_direction", "blockId": "<narration-row-id>", "startOffset": 0, "endOffset": 11 }
```

The angle-bracket strings and `row` placeholder above are *notation*, not executable UUIDs or a valid replacement row. The gaps must identify current exact positions, and `rowIds` for compact placement must identify complete selected Stash outline branches. `create_stash_note` accepts `bundleId`, `row`, `sectionId`, `parentRowId`, `afterRowId`, and optional `mode`—nothing else.

For a placed `plainDirection:true` row, **whole-row** `make_spoken` deletes that flag and its `spoken:false` token markers; subsequent whole-row `make_stage_direction` on the converted note re-adds them. Both leave characters, token IDs, token values, and offsets untouched and mark the placed Stash origin as authored (`returnEligible:false`). An ordinary `edit_row` can replace the complete text and correctly frozen tokens but cannot silently toggle `plainDirection`; use the explicit stage commands. Whole-row conversion is unavailable for an empty note (no speech token to select). Partial selection, corrupt flags/offsets and literal-bracket delimiter deletion refuse. For *legacy* recognized bracket pairs, #341's token-aligned stage edits and paired-delimiter shortcut retain their original semantics. They do not fire on literal brackets inside a flagged plain note.

An untouched placed note retains `stashOrigin` (kind, section, parent/sibling anchors, `returnEligible:true`) and can return as the **same exact raw note** with `stash_rows`. Edited notes lose compact return eligibility until exact Undo. `createRowEditSessionV2` / Sorting trial Undo restores the entire prior row, content, versions, and eligibility snapshot.

## Sorting trial outcomes and recovery

`createSortingTrialV2(baseline)` holds a private session, not the canonical document. Apply supported public row commands with `trial.apply(command[, expectedRevision])`; `trial.preview()` makes the trial read-only; `trial.returnToSorting()` re-enables edits. `trial.serialize()` produces `{"format":"sorting-trial/v1","baseline":<complete-script-document>,"actions":[<public-commands-or-undo>],"phase":"sorting"|"preview"}`. `resumeSortingTrialV2(json)` validates baseline JSON and replays commands/Undo, restoring projection provenance and phase; no guessed note parsing, IDs, or intent.

If a default plain note is placed, made spoken, edited, and reordered in the trial:

| Outcome | Placement | Text and semantic intent | Stash kind / return |
|---|---|---|---|
| `accept(baseline,"all")` | Trial placement/order | Edited text, spoken if explicitly converted | Placed edited origin, not eligible for untouched compact return |
| `accept(baseline,"edits_only")` | Original saved location | Edited text and explicit spoken classification | Ordinary saved `"row"`, not compact `"note"` |
| `accept(baseline,"sorting_only")` | Trial placement/order | **Baseline exact text** and `plainDirection:true` | Original `"note"` provenance, `returnEligible:true`; can return untouched |
| `discard(baseline)` | Original | Original text, token flags, IDs, provenance | Canonical document unchanged |

Selective outputs compose by stable row ID and immutable birth/tombstone/slot snapshots, not by textual bracket heuristics. A successful changed acceptance increments the canonical revision **once**. Any failed acceptance leaves the trial pending and the supplied canonical untouched. Accept refuses a changed canonical baseline; invalid exact gaps, reused IDs, missing outline parents, broken supporting-item routing, row audio fences, malformed action history, and stale revisions refuse atomically. A saved trial is bounded to **1,000 accepted non-Undo edits**, **2,000 serialized action entries**, and **5,000,000 JSON characters**; neither the UI nor recovery may treat this as an unlimited durable collaboration log.

## Export and consumer contract

- **Canonical authoring JSON:** `serializeAuthoringDocumentV2` preserves literal `NarrationBlockV2.text`, `plainDirection:true`, all exact UTF-16 tokens and `stashOutline.kind`. No duplicate compact text, invisible delimiter wrapper, or general-purpose script-text exporter exists. Deserialize refuses malformed semantic metadata, including on parked Stash rows.
- **Prompter `exportPrompter`:** reads active Draft only. Saved Stash content and active whole-row plain directions have **no plaintext line and no sidecar beat/entry**. Explicitly converted spoken text (including literal brackets) is exported normally. In old mixed narration, only independent, recognized semantic `[direction]` runs are removed from spoken export.
- **Python narration and build stage:** pure semantic frozen-token filtering and UTF-16-width masking avoid provider requests, billing planning, or speech synthesis for empty/nonspoken direction-only rows. No phrase/punctuation classifier is involved; malformed intent is refused, not treated as speech.
- **Timeline compiler / media needs:** the note contributes no invented narration recording, duration, or visual timeline length. A placed direction-only row without an independently verified duration still refuses with `NARRATION_DURATION_UNKNOWN`; dependent media-needs timing can report `STALE_TIMING_MAP`. This is a deliberate unresolved duration policy, **not** evidence of generated speech. Old mixed narration behavior and compiler goldens stay unchanged.

## Verification and scope

Phase-4 focus: `sorting-content-v2.test.ts` (four outcomes, preview/Return, semantic conversion, exact Undo), `sorting-recovery-v2.test.ts` (empty/multiline, serialize/replay, origin, stale/corrupt/cross-row refusal), `sorting-edit-invariants-v2.test.ts` (deterministic mixed editing/order permutations), plus old `stash-outline-v2.test.ts` and `authoring-v2-schema.test.ts` snapshots. Phase 5 owns the full `npm run validate:fast` gate, mutation checks and independent review; CI owns the full validation on the PR head.

Not provided: production keystroke/selection editor, arbitrary mixed token slicing, a render-only outer bracket display, generic script-text exporter, audio provider/Resolve integration, source-anchor repairs, attachment splits, or a duration policy for active direction-only rows. #125 consumes these domain commands; downstream UI/research owners remain separate.
