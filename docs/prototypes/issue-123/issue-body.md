## Outcome

Design and obtain Producer acceptance for reconciling changes made in a managed
Resolve timeline back into the canonical script. The design must reuse the
accepted S05 change-review language wherever possible, including white script
rows, while entering from the accepted S03 authoring experience.

## Scope

- Create a new successor artifact in the existing `VERA design feedback` Claude
  project without changing the accepted S01–S05 artifacts.
- Show only changes originating in Resolve. Script-only edits remain canonical
  and absent from inbound review.
- Design preselected safe changes, explicit compatible same-row confirmation,
  and incompatible same-row choices for script-wins, supported Resolve adoption,
  or defer.
- Introduce locked **Resolve-only content** rows for recognized-but-unrepresentable
  and ambiguous/unrecognized timeline material, with attached and standalone
  placements, optional descriptive names, collapsed script presentation, future
  preservation, collision blocking, and verified-removal review.
- Retain design evidence at `1280 × 800` and `1024 × 768` across entry, review,
  conflict, preservation, result, no-change, unavailable, error, focus,
  non-color, and overflow states.

## Acceptance criteria

- [ ] S03 shows a clear, non-color-only managed-timeline-change alert, the
  number of timeline-originated changes to review, and a dedicated counted
  action; the no-change and unavailable states show no false or stale count.
- [ ] The review visibly reuses S05's white script rows, script order,
  two-column structure, red/green plus non-color semantics, filters, controls,
  counts, scrolling, focus, and responsive behavior.
- [ ] Script-only edits are absent. Understood non-conflicting Resolve changes
  are preselected, while compatible same-row changes require explicit combine
  confirmation.
- [ ] Incompatible same-row changes have no default and offer only clear
  script-wins, supported Resolve-adoption, or defer decisions with their future
  inbound and outbound consequences.
- [ ] Resolve-only content is automatically recorded in attached or standalone
  locked rows, retains a permanent system label and optional editable name, and
  remains collapsed but visible in ordinary script editing.
- [ ] Future outbound updates preserve Resolve-only material; ambiguous movement,
  overlap, order, or timing collisions block; missing content is never replaced
  with a slate; verified deletion is proposed as a selected row removal.
- [ ] After presenter recording changes word timing, understood B-roll retimes
  normally while affected Resolve-only media stays untouched and receives one
  stable, non-rendered manual timing review marker at the recalculated word
  anchor; ambiguous or missing anchors block instead of being guessed.
- [ ] **Reconcile script** can complete safe work while accurately reporting
  deferred conflicts and partial out-of-sync status. It never claims to create
  or update a Resolve timeline.
- [ ] Both required viewports demonstrate pointer and keyboard routes, logical
  focus, readable non-color states, and no horizontal overflow.
- [ ] The Producer reviews and explicitly accepts the exact Claude artifact or
  identifies the first unacceptable state.

## Dependencies

- Blocked by #14
- Blocked by #58

## Exclusions

- No Resolve sync, observation implementation, diff engine, persistence, script
  mutation, timeline build, authorization, production UI, API, schema, contract,
  fixture, golden, generated-type, or accepted-artifact change.
- No technical proof of exact reverse mappings in this design slice.

## Follow-up requirement

After design acceptance, create a separate Inbox technical story that blocks
implementation and proves the supported reverse mappings, stable identity and
anchoring, preservation, conflict/defer persistence, verified deletion,
missing-content behavior, post-presenter timing-marker identity/lifecycle, and
required contract/generated-type changes.

## Parent rationale

Sub-issue of #62 because the integrated prototype and final design handoff must
include this explicit timeline-to-script reconciliation path before design
finalization.
