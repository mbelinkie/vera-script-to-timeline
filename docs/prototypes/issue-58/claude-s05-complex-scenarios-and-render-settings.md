# Claude brief: complete S05 complex scenarios and render settings

Continue refining S05 in the existing **Script to Timeline — Prompter Runtime
and Suite Navigation S04–S06** artifact.

Before editing, stop and ask Matthew focused questions about every material
product or interaction decision that remains unclear. Wait for his answers.
Use your own product-design judgment within the requirements below rather than
mechanically adding controls.

Keep S04 unchanged. Keep S06 completely deleted. Do not restore Preview/Release
terminology or inbound **Changes in Resolve** review.

## 1. Add the missing complex-scenario coverage

Add focused S05 harness scenarios that demonstrate each distinct rule below.
Do not place every example in the main **Connected · ready** scenario.

Reuse S03 conventions throughout:

- preserve S03's narration and production-column widths;
- reuse its thumbnail and card treatments;
- voiceover text is regular;
- on-camera text is bold;
- ordinary VO and OC badges do not appear; and
- `VO → OC` and `OC → VO` are the only camera-state badges.

All affected-row checkboxes begin selected. Checked means send that row's
change; unchecked means skip it. Counts, warnings, action labels, completion
results, and manual checks must derive from the current selections.

Old material uses red treatment, new material uses green treatment, and
unchanged context stays quiet. Do not add a persistent legend.

### First correct the existing Closing row

Revision A:

- Voiceover, regular: `We adjust only after the second reading.`
- Visual: Still Image `asset-second-reading-dashboard`

Current script:

- On camera, bold: `The second reading tells us when to adjust.`
- Visual: On Camera, Tight

Required behavior:

- Show `VO → OC`.
- Keep the deleted wording regular and red.
- Show the new wording bold and green.
- Hovering or focusing the current On Camera card green-underlines only
  `The second reading tells us when to adjust.`
- Represent the old dashboard's previous coverage separately. Never concatenate
  the old and current wording into one current range.
- The accessible description must name the previous and current text and ranges
  separately.
- One row checkbox controls the complete wording, camera-state, and visual
  change.

This demonstrates a camera-state change combined with a wording change.

### Scenario: Camera-state changes

Show three logical row changes, all selected by default.

#### VO → OC only

Revision A:

- Voiceover, regular: `The indicator remains steady through the first reading.`
- Still Image `asset-indicator-closeup`, covering the complete sentence

Current script:

- On camera, bold: `The indicator remains steady through the first reading.`
- On Camera visual, Tight, covering the complete sentence
- The wording is identical.

Required behavior:

- Show `VO → OC` without inventing a wording deletion/addition.
- Show the old still image as removed and On Camera as current.
- Hovering the current On Camera visual uses a solid green underline across the
  full sentence.
- Hovering the removed still image separately uses the dotted red previous-range
  underline across the full sentence.
- One checkbox controls the complete state and visual change.

This demonstrates a pure VO → OC change with unchanged words.

#### OC → VO only

Revision A:

- On camera, bold: `The warning sits directly beneath the gauge.`
- On Camera visual, Medium

Current script:

- Voiceover, regular: `The warning sits directly beneath the gauge.`
- Still Image `asset-warning-gauge`, covering the complete sentence
- The wording is identical.

Required behavior:

- Show `OC → VO` without a wording diff.
- Mark the replacement image itself visibly as `NEW`; the badge alone is not
  sufficient.
- Show the old On Camera treatment as removed.
- Hovering the new image uses a solid green underline across the full sentence.
- Hovering the old On Camera card separately uses the dotted red previous-range
  underline.
- One checkbox controls the complete state and visual change.

This demonstrates the reverse camera-state change and makes the newly added
image unmistakable.

#### State and wording changed together

Use the corrected Closing row above. It demonstrates that a camera-state badge,
wording diff, typography change, and visual change can belong to one selectable
row.

### Scenario: Rows split and merged

These are structural changes, not ordinary text rewrites. Preserve the exact
words and punctuation so the row boundary is the only change.

Show six visible affected rows, all independently selected by default. Do not
link their checkboxes: row-level approval remains authoritative. Partial
selection is allowed, with explicit outcome warnings.

#### Pure split: one old row becomes two current rows

Revision A has one row:

