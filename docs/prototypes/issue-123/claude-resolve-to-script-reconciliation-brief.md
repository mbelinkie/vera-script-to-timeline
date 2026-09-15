# Initial Claude Design brief — Resolve-to-script reconciliation from S03

> Historical input: this brief was sent before the Producer and Claude refined
> the row, layering, provenance, and post-recording decisions. The current
> instructions are in
> `claude-resolve-to-script-reconciliation-continuation.md`. Do not resend this
> initial brief as the current design direction.

Create one new, separate design artifact in the existing Claude Design project
`VERA design feedback`, named:

**Script to Timeline — Resolve-to-Script Reconciliation S03**

Do not edit the Producer-accepted artifacts:

- `Script to Timeline — Two-Column Authoring S01–S03 v2`
- `Script to Timeline - Prompter Runtime and Suite Navigation S04-S06`
  (the historical filename now contains accepted S04 and S05 only)

This is a successor design for an inbound reconciliation mode reached from S03.
It must preserve the accepted S03 and S05 design intent rather than redesigning
either artifact.

## Start with design judgment and questions

Do not begin editing immediately.

First inspect the accepted S03 and S05 artifacts closely. Reuse as much of the
S05 design as possible: its page composition, white script rows, typography,
script-order presentation, narration/production columns, compact row density,
red and green old/new treatments, non-color labels, filters, checkboxes, bulk
controls, selected/skipped counts, sticky action relationship, single-page
scrolling, focus treatment, and responsive reflow.

Then use your own product-design and interaction-design judgment to propose a
plain-language concept for this mode. Ask Matthew focused questions whose
answers would materially improve the design. Explicitly look for edge cases,
failure modes, confusing terminology, and interaction consequences that this
brief may have missed. You may challenge or refine the proposed presentation
while respecting the locked product decisions below.

Wait for Matthew's answers before editing. After the questions are resolved,
implement, exercise, and verify the design rather than merely describing it.
Continue to ask a focused question later if implementation exposes another
material ambiguity. This remains Producer review material, not acceptance.

## User job and authority model

This mode reconciles changes made in DaVinci Resolve back into the canonical
script. It is not a general list of every difference between script and
timeline, and it is not the outbound S05 Update timeline flow.

Internally VERA may compare:

1. the last applied immutable build;
2. the current managed Resolve timeline; and
3. the current canonical script.

The user-facing list shows only changes that originated in Resolve. Script-only
edits are already accepted as canonical and must not appear as approval items.
Only surface a script edit when the same script row was also changed in Resolve,
because that overlap needs an explicit warning and decision.

Never imply that Resolve is globally canonical, that every Resolve operation
can be translated into script form, or that a design simulation actually
observed or changed Resolve.

## Entry from S03

Add a clear, non-color-only changed-timeline status and dedicated reconciliation
button beside the established S03 Prompter/Resolve access. The message should
say in ordinary language that the managed Resolve timeline changed after VERA's
last update and those changes can be reviewed for the script.

Make the alert concrete by showing the number of timeline-originated changes
waiting for review. Design at least these examples:

- **Resolve timeline changed since VERA's last update · 6 changes to review**
  with a **Review 6 changes** action.
- A useful expanded or secondary breakdown such as **3 ready to apply · 1 needs
  a decision · 2 Resolve-only items will be recorded**.

The total counts each atomic timeline-originated change once and excludes
script-only edits. A move shown at two positions still counts once. Resolve-only
items are included in the total because the user should see and may name them,
even though VERA records their existence automatically. Keep the shorter alert
scannable; use your design judgment about whether the breakdown is always
visible or progressively disclosed.

Also design the no-change state. When the managed timeline matches the last
observed state, do not show a false count or reconciliation action. While VERA
cannot inspect Resolve, show an honest checking/unavailable state rather than a
stale count.

The new artifact may reproduce only enough of S03 to demonstrate this entry and
its no-change counterpart. Preserve the accepted two-column white-document
authoring composition and do not redesign S03.

## Review presentation

Treat S05 as the visual and interaction baseline, reversed in direction. Use
white script rows in script order—not a dashboard of abstract change cards.
Where relevant, retain the recognizable narration column on the left and
production/visual content on the right. Show old and current material with the
same clear red/green plus text/icon/pattern language used by S05.

