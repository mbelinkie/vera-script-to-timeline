## Outcome

Design and obtain Producer acceptance for reconciling changes made in a managed
Resolve timeline back into the canonical script. Reuse the accepted S05 review
language wherever possible, including its white rows, while entering from S03.

## Scope

- Continue the successor artifact in the existing `VERA design feedback`
  Claude project without changing accepted S01–S05 artifacts.
- Show only Resolve-originated changes, except where a script edit intersects
  the same words, audio item, or visual item and creates a conflict.
- Design preselected safe changes, explicit compatible combinations, and
  unselected incompatible Accept/Reject/Defer decisions.
- Treat rows as author-defined closed visual containers: visuals may be
  sequential or overlap as stacked layers inside one row, but cannot cross a
  row boundary. A bridging visual proposes a row merge; structural boundaries
  block instead.
- Treat **Added in Resolve** as provenance. Understood additions become native
  editable cards; unsupported accepted additions become locked
  **Preserved as-is** cards with optional names.
- Represent only effective visible/audible output in the active script while
  silently preserving fully hidden lower-track alternatives for possible later
  restoration.
- Retain design evidence at `1280 × 800` and `1024 × 768` across entry, review,
  conflict, merge, preservation, result, no-change, unavailable, error, focus,
  non-color, scrolling, wrapping, and overflow states.

## Acceptance criteria

- [ ] S03 shows a clear non-color-only managed-timeline alert, truthful count,
      and counted action, with no false or stale count when in sync, checking,
      or unavailable.
- [ ] The review visibly reuses S05 white rows, script order, two columns,
      red/green plus non-color comparisons, filters, controls, counts, scrolling,
      focus, and responsive behavior.
- [ ] Understood non-conflicting Resolve changes are preselected. Compatible
      intersecting changes require **Combine both changes**; incompatible ones
      have no default and offer Accept, Reject, or Defer with accurate inbound
      and future S05 consequences.
- [ ] **Words cut** is demonstrated only from verified program-audio/transcript
      removal, never inferred from a picture trim.
- [ ] A visual bridging adjacent narration rows is one compound merge proposal
      that preserves words, paragraph structure, OC/VO state, anchors, comments,
      and identity. Valid merged rows do not auto-split; structural-boundary
      spans block.
- [ ] Full-frame visuals retain #56's ordered non-overlapping sequence while
      simultaneous overlays use bounded, possibly overlapping ranges and clear
      compositing order. Unanchored footage uses a right-only row with explicit
      timeline bounds.
- [ ] Understood accepted additions become native cards with a compact permanent
      **Added in Resolve** badge. Unsupported additions require Accept/Reject/
      Defer; accepting creates a locked **Preserved as-is** card with optional
      non-rendered naming.
- [ ] Fully covered lower clips disappear from the active script but remain
      dormant and silently preserved in Resolve/history. Verified later reveal
      produces one preselected compound restoration proposal; partially visible
      layers remain represented.
- [ ] Attached preserved-as-is media follows a verified start-word anchor while
      retaining source in/out and duration. When ending fit needs review, one
      stable non-rendered marker appears at the resulting outpoint; safe fit has
      no marker and missing/ambiguous anchors block.
- [ ] Actual S05-style future states show rejection selected by default, defer
      unchecked, preservation/restoration, verified deletion, and missing-media
      blocking without a slate.
- [ ] **Reconcile script** can finish safe work while accurately reporting
      deferred conflicts and partial out-of-sync status and never claims to
      change Resolve.
- [ ] Both viewports demonstrate pointer and keyboard routes, readable non-color
      states, wrapping, scrolling, and no horizontal overflow.
- [ ] The Producer explicitly accepts the exact artifact or identifies the
      first unacceptable state.

## Dependencies

- Blocked by #14
- Blocked by #58

## Exclusions

- No Resolve observation or sync, diff engine, persistence, script mutation,
  timeline build, production UI, API, schema, contract, fixture, golden,
  generated-type, or accepted-artifact change.
- No technical proof of exact reverse mappings or row/identity migration.

## Follow-up requirement

After design acceptance, create a separate Inbox technical story that blocks
implementation and proves row merging/cross-block representation, stable native,
preserved and dormant identities, effective-output comparison, audio-cut
detection, conflict/defer persistence, dormant restoration, deletion, missing
media, marker lifecycle, and required contract/generated-type changes.

## Parent rationale

Sub-issue of #62 because the integrated prototype and final design handoff must
include this inbound reconciliation path before design finalization.
