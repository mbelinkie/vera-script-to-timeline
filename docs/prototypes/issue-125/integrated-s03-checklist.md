# Integrated S03 design checklist — #125

Updated 2026-10-27. This is the integration review list, not a claim that the
current comments or Sorting prototype implements every item. Producer choices
remain accepted where recorded; each unchecked box means it still needs an
explicit disposition against the final integrated artifact.

## How to use this list

For each item, record **verified**, **missing**, **explicitly deferred**, or
**accepted prototype limitation**, with the exact artifact and scenario. A
verified design interaction is separate from production/runtime capability.
Deferred items need their owning issue and recorded scope decision. Do not
silently lose an existing feature while incorporating a new one.

Primary inputs: the accepted #135/#140 S03 controls; the #318 action/capability
matrix (A01–A25); #125's consolidated scope; and later Producer decisions.
The accepted Sources remain immutable; review the latest actual working
successor, not a reconstruction. Relevant later working files include shared
S03 r11 and Sorting r14; record the exact current comments and integrated
filenames before review rather than assuming those versions are still latest.

For every section below, check normal and narrow views at 1280×800 and
1024×768, pointer and keyboard access, focus/Escape, cancellation, empty and
populated states, and relevant Undo/error states. Preserve known limitations
without treating simulated behavior as backend evidence.

## 1. Script reading, selection and visual insertion

- [ ] Narration remains readable in the established two-column S03 grammar;
  adding a comment does not reflow words through inline pills.
- [ ] Bold means On Camera at the actual word range; VO and graphic overlays
  do not acquire bold merely because of their type or position.
- [ ] Range actions snap to complete words, and the popup's quoted selection
  agrees with the visibly highlighted range. Ordinary character editing remains.
- [ ] Selected narration offers both **Add visual** and **Add comment** and
  retains the range while the chosen interface opens.
- [ ] Existing **+ Visual** entry remains available without a text selection.
- [ ] **Next visual in sequence**, **Cutaway then return**, and **Graphic
  overlay** are reachable and describe different picture behavior.
- [ ] Selecting words → Graphic overlay → Lower third preserves the base
  picture, narration and audio and uses the selected start/end words.
- [ ] Sequential and cutaway choices disclose their coverage/return changes;
  existing coverage is not a blanket reason to disable Add visual.
- [ ] Placeholder, local media, Research footage, capture and graphics entry
  points remain available within each owner's supported envelope.
- [ ] End brackets, start words, word-ended/media-ended behavior and card ↔
  text hover/focus correspondence remain understandable and adjustable.
- [ ] Connector lanes remain separate and aligned through expanded controls,
  sidebar opening, overlays and cross-row music appearances.
- [ ] Rows are identified by content in product copy and accessible labels,
  never row numbers. Visual-event ordinals and internal IDs are separate.

## 2. Row and section controls

- [ ] Add row above/below and Add section remain discoverable and keyboard
  accessible, including at the beginning/end and in an empty section.
- [ ] Row **⋯** actions occupy a reserved gutter and do not overlap cards,
  connectors or text; hover actions also appear on keyboard focus.
- [ ] **Stash** and **Delete row** are distinct explicit actions.
- [ ] Populated-row deletion retains the established confirmation/cancel and
  Undo route; empty-row behavior is deliberate.
- [ ] Delete removes active row content/placements without deleting source
  media files or silently turning the operation into Stash.
- [ ] Deleted-target discussions survive quietly as orphaned; exact Undo is
  intended to restore the row and its prior comment attachment state together.
- [ ] Structural changes expose supported relationship/timing consequences
  without claiming automatic repairs or implicit Resolve updates.

## 3. Visual, audio and inspector controls

- [ ] Card type/source replacement, removal and supported reordering remain
  accessible; overlays stay distinct from full-frame visuals/cutaways.
- [ ] Source preview/trim, word seek and Set/Clear out retain their established
  behavior, provenance and missing-media treatment.
- [ ] No/Quiet/Full source-sound behavior remains explicit; footage with full
  primary sound has its own row with empty host narration.
- [ ] Footage transcript appears on the right card and is never host narration
  or prompter text; the Footage pill has consistent treatment.
- [ ] On Camera/Wide/Tight and cutaway returns preserve the qualified limits;
  no unrelated framing or dialogue change is implied.
- [ ] Image/capture motion, automatic zoom and None/settings footprints agree
  with the adopted product decision and the exact available proof.
- [ ] Add audio/library/local-audio, span endpoints, duration-ended tails and
  supported cue settings retain their entry points and honest limits.
- [ ] Markers, citations, nonspoken directions and graphic-template inputs
  remain distinct from narration and preserve their established affordances.

## 4. Transitions

- [ ] Internal-visual and between-row boundary controls appear on hover/focus;
  a final row offers Add row without a nonexistent next-row transition.
- [ ] New boundaries start as cuts; adding a transition is always explicit.
- [ ] Project library add/search/curation/order supports qualified entries;
  first-in-list is chooser order, never automatic application.
- [ ] Actual Resolve names, occurrence effect/duration/alignment and qualified
  effect-specific controls appear without aliases or invented controls.
- [ ] Removing an in-use project entry offers keep existing, explicit
  replacement and cancel within supported preservation/replacement limits.
- [ ] Missing neighbors, insufficient handles, unavailable/unknown effects and
  settings have explicit supported outcomes; no silent Cut or timing theft.