Provide filters and counts for the timeline-originated states that are actually
useful. Do not include a Script changed filter or unchanged rows merely to make
the comparison look symmetrical.

Understood, non-conflicting Resolve changes are selected by default. A checked
row means its displayed Resolve-originated change will be represented in the
script. Selection and counts must remain accurate everywhere they appear.

Use **Reconcile script** as the primary action. Its accessible description and
confirmation should state how many Resolve changes will update the script, how
many script-wins decisions are being recorded, and how many conflicts remain
deferred. It never creates, duplicates, or updates a Resolve timeline.

## Same-row changes

Any row changed in both the script and Resolve gets a prominent non-color-only
warning, even when VERA believes the changes are compatible.

For compatible changes, require explicit **Combine both changes** confirmation.
Do not preselect or silently merge overlapping work simply because the changes
touch different properties.

For incompatible changes, select no default. Show these three choices with the
consequence directly under each choice:

1. **Keep current script — update Resolve next time**
   - Preserve the current script.
   - Record that this conflict was resolved in the script's favor so the same
     unchanged Resolve delta does not repeatedly return as an inbound conflict.
   - In the next S05 outbound review, select this row by default and explain
     that applying it will replace the conflicting Resolve version.
2. **Adopt Resolve into script**
   - Offer only when VERA has a safe, reversible script representation for the
     detected change.
   - State exactly what script content will change.
3. **Defer**
   - Change neither side.
   - Bring the conflict back in future inbound reconciliation.
   - Leave it unchecked by default in future S05 outbound review so VERA does
     not accidentally overwrite the Resolve edit.

Allow the user to finish other selected work with one or more deferred
conflicts. The completion state must say the script and timeline remain
partially out of sync and name the deferred count.

## Resolve-only content: a placeholder in reverse

Reuse the accepted Onscreen Placeholder card language, but make the reversed
ownership unmistakable:

- **Onscreen Placeholder** is authored in the script. It expresses future
  intent and VERA renders a visible stand-in in Resolve.
- **Resolve-only content** already exists in Resolve. VERA cannot safely express
  or rebuild it, so the script records a protected reference and future updates
  leave the real Resolve material untouched.

Do not call the new row a Timeline placeholder and never render its custom name
as a slate.

Whenever content is recognized but cannot be represented in script form, or is
ambiguous/unrecognized, automatically create a locked **Resolve-only content**
row. The user does not need to approve the fact that detected content exists.
The reconciliation result should report how many such rows were recorded.

Support both forms:

1. **Attached Resolve-only content**
   - Appears in the production/right column beside understood narration or VO
     when VERA has a trustworthy row anchor.
   - VERA may update understood material in the row but must not touch the
     opaque Resolve-owned item.
   - It moves only with a verified anchor.
2. **Standalone Resolve-only content**
   - Appears between the nearest trustworthy script rows when no safe row is an
     anchor.
   - Do not invent narration or an understood visual description.
   - It stays fixed during future outbound updates.

Every row keeps the permanent system label **Resolve-only content**. Offer an
optional editable descriptive name during reconciliation, for example
`Pre-made highlight reel`. The user may also rename it later in the ordinary
script. The name is explanatory metadata only: it does not raise VERA's
confidence, make the content adoptable, change Resolve, or become rendered
video text.

Show compact observed details such as timeline position, duration, track, and
anchor when available. Keep the row collapsed but visible in ordinary script
editing so it protects the timeline without dominating the writing experience.

Future outbound timeline updates must skip over this material in the sense of
preserving it unchanged—not omitting it. Continue updating understood content
around it, especially understood VO. If movement, overlap, ordering, timing, or
anchor changes make preservation ambiguous, block the affected operation and
require review instead of guessing.

If the referenced material is missing or cannot be verified, warn or block. Do
not substitute an Onscreen Placeholder or any other generated slate.

If a later comparison can verify that the editor deleted the real content in
Resolve, show a preselected proposed removal of the corresponding script row.
Applying reconciliation removes the row while retaining its descriptive name
in reconciliation history.

## Post-presenter timing review

Recorded presenter footage changes the narration timing source. Ordinary
VERA-understood, word-anchored B-roll is recompiled against the words the
presenter actually spoke. Resolve-only content is different: VERA may know its
intended in-word and may understand the surrounding voiceover, but it cannot
safely trim, stretch, move, or otherwise edit the opaque footage.