- Voiceover: `The first reading rises to eighteen, then pauses. The second reading reaches twenty-seven.`
- Logged Clip `asset-chart-first-reading` covers the first sentence.
- Logged Clip `asset-chart-second-reading` covers the second sentence.

The current script has two rows:

1. Voiceover: `The first reading rises to eighteen, then pauses.`
   - Logged Clip `asset-chart-first-reading` covers the complete row.
2. Voiceover: `The second reading reaches twenty-seven.`
   - Logged Clip `asset-chart-second-reading` covers the complete row.

Required behavior:

- Label the relationship as a row split, not a narration rewrite.
- Display the old combined row in red at its old location.
- Display the two current rows in green at their current locations.
- Do not mark any individual words as changed; the wording is identical.
- Each of the three visible rows has an independent checkbox.
- If the old-row removal is skipped while either new row is included, warn:
  `The original combined row will remain alongside the selected new row or rows.`
- If either new row is skipped, state exactly which narration and visual will
  not be added.
- Confirmation and result copy must describe the actual partial outcome.

This demonstrates a one-to-many structural change without overriding row-level
approval.

#### Pure merge: two old rows become one current row

Revision A has two rows:

1. Voiceover: `The lens clears before the reset.`
   - Still Image `asset-lens-closeup` covers the complete row.
2. Voiceover: `The dashboard returns to normal.`
   - Still Image `asset-dashboard-wide` covers the complete row.

The current script has one row:

- Voiceover: `The lens clears before the reset. The dashboard returns to normal.`
- `asset-lens-closeup` covers the first sentence.
- `asset-dashboard-wide` covers the second sentence.

Required behavior:

- Label the relationship as rows merged, not text changed.
- Do not add `and`, change punctuation, or show a word-level diff. Only the row
  boundary disappeared.
- Show both old rows in red and the current merged row in green.
- Give all three visible rows independent checkboxes.
- If the merged row is included while an old row's removal is skipped, warn
  that the retained old row will coexist with the merged narration.
- If the old rows are removed but the merged row is skipped, warn that the
  selected material will disappear from the new timeline version.
- Never silently force an atomic merge.

This demonstrates a many-to-one structural change with exact row-level control.

### Scenario: Visuals added, removed, and replaced

Narration remains unchanged in all three examples. Each row checkbox controls
its production-column change.

Use this consistent hover/focus rule throughout S05:

- unchanged visual: gold underline;
- new visual: solid green underline; and
- old or removed visual: dotted red underline.

Only the card currently hovered or focused paints an underline. Old and new
underlines never appear simultaneously, even when their spans are identical.

#### Add a visual within an existing row

Narration:

`The warning appears beneath the second reading.`

Existing unchanged visual:

- Still Image `asset-dashboard-wide`, covering the complete sentence

New visual:

- Onscreen Placeholder `asset-warning-callout`
- Covers `The warning appears`
- Displayed as a green `NEW` card

Required behavior:

- The unchanged dashboard remains neutral and uses the normal gold full-range
  underline on hover/focus.
- The new warning card uses a solid green underline only under
  `The warning appears`.
- There is no red previous range because this visual did not previously exist.

This demonstrates adding a visual without adding or rewriting narration.

#### Remove one of several visuals

Narration:

`The reset control remains visible while the graph settles.`

Unchanged visual:

- Still Image `asset-dashboard-wide`, covering the complete sentence

Removed visual:

- Onscreen Placeholder `asset-reset-control`
- Previously covered `The reset control`
- Displayed as a red `REMOVED` card

Required behavior:

- Hovering the unchanged dashboard uses a gold underline.
- Hovering the removed control separately reveals its old range with a dotted
  red underline.
- Do not show a current green range for the removed visual.
- Skipping the row keeps the control in the new timeline version.

This demonstrates removing one visual without deleting its narration or
unchanged sibling visual.

#### Replace a visual over the same range

Narration:

`The repaired housing holds through the final test.`

Revision A visual:

- Still Image `asset-housing-before`, covering the complete sentence

Current visual:

- Still Image `asset-housing-after`, covering the same complete sentence

Required behavior:

- Show the old image as red/removed and the new image as green/new.
- Do not claim the coverage boundary changed; the range is identical.
- Hovering the new image produces a solid green underline across the sentence.
- Hovering the old image separately produces a dotted red underline across the
  same sentence.
- One checkbox controls the replacement atomically.

