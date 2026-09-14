# Issue 123 plan — timeline-to-script reconciliation and S03 entry

## Scope and authority

Issue #123 is the active Sol/high, Producer-accepted design slice for the
reverse reconciliation path: a managed Resolve timeline differs from its last
applied immutable build and the canonical script may need an explicitly chosen,
bounded update. The design adds a clear S03 entry beside the established
export/release access and a focused three-way review derived from the accepted
#58 S05 change-review language.

The active claim is task `01a09d7d-49f0-7b12-b003-1163fb7d7959` on
`codex/issue-123-reconciliation-design`, using `sol` at `high` effort.
Acceptance authority is Producer. Dependencies #14 and #58 are closed and Done:
#14 supplies the accepted S03 authoring composition and #58 supplies the
accepted row-review, selection, consequence, accessibility, and responsive
language that this slice deliberately reverses.

## Slice ritual

Scope: one self-contained design prototype and retained evidence for the S03
entry, three-way review, explicit decision boundaries, safe bulk selection,
dependency effects, protected editorial changes, completion result, and all
required capability/accessibility/error states.

Exclusions: no Resolve observation or sync; no diff engine; no persistence or
script mutation; no timeline build; no authorization; no export/release change
beyond the prototype entry; no arbitrary reverse import; and no production UI,
API, local-agent, background-job, or Resolve behavior.

Touched contracts, fixtures, goldens, generated types, and shared tokens: none.

New dependencies: none. The prototype is one native HTML/CSS/JavaScript file,
so the review artifact adds no package or runtime dependency.

Automated checks:

- validate the document structure and required labels with a small Node check;
- render every retained state at `1280 × 800` and `1024 × 768` with the local
  browser and confirm image dimensions;
- scan every rendered state for horizontal document overflow;
- confirm the repository diff contains no contract, fixture, golden,
  generated-type, or production-code change;
- run whitespace and repository validation checks appropriate to a docs-only
  slice.

## Design authority and interaction boundary

The review names all three sources at all times: **last applied build**,
**current script**, and **managed Resolve timeline**. A Resolve-side observation
is evidence to review, never canonical script truth.

The five row classifications and defaults follow the product specification:

| State | Non-color label | Default | Safe bulk behavior |
| --- | --- | --- | --- |
| Script changed only | `SCRIPT CHANGED` | Selected | Included |
| Resolve changed only | `RESOLVE CHANGED` | Not selected | Excluded |
| Both changed, compatible | `BOTH CHANGED · COMPATIBLE` | Selected | Included |
| Both changed, conflicting | `CONFLICT · DECISION REQUIRED` | Proposed selected, blocked | Excluded until decided |
| Unchanged | `UNCHANGED` | Hidden | Excluded |

`Select all safe updates` selects only script-only and compatible rows. It never
selects Resolve-only, unresolved conflicts, protected editorial work, or
transition changes.

Every conflict exposes only four deliberate outcomes:

1. **Use script version** — rebuild script-owned content in the new timeline
   while preserving recognized compatible Resolve work.
2. **Keep Resolve version for now** — leave the script unchanged, preserve the
   Resolve row, and record the row as out of sync.
3. **Adopt supported Resolve change into script** — available only for clean
   in/out refinements and subtitle-copy edits, and only after the user selects
   that exact bounded adoption.
4. **Review manually in Resolve** — preserve the current timeline and defer the
   row without inferred adoption.

Transition-default and transition-occurrence changes are protected editorial
state. They are separate Resolve-side reconciliation items, are never treated
as trim or subtitle edits, and route to preserve/review manually in Resolve.
The same protected path applies to arbitrary tracks, effects, ripple edits,
grades, mix changes, and protected additions.

Before the simulated action, the design reports duration/dependency effects,
anchored additions that move, unanchored items requiring review, deliberately
out-of-sync rows, and deferred conflicts. The result names a new versioned
timeline and explicitly says that the current timeline remains untouched. It
does not claim that any production operation ran.

## Retained state matrix

The prototype exposes deterministic `?state=` routes for:

- `entry`: S03 non-color alert and adjacent reconciliation action;
- `review`: all five row classes, filters, defaults, and safe bulk selection;
- `conflict`: property-level four-way decision, bounded adoption, and protected
  transition item;
- `result`: dependency effects, preservation, out-of-sync decisions, deferred
  work, and new-versioned-timeline language;
- `no-change`: current timeline matches the last applied build and no false
  reconciliation action appears;
- `unavailable`: browser/local-agent/Resolve boundary and recovery actions;
- `focus`: keyboard route and visible focus order;
- `non-color`: labels/icons/patterns remain understandable without color;
- `overflow`: long script/media/transition labels reflow without clipping; and
- `error`: a readable observation failure with retry and manual-preservation
  path.

Each route is retained at both required viewport sizes. The prototype supports
pointer activation and native keyboard controls, uses one document scroll
region, and keeps the review/action relationship intact when rows stack at the
narrow viewport.

## Producer acceptance checklist

1. Open `docs/prototypes/issue-123/timeline-to-script-reconciliation.html` at
   `?state=entry` and `1280 × 800`. Confirm the S03 alert states that the
   managed timeline changed, does not rely on color, and places **Reconcile
   timeline changes** beside the established Prompter/Resolve actions.
2. Activate the reconciliation button, then review `?state=review`. Confirm the
   three named sources, five row labels, filters, documented defaults, counts,
   row-level choices, and **Select all safe updates** behavior faithfully reuse
   #58's review language in reverse.
3. Open `?state=conflict`. Confirm all four decisions state direction and
   consequence; bounded adoption is available only for the clean in/out and
   subtitle-copy examples; the transition occurrence remains a distinct
   protected item with only preserve/manual review behavior.
4. Open `?state=result`. Confirm the dependency effects, anchored/unanchored
   outcomes, deliberately out-of-sync row, preserved Resolve work, deferred
   conflict, new timeline version, and untouched-current-timeline statement are
   all explicit design language rather than execution claims.
5. Open `?state=no-change`, `?state=unavailable`, and `?state=error`. Confirm the
   no-change state offers no false action; browser/local-agent/Resolve limits
   and recovery are readable; and failures preserve the timeline and offer an
   actionable retry/manual path.
6. At `?state=focus`, traverse controls with Tab/Shift+Tab and activate filters,
   checkboxes, row decisions, and the primary action with the keyboard. Confirm
   the visible focus ring and logical order.
7. At `?state=non-color`, confirm state meaning remains clear from text labels,
   icons, borders/patterns, and strikethrough without color.
8. At `?state=overflow`, confirm long narration, media identity, path, and
   transition text wrap/reflow without horizontal clipping.
9. Repeat steps 1–8 at `1024 × 768`, using the retained screenshots as reference.
   Confirm the narration/production columns reflow within each row, controls
   remain readable, and the page has no horizontal overflow.
10. Reply `Accepted — update and close #123` if every state is acceptable, or
    identify the first unacceptable file/view/action and expected correction.
    The issue remains **In review** until this explicit Producer response.
