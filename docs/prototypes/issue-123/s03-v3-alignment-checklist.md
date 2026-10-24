# Issue #123 — accepted S03 v3 alignment checklist

Status: **working verification checklist, not Producer acceptance**. The active
artifact is `Script to Timeline - Compact Mixed-Change Reconciliation Pilot` in
the VERA design feedback project. The older twelve-case issue body and plan are
historical descriptions; they must not override the current 22-change pilot,
later Producer decisions, or the [annotation guide](reconciliation-annotation-guide.md).

## Authority and scope

- #135 is accepted and Done. Its retained, self-contained artifact is
  `issue-135/S03 v3 authoring artifact - issue 135 export v2.dc.html`, SHA-256
  `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea`.
  The first export is invalid and superseded. See #135's retained `handoff.md`
  for the 22-row migration and control matrices.
- Transfer the accepted *authoring row grammar* into #123's read-only surfaces.
  Do not transfer S03 editing chrome, and do not paint reconciliation green/red
  onto ordinary authoring rows. The #123 annotation guide controls difference
  signals on Current Resolve; Current script remains the literal neutral source.
- Preserve all 22 #123 changes, decisions, source switching, derived-result
  conditions, context, counts, and simulated outcomes. #123 remains In progress
  until explicit Producer acceptance.
- Allowed design edit: the #123 pilot and its page-local renderer adaptation.
  Do not edit accepted S01–S05 artifacts, #127/#135, shared renderer pages,
  contracts, fixtures, generated types, or production interfaces.

## Shared row invariants to verify

| Accepted S03 v3 rule | #123 verification |
| --- | --- |
| Row-local visual IDs; subtle singleton, full multi-visual numbers | Both literal sources use the same neutral identity grammar; numbers never mean a diff. |
| Non-orphaning bracket and word units; straight Graphic ticks | No orphan bracket at small/default text; stable card-to-range linkage by pointer and keyboard. |
| On Camera means presenter visible; opaque cutaway hides the base | Narration weight and return treatment match actual visible picture; hidden footage is not depicted as visible or deleted. |
| Transparent Graphic is an independent layer | Its base remains visible; card has a fine dashed perimeter and its own range marks, without persistent dashed narration underline. |
| Light type tints for unchanged cards | Whole new/replaced cards instead use #123's green fill and border; property/range-only changes retain type tint. |
| One compact primary card pill, thumbnail, useful length, sound and zoom | Source bookkeeping is on demand. B-roll under narration is No/Quiet, not Full; standalone Full sound can show transcript. |
| Need to Find and Placeholder are visible, ranged visual intent | Same-anchor fulfillment replaces a slot: green footage card, neutral range marks and unchanged words. |
| Music uses separate document-wide M IDs and thin right-margin rail | An explicit out-word differs from a duration-driven tail with no out-word; neither merges visual rows. |

## Focused cases and expected evidence

- **7, 13 — audio:** New bed has green rail and anchors, existing fade-only
  change boxes only the fade value. The unchanged rail/span and narration stay
  neutral. Audio IDs use M, not visual ordinals.
- **15 — cutaway:** The opaque insertion alone is green; original B-roll
  continues underneath and resumes. Words are neutral unless their text changed.
- **16, 20, 21 — Graphics:** The base stays visibly continuous under a
  transparent Graphic. New Graphic card/marks are green with a fine dashed
  perimeter. #21's already-decided Accept produces one clean script row across
  the ordinary former row boundary, while preserving both original sentences.
- **17 — request fulfillment:** Current script has the neutral ranged request.
  Current Resolve has green candidate footage over identical neutral anchors.
- **22 — existing Graphic range:** Card retains Graphic tint and identity; only
  the changed endpoint and useful duration are green. No green unchanged words
  or persistent dashed underline.
- **2, 5, 11, 12, 18, 19 — regression samples:** Added row, whole-row move,
  start-only trim, same-range source replacement, clip swap, and whole-row swap
  must retain their distinct annotation rules.

## Final evidence gate

Record each of 22 changes against the annotation guide: literal source
truthfulness, changed entity, selected outcome, conditional result, range
inspection, card fit, and accessibility. Check 1024 × 768 and 1280 × 800;
default/small text; default/0% thumbnails; pointer and keyboard focus; no
horizontal overflow or runtime errors. Then retain an exact self-contained
#123 export and a short handoff with hash, known limitations, and Producer
acceptance steps. Do not mark #123 Done based on an agent self-report.