This treatment is consistent with every other new-versus-old visual: underline
color communicates which version owns that visual, while only one hovered card
is shown at a time.

### Scenario: Section structure

Show section-marker addition, removal, and movement.

#### Removed section marker

- Old section row: `Section: Setup`
- Production column: Resolve section-marker card with red `REMOVED` treatment
- Skipping the removal leaves the Setup marker in the new timeline version.

#### Added section marker

- Current section row: `Section: Verification`
- Production column: Resolve section-marker card with green `NEW` treatment
- Skipping it prevents the Verification marker from being added.

#### Moved section marker

Show `Section: Closing` in red at its previous location and green at its current
location. Because only its location changed, treat the pair as one pure move:
the two visible checkboxes mirror one logical selection.

At both the old and new locations, provide context controls so the user can
reveal the neighboring narration on either side and understand what the marker
previously divided and what it divides now.

This demonstrates marker creation, deletion, and movement rather than only the
existing rename example.

### Scenario: Timeline already up to date

Show a linked Resolve timeline whose baseline matches the current script.

Copy:

`Timeline version 3 already matches the current script.`

Required behavior:

- Do not show an empty outbound-diff section.
- Do not show zero placeholder rows.
- Do not offer Update timeline or Update and render.
- Retain only useful timeline identity, connection, and navigation information.

This demonstrates the normal return state when nothing needs sending.

### Scenario: A reviewed row changes again

Use one row with three versions:

- Timeline baseline: `The operator described the change as “slow.”`
- Version currently shown in the review: `The operator described the change as “slow, then sudden.”`
- Newer synchronized cloud version: `The operator described the change as “slow, then sudden, then steady.”`

Required behavior:

- Show `Newer script version available` on that row.
- Offer a visible `Update row` button.
- Do not disable the overall review or either timeline action.
- `Update row` fetches and recalculates only that row in place, changes its
  current wording to `slow, then sudden, then steady`, and removes the notice.
- Other row selections remain untouched.
- The user may ignore the newer version intentionally.

If the user ignores it, both timeline actions use the reviewed wording currently
shown: `slow, then sudden`. Do not silently fetch the newer script.

When the affected row is included, show a concise nonblocking warning before a
render begins:

`This row has a newer script version. Continuing will use the version shown in this review.`

After completion, report appropriately:

- timeline only: `Built from the version you reviewed. 1 newer script change was not included.`
- timeline and render: `Rendered from the version you reviewed. 1 newer script change was not included.`

The ignored change returns in the next update review. Do not call the resulting
timeline incoherent or invalid; the user may deliberately create a temporary
timeline and render representing the reviewed state.

## 2. Correct the context affordance globally

This supersedes the previous rule that a section-ending row cannot reveal
context from the next section.

- The first row of a section may reveal the final row of the preceding section.
- The final row of a section may reveal the first row of the following section.
- The absolute first row of the entire script cannot reveal a row above it.
- The absolute final row of the entire script cannot reveal a row below it.
- Continue showing context only on request; do not permanently fill the review
  with unchanged rows.

Therefore, `Here is the sensor before the trial began.` may show the next row as
context when another section follows it. The moved-section example must offer
context at both its previous and current locations.

## 3. Timeline-only actions are immediate

`Create timeline` and `Update timeline` are one-click actions. Clicking either
starts the operation immediately.

Do not open a confirmation dialog. Remove the entire existing confirmation
surface beginning with copy such as:

`Create version 3 of Harbor Lights — Main`

Do not replace it with another comparison recap, selected-row summary, or
duplicated explanation. The review page already explains what Update timeline
will do.

## 4. Create/Update and render opens only render settings

Keep both action pairs:

- `Create timeline`
- `Create and render`
- `Update timeline`
- `Update and render`

The timeline-and-render actions open a compact **Render settings** popup. This
popup is not a timeline confirmation.

It must not contain:

- `Create version 3 of Harbor Lights — Main`;
- another explanation of the timeline duplication;
- another comparison against Timeline version 2;
- another affected-row count; or
- a generic confirmation of changes the user already reviewed.

The popup exists only to choose how much to render and which saved render
settings to use.

### Render settings behavior

- Prepopulate settings from the user's last render.
- Allow named render presets to be defined, saved, and selected later.
- Clearly distinguish `Last used` from a deliberately saved preset.
- Ask Matthew which concrete format choices, preset fields, and first-run
  defaults to demonstrate. Do not invent a supported codec/format matrix.