When a recorded conform changes the compiled time of an anchor governing
Resolve-only content and VERA cannot verify that the existing edit still fits:

- preserve the Resolve-only media exactly as it is;
- do not silently retime, trim, stretch, freeze, loop, or move it;
- add or update one stable VERA-owned **manual timing review** marker at the new
  calculated word anchor in the new timeline;
- name the affected Resolve-only row, using its custom name when present; and
- explain that the editor must check the media's start and ending against the
  recorded presenter timing.

Use a concrete example such as **Timing review · Pre-made highlight reel** at
the newly calculated in-word. The marker note can identify the intended word or
phrase, the preserved current placement, and the timing difference when VERA
knows it. It is an editorial instruction only and never appears in rendered
video.

This is a distinct marker purpose, not an Onscreen Placeholder, not a duplicate
Resolve-only script row, and not an editor-created marker. Repeated builds must
update the same marker by stable identity rather than accumulating duplicates.
If the recorded timing causes no material timing impact and preservation is
verifiably safe, do not create a needless warning marker. If the intended anchor
itself is missing or ambiguous, block the affected operation for review instead
of placing the marker at a guessed location.

Use your design judgment and ask Matthew questions about the marker's visual
treatment, wording, completion/dismissal path, and how much timing detail is
useful. Demonstrate the marker in both the relevant script/update explanation
and a simple representation of the post-presenter Resolve timeline so the
relationship is understandable without turning the artifact into a timeline
editor redesign.

## Required scenarios

Choose concise fictional content and use your own design judgment to make the
states coherent. The artifact must make it possible to inspect:

- S03 changed-timeline entry and no-change states;
- S03 count examples showing the total changes to review and a useful breakdown
  of ready, decision-required, and Resolve-only items;
- an understood, non-conflicting Resolve change selected by default;
- a compatible same-row change requiring explicit Combine both changes;
- an incompatible same-row change with all three choices and no default;
- attached recognized-but-unrepresentable Resolve-only content;
- standalone ambiguous/unrecognized Resolve-only content;
- optional naming with `Pre-made highlight reel` as one example;
- the collapsed Resolve-only row in ordinary script editing;
- a future S05 update preserving Resolve-only material while updating
  understood VO around it;
- a post-presenter conform where understood B-roll retimes to recorded words,
  Resolve-only media stays untouched, and one manual timing review marker lands
  on the newly calculated word anchor;
- repeated post-presenter updates replacing that marker rather than duplicating
  it, plus an ambiguous/missing-anchor case that blocks instead of guessing;
- the distinct future effects of script-wins and defer;
- a verified Resolve deletion proposed as a selected row removal;
- an ambiguous preservation collision that blocks rather than guesses;
- partial completion with deferred conflicts and accurate out-of-sync status;
- unavailable Resolve/local helper and readable observation failures;
- keyboard focus, non-color meaning, long-content wrapping, and narrow-screen
  reflow.

If your design exploration reveals another material state or edge case, raise
it with Matthew and include it when agreed rather than limiting the design to
this list.

## Responsive, accessibility, and simulation boundaries

Exercise the full experience at internal `1280 × 800` and `1024 × 768`.
Preserve one vertically scrolling page, visible keyboard focus, logical
Tab/Shift+Tab order, native control semantics, readable non-color status, and no
horizontal overflow. At the narrow viewport, reflow row content without losing
the narration/production relationship or the connection between a decision and
its consequence.

Keep every action simulated. Do not create or claim production Resolve
inspection, sync, diffing, script mutation, persistence, authorization, local
helper behavior, timeline building, APIs, schemas, contracts, fixtures, golden
files, generated types, or shared-system changes. Use no private content,
credentials, real media, or local paths.

## Return after implementation

After questions are resolved and the design is implemented, return:

- the exact new artifact filename and link;
- confirmation that both accepted source artifacts were preserved;
- how the design reused S05 and where it intentionally diverged;
- the states exercised at both viewports;
- keyboard, focus, non-color, and overflow results;
- additional edge cases you discovered and how they were resolved; and
- any remaining Producer decisions or blockers.

Stop after this successor design. Do not begin the technical reverse-mapping
story or any production implementation, and do not imply Producer acceptance.