- [ ] Movement preserves intact-pair effects, retains separated-pair review
  evidence and leaves new joins as cuts; no automatic effect reactivation.

## 5. Sorting and Stash

- [ ] A · Line is the selected compact layout; literal opening/ending excerpts
  preserve OC formatting, with short text shown only once.
- [ ] One orange ellipsis means omitted text; orange +N between right-side
  endpoints means omitted visuals. Neither means timing or a script cut.
- [ ] Right-only first/last thumbnails count planned beats, including repeated
  endpoints; OC is neutral and missing images have honest placeholders.
- [ ] Photo hover/keyboard enlargement does not shift rows and is suppressed
  during dragging; OC and unavailable slots do not enlarge.
- [ ] At least ten readable collapsed rows fit both required viewports; no
  shrinking type or hiding required context to manufacture a pass.
- [ ] Left gutter click/range/Shift selection stops at section boundaries;
  one group handle stays on the left and internal order is preserved.
- [ ] Row/group movement across sections and complete-section movement have
  insertion feedback, keyboard/Move to alternatives, cancel and Undo.
- [ ] Colored left Moved marks reflect net deliberate changes and clear on
  return to the starting position; dragging has no visible destination prose.
- [ ] Single-click expansion/collapse preserves a summary header and does not
  collapse when interacting inside content. No redundant Collapse button.
- [ ] Back to script previews proposed ordering read-only; Accept, Return and
  Discard have the agreed script AND Stash consequences and retained drafts.
- [ ] Show Stash/count, sidebar, wide inspection and normal-authoring access
  remain present. Saved rows are excluded from active build/export consumers.
- [ ] Independent Stash restore/explicit multiselect and optional Stash sections
  retain adopted requirements; working depiction waits for #337's exact proof.
- [ ] Quiet piano uses a separate right gutter. Intact runs remain intact;
  first-interruption shortening/warning/cancel/Undo retains #326's proof hold.
- [ ] No stale user-facing “trial,” fixture/developer labels or row-number
  descriptions return to the product frame.

## 6. Comments and Research consistency

- [ ] Sidebar is selected; opening it does not cover the target. Global
  Comments access and local text/card/row/gap access remain consistent.
- [ ] Valid unresolved text discussions use subtle highlighting with no inline
  pills; clicking/focusing reaches every discussion on an overlapping range.
- [ ] Replies are flat/chronological with consistent author/time/composer
  treatment; mentions and roles do not imply unproved service delivery.
- [ ] Escape and switching discussions retain drafts; Discard is explicit and
  focus returns sensibly. No unproved NEW/unread service behavior is implied.
- [ ] Unresolved missing-target discussions have no script pill/highlight and
  live under collapsed **Orphaned comments**, with a quiet count.
- [ ] Orphaned context retains the old quote/visual description and offers
  Show original row, Show in Stash or Original row deleted as appropriate.
- [ ] Reattachment is optional inside the orphaned discussion; there is no
  guessed target or prominent repair demand in the script.
- [ ] Replaced-source-shot discussions do not transfer to the replacement;
  title/ordinary settings edits alone do not count as replacing the source.
- [ ] Whole-row discussions remain attached while their row survives.
- [ ] Resolving removes persistent marker/highlight and moves the discussion
  to collapsed **Resolved**; temporary target inspection does not reopen it.
- [ ] Resolved includes all resolved discussions; reopening one with no valid
  target moves it to Orphaned, never a second simultaneous listing.
- [ ] From Research starts collapsed, remains separately labeled/read-only and
  offers Open in Research even in read-only script contexts.
- [ ] Research source discussion stays out of script-wide discussion counts
  and never becomes production instructions without a separate explicit action.
- [ ] Research and S03 share comment visual vocabulary; any proposed divergence
  has a named Research follow-up rather than an unrecorded inconsistency.
- [ ] Comment-only operations leave narration/prompter/duration/build unchanged;
  #324's exact limits are not confused with new replacement/Undo/service proof.

## 7. Remaining authoring controls and integration

- [ ] Presenter name/thumbnail, text size, thumbnail size including zero,
  column divider and Reset retain accepted behavior without changing content.
- [ ] Media provenance/readiness, missing-file/relink/replacement and unplaced
  content retain their honest states and supported recovery entry points.
- [ ] Narration audio state, preview/regeneration and build readiness are
  visible without pretending unsynchronized or unresolved content is complete.
- [ ] Prompter, Preview/Release, build/update and inbound-review entry points
  retain their owner's scope and return to the intended S03 state.
- [ ] Saved/local/sync/offline/error/role states do not promise capabilities
  absent from the actual implementation; disabled/unknown states are honest.
- [ ] Existing review grammar, citations, linked/dormant alternatives and
  provenance/locks survive consolidation; do not replay or undo accepted choices.
- [ ] Ideas/planning and broader Extras are accounted for separately from
  Sorting/Stash; no implicit delivery or silent deletion of future scope.

## Accepted prototype limitations and finish line

Expanded rows need not render the supplied photo atlas at full fidelity for
this interaction review. No audio/video playback, real service synchronization
or Resolve action is proved by a simulated page. These are recorded limits,
not invitations to repair unrelated prototype fidelity.

Before final #125 acceptance, give every item above a disposition against one
named integrated S03 source. Keep the latest comments/Sorting decisions and
exact source references with the handoff, and test the ordinary workflow again
after integration. The current component review can stay focused: the missing
Graphic overlay selection choice belongs to that later integration check, while
whole-word comment selection belongs to the current comments review.