- Do not make format, preset, or destination claims that have not been decided.

The final popup action is context-specific:

- `Create timeline and render`
- `Update timeline and render`

After that click, VERA creates or updates the timeline, verifies it, and renders
without another confirmation.

### Continuous section render range

The popup allows either:

- the complete timeline; or
- a continuous range of script sections.

Use four illustrative section names:

1. `Opening`
2. `Why the Signal Changes`
3. `Verification`
4. `Closing`

Prefer a control such as `From section` and `Through section`, because it makes
noncontinuous selection impossible. Demonstrate rendering from
`Why the Signal Changes` through `Verification`.

The resulting render range begins at the first frame of the first chosen
section and ends at the last frame of the final chosen section. Do not permit
disconnected section selections in one render.

If you choose another interaction, it must explain why noncontinuous sections
cannot be selected and remain easy to use at both viewport sizes.

### Action hierarchy

Do not visually bury the timeline-and-render action. Give the two actions equal
weight, or make Create/Update and render the primary action. Ask Matthew if a
single hierarchy choice is required before editing.

### Capability truth

- Connected supported Resolve: both actions are available.
- Resolve closed or temporarily disconnected: both are unavailable until the
  connection returns.
- Unsupported Resolve version: both are unavailable.
- Broken timeline link: update actions are unavailable until resolved.
- Resolve Free: retain the honest package/manual-import flow and do not offer
  automated Create/Update and render.

## 5. Operation lifecycle and failure behavior

For an Update and render run, show these user-facing stages:

1. `Preparing timeline version 3`
2. `Duplicating version 2`
3. `Applying selected row changes`
4. `Verifying the new timeline`
5. `Rendering`
6. `Verifying the render`
7. `Complete`

Required behavior:

- Freeze the reviewed script version, row selections, chosen render settings,
  and selected continuous section range when the run begins.
- Prevent those inputs from changing during the run.
- If timeline creation fails, rendering never begins.
- If Resolve closes, wait and resume the same operation with the same frozen
  inputs rather than duplicating again.
- If timeline verification succeeds but rendering fails, retain the successfully
  created timeline.
- `Retry render` retries only rendering; it never creates another timeline.
- Cancellation is allowed at any stage and retains whatever completed
  successfully.
- The prior timeline always remains intact.
- Timeline-only operations stop after timeline verification and produce no
  render.

Completion identifies separately:

- the newly created timeline version;
- the selected row changes applied;
- intentionally ignored newer script changes;
- the chosen render section range; and
- the rendered artifact.

## 6. Keep prototype controls outside the user-facing app

Move `Timeline fails`, `Render fails`, `Resolve closes`, and other simulation
triggers out of the VERA application window and into the external
**PREVIEW HARNESS · NOT PART OF THE DESIGN** area.

Only genuine user-facing controls such as Cancel, Resume, or Retry belong in
the application window. A user looking only at the app window must never see a
`Simulate` label or mistake prototype controls for VERA functionality.

## 7. Intentionally excluded

Do not add any of the following to S05:

- Changes in Resolve
- Review Resolve changes
- Adopt a Resolve edit into the script
- Conflict resolution between script and Resolve
- Preview versus Release
- S06 or a replacement navigation page

Resolve-side reconciliation belongs to a separate future authoring-mode design.
S05 shows only what VERA proposes to send to Resolve.

## 8. Verification

Exercise every scenario at both `1280 × 800` and `1024 × 768`.

Verify:

- every checkbox, mirrored checkbox, and independent-checkbox rule;
- both directions of every partial split/merge selection;
- warning, count, footer, action, completion, and manual-check consistency;
- zero-selected disabling;
- hover and keyboard-focus coverage behavior;
- new-image green and old-image dotted-red underlines;
- separate accessible old/current wording and ranges;
- S03 narration typography and row proportions;
- cross-section context above and below;
- Update row and the intentionally ignored-newer-version path;
- immediate one-click Create/Update timeline behavior;
- last-used render settings and saved-preset behavior;
- continuous section-range enforcement;
- interruption, resume, cancellation, failure, retry, and success;
- no simulation controls inside the user-facing application;
- no inbound Resolve review anywhere; and
- S04 unchanged and S06 still entirely absent.

Fix every inconsistency you find before reporting completion.
