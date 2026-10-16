# Producer clarification: row audio and the prompter checkpoint

Source: Matthew Belinkie's instructions in the #144 implementation task on
2026-10-03. This records adopted behavior; it is not implementation acceptance.

1. Each narration row is one logical temporary-audio replacement unit. Any VO
   wording change, including a simple accepted cut, invalidates that row's
   current recording and requires a newly generated recording of the whole row.
   No splicing or concatenating fragments of the old row recording.
2. Fresh timing comes from the replacement recording. Recalculate all anchored
   cuts in the row and subsequent timeline positions affected by its duration;
   regenerated delivery can change pacing throughout the row.
3. Prompter generation is the checkpoint for locking/warning on left-side
   authoring edits. This starts before a real presenter recording is imported.
4. Explicitly overriding the warning to change row VO regenerates the complete
   row's temporary recording and signals the need for a reshoot. Existing takes
   and old builds remain historical; their approval must not silently transfer
   to changed wording.
5. A future feature exports prompter material only for rows changed since the
   last prompter script. The comparison baseline is the last export, not the
   last audio import or build. Detailed selection/context/export semantics need
   a separately bounded design and acceptance slice.
6. Subsequent Producer framing: each row is a self-contained box. Narration
   and visuals are row-local; changing VO regenerates and retimes only that
   row, and a visual adjustment affects only that row. Music is an explicit
   exception that may span rows. A duration change translates later boxes in
   the assembled timeline without regenerating their audio or changing their
   internal cuts. Building the timeline validates the boxes individually and
   joins them in order, with separate checks for spanning music.
7. A conceptual per-row pre-comp helps distinguish altered rows, rearranged
   rows and untouched rows. Actual nested timelines are not required: the
   delivery should remain practical for a human editor. Rearrangement changes
   placement, not the contents of an untouched box.

## Consequences for #144

The old proposed lossless-splice narration route is withdrawn. No omission
rebuild or splice implementation had been completed. Finished visual semantics
do not change narration text and remain useful for identifying accepted anchors
against the old baseline. A wording-edit rebuild subsequently recompiles against
replacement audio, rather than forcing old edited frame geometry to survive.

PreparedBuild currently verifies local narration inputs, not generation. The
new whole-row generation/preparation handoff must be reviewed and implemented
before claiming an integrated positive omission rebuild. Synthetic generation
in #144 must be labeled as injected evidence; #145 needs the actual authorized
whole-row recording and fresh timing. This policy alone authorizes no paid/cloud
provider use, no current-project mutation and no frozen-contract changes.

## Scope and assumptions to expose to the Producer

- “Change the row” is interpreted here as changing its VO content. Visual-only
  edits still modify their visual anchors/source ranges without replacing
  unchanged narration. This interpretation should be visible in the summary.
- A row's duration change can move later rows' absolute starting positions;
  it must not regenerate or internally retime those unaffected rows. Their
  existing audio, relative cuts and source ranges stay intact. Cross-row music
  must be checked against the new assembly rather than assumed unchanged.
- #144 creates and verifies a fresh timeline through accepted assembly. Equal
  untouched-row content is not proof of reusing native timeline objects or
  retaining all human refinements in the new target. Preserving compatible
  Resolve-owned work during selective updates is production #104 scope and
  must not be claimed by the current harness.
- A Resolve cut proposes a script omission only after verified audible absence
  and an explicit accept decision. It never silently changes wording.
- The warning/lock UI, reshoot state and changed-row prompter export are future
  authoring/recorded-workflow work, tracked in Inbox
  [#153](https://github.com/mbelinkie/vera-script-to-timeline/issues/153), not
  frontend implementation inside #144.
- Existing post-shoot rules retain unchanged recorded-beat approvals. The
  Producer has specified whole-row temporary-audio replacement and a reshoot
  indication; whether a changed row must replace every unchanged recorded beat
  in a later conform remains a separate product decision, not an implied
  deletion of historical approvals.

## Authoritative-spec comparison

Section 8.3 already defines per-block replacement and stale-input regeneration.
Section 6.15 already recomputes text anchors against the chosen recording and
marks changed spoken wording stale. The clarification adds an explicit
post-prompter edit guard and full-row replacement policy; the old #144 splice
proposal and exact old-duration timing assumption conflict and are withdrawn.
The left-side lock's exact controls and the interaction with retained unchanged
recorded beats should be resolved in the owning authoring/conform design.

Claude checkpoint 7 and its row-box follow-up confirmed the corrected rule and
the existing compiler's block-local timing/sequential assembly. The follow-up
withdrew the initial suggestion to limit temporary regeneration to pre-approval:
an explicit post-prompter edit can bind new temp VO to a new revision without
overwriting any prior locked human recording. No additional #144 product
decision was raised. Spanning music and actual preservation of untouched human
refinements remain outside this proof's implemented capabilities.
