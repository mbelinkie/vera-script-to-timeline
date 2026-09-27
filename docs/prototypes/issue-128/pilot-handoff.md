# Issue 128 — S05 successor pilot checkpoint

Status: **Producer-choice checkpoint; issue #128 remains In progress.** This is
not the complete successor export and must not be moved to In review.

## Exact checkpoint

- Pilot: `docs/prototypes/issue-128/s05-outbound-review-pilot.html`
- Pilot SHA-256: `28214ac222be814c5fb2de099739ff0649972f81a1e8469aac928863c0b3b22f`
- Check: `docs/prototypes/issue-128/check.mjs`
- Check SHA-256: `dfa292168e93fb6fc5af29dca64b18a808af3d70116e69d678aa990412120543`
- Evidence: 20 PNGs in `docs/prototypes/issue-128/pilot-evidence/` covering
  10 states at 1280×800 and 1024×768.
- Claude consultation prompt and unedited response are retained beside the
  pilot. Claude did not edit the repository or make product decisions.

## Frozen authority and reuse record

The pilot verifies the accepted #135 S03 source before every evidence run:

- `docs/prototypes/issue-135/S03 v3 authoring artifact - issue 135 export v2.dc.html`
- 3,943,452 bytes
- SHA-256 `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea`

The accepted artifact remains untouched. The pilot imports the frozen shared
row stylesheet that is byte-identical inside that source, copies its exact
ordinary type themes, and privately adapts its row-local ordinal, narration
range, compact card, transparent Graphic, OC and document-wide music-rail
patterns into a read-only renderer. It does not mount or hide the editor and
has no authoring callbacks, persistence, text patching or color inference.

The accepted #123 contribution is limited to comparison grammar: changed
entity precedence, neutral unchanged words, readable deletion evidence,
linked move identity and structural-span treatment. Its inbound decisions and
patched renderer are not reused. The left rail is preserved structurally but
adapted to explicit outbound `Selected`, `Skipped` and `Blocked` states with
one consequence and a result derived from the same selection.

## Five-case pilot

| Case | Atomic proposal | What the checkpoint proves |
| --- | --- | --- |
| Narration cut + B-roll start | One selected update with two changed entities | The spoken cut and range endpoint remain distinct; skipped After update contains neutral current content, never the script target. |
| Three-row deletion | One checkbox and one count | Current rows stay readable as inert evidence; selected After shows one seam; skipped After keeps all rows. |
| Three-row move | One identity and count across both locations | Real neighbors remain visible. A uses a primary passage plus linked stub; B shows both locations in full. |
| Transparent Graphic merge | One structural update | The changed entity is the row break. Current shows two rows and a transparent overlay; selected After shows one row without false row-pair connectors. |
| Cross-row M2 change | One independent audio update | Audio-only is valid; M2 spans rows once; its duration end is not attached to an invented out-word. |

## Harness and retained evidence

- Eligible changes start selected. Select all, Clear all and per-change
  checkboxes update the rail, counts, After update and action from one shared
  selection.
- Missing visual and audio files block only their affected changes in the
  pilot. Blocked is separate from skipped even after Clear all; offline media
  is explicitly not deletion evidence.
- Partial failure remains inside the review. Consequences distinguish
  `Verified in v4`, `Attempted — not verified`, `Not attempted` and `Skipped`.
  Counts are derived from the selected plan, Retry preserves that selection,
  v3 remains current and the baseline is not updated.
- Move treatments A and B, skipped comparison, missing media, cleared blocked
  state, partial failure and audio-only partial failure all have focused
  evidence at both target sizes.
- No tested state has horizontal overflow.

Verification:

```sh
node docs/prototypes/issue-128/check.mjs
```

Result:

```text
PASS accepted #135 source c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea
PASS shared stylesheet and copied row-type source markers
PASS 10 pilot states × 2 viewports; 20 screenshots retained
```

## Known pilot limits

- This is a controlled static simulation, not Resolve detection, planning,
  persistence or execution.
- The sticky action overlaps the lower edge of some 800px evidence while
  scrolling. It does not obscure the state, consequence or choice under test;
  polish waits for the Producer's layout direction.
- The five cases are a mechanics gate, not the complete accepted S05 coverage.
- Protected/incompatible Resolve work has no accepted classification in #58.
  The pilot exposes scoped blocking but does not silently invent preservation.

## Producer choice gate

Open the exact pilot above, then make these choices in order:

1. **Left rail and compact default.** Confirm that the retained #123-style
   hierarchy works when its decision is outbound `Selected / Skipped /
   Blocked`, and that skipped clearly means Resolve stays current while the
   difference remains outstanding.
2. **Compare scope.** Choose inline per change only, or add a document-wide
   Compare mode later. Current recommendation: inline only until a real
   whole-document need appears.
3. **Move default.** Choose A, primary passage plus linked stub, or B, both
   locations in full. Current recommendation: A; it preserves one identity
   without making the passage look duplicated.
4. **Protected/incompatible work.** Approve scoped blocking with whole-plan
   escalation when the conflict cannot be bounded. Confirm `Blocked` remains
   distinct from `Skipped`.
5. **Missing local media.** Choose affected-change blocking or warning-only
   execution. Current recommendation: block the affected change; absence is
   not evidence that the attachment should be removed.
6. **Partial failure baseline.** Confirm all-or-nothing baseline advancement:
   draft v4 may contain verified work, but v3 remains authoritative until the
   entire selected plan verifies.

If any treatment is unacceptable, name the first bad case and state. A concise
recording response can be: `Rail yes/no; compare inline/both; move A/B;
protected scoped/whole-plan; missing block/warn; baseline all-or-nothing/
subset`, followed by the first failure if any.

## First unfinished step

After the Producer records those choices, expand the accepted direction in
bounded additive batches across the remaining S05 families listed in the plan.
Do not start that expansion before this gate is resolved.
