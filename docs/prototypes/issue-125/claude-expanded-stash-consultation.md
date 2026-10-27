# Expanded Stash — CLI consultation brief

Prepared 2026-10-27. Consultation only; not submitted to Claude Design.

Canonical adopted behavior and test inventory: [#62 amendment](https://github.com/mbelinkie/vera-script-to-timeline/issues/62#issuecomment-6447015057), IDs S03-STASH-001–007 and S03-TEXT-001–004. #125 consumes this record; do not create a second competing feature inventory.

## Prompt

Act as an adversarial product co-designer. Critique this expanded Stash brief
before any visual construction. Do not edit files or build a prototype. The
question is how much #125 must settle now, given that later supporting design
belongs to #59. Challenge that boundary if it would force an S03 redesign.

### User and purpose

A writer starts with a compact outline of ideas, reminders, prospective VO and
clips, then gradually turns that material into a script. The same Stash also
holds script rows temporarily removed from the active script. The writer must
be able to think in an outline without constructing two-column rows first.

### Adopted product behavior — preserve it

- One unified Stash contains compact text notes, standalone clips and complete
  script rows. Existing Stash sections remain an organization tool. Separate
  user-facing Ideas and Extras surfaces are superseded.
- Notes support indented, collapsible subnotes. Notes are compact outline
  entries, not miniature full script rows. Complete saved rows use compact
  summaries; clips use a compact clip representation. No attached-footage note
  category is required.
- Stash is accessible from normal authoring and Sorting. Reuse the existing
  Show Stash sidebar, wide inspection and ordinary-authoring editing direction.
  Do not reconstruct accepted S03 rows, Sorting or comments.
- Dragging an item to an explicit script gap moves it out of Stash. It does not
  leave a checked-off original. A clip becomes a footage row; an existing row
  retains its complete content, identity and attachments within supported limits.
- A text note becomes a row whose text preserves its spoken/direction meaning.
  A note can mix prospective spoken text and nonspoken directions.
- Producer clarification: plain notes become nonspoken stage directions by
  default, keeping planning material distinct from narration. Preserve explicit
  spoken intent where the writer has already converted it; do not adopt the
  CLI reviewer's plain-notes-are-spoken recommendation.
- Dragging a parent note moves the parent and descendants together into a group
  of rows in outline order. Text and clip descendants become corresponding rows.
  Indentation never automatically creates script sections. This placement does
  not authorize a permanent mandatory bundle of script rows.
- Returning converted material to Stash without editing it restores its outline
  form. Once authored changes have been made, it returns as a script row. Keep
  origin/hierarchy information sufficient for the untouched return; this is not
  permission to link all future script-row moves as a mandatory bundle. Whether
  the row has been edited is part of Undo: fully Undoing the edit restores its
  previous outline-return eligibility. Ordinary manual rewriting back to the
  original words is not automatically declared equivalent to Undo.
- Producer clarification on partial return: an untouched child whose parent is
  still in the script returns as a top-level note in its original Stash section.
  No placeholder parent or new section is created, and no unselected parent or
  sibling is pulled from the script. If the parent is already in Stash, return
  the untouched child to its original nested slot.
- Square brackets mark nonspoken stage directions. Parentheses remain ordinary
  spoken text. For an existing paired direction, deleting either delimiter
  removes its partner, retains the enclosed words and converts them to speech.
  Make stage direction wraps selected words. Undo reverses the text/classification
  change together. This writing control belongs in normal script and Stash.
- Quotes are not a parser or requirement for prospective VO. Do not infer spoken
  status from literal quotation marks. Do not add a new script text type.
- Content remaining in Stash is excluded from the active script's ordinary
  narration, prompter, build and exports. Placement does not silently repair
  timing/media/transition relationships or update Resolve.
- Saved rows remain independently restorable. Producer clarification: notes and
  clips CAN be placed from Stash during pending Sorting. Do not depict placement
  as blocked merely because #310 currently lacks conversion support; record the
  missing proof. Any expanded script row in Sorting supports full authoring, not
  only newly placed notes. Writing and organization share the same pending
  session: Accept keeps both, Discard reverses both. Existing script-format
  preview remains read-only; Return to Sorting retains the pending edits. Do not
  imply that Discard undoes irreversible external media/service operations.
- Producer follow-up: Accept remains the default and keeps all changes. An
  adjacent dropdown contains only Keep edits, undo sorting and Keep sorting,
  undo edits. Discard all is a separate button, never a dropdown item. Edits-only
  restores original placement while retaining
  authored edits. Specifically, a note taken from Stash, edited in the script,
  then accepted as edits-only returns to Stash as an edited script row. Do not
  restore its old note content, lose the edits or leave it in the active script.
  Selective acceptance needs separate executable proof, including newly created
  or deleted rows and relationship/attachment consequences; full-result #310
  acceptance alone does not establish this behavior.
- Producer classification: deleting a script row is an EDIT. Keep edits, undo
  sorting preserves deletion; Keep sorting, undo edits restores the row. Preserve
  existing deletion confirmation/Undo and quiet orphaned discussions. Deleting a
  script row never deletes source media.
- Product copy uses content rather than row numbers. Bold continues to mean
  On Camera. Comments retain one discussion per target and the selected sidebar;
  do not add planning-specific comment semantics here.

### Current authority and capability limits

Current visual references, not a mandate to edit: the existing VERA design
project's S03 Outline Sorting Comparison r14 working successor and S03 Comments
Placement Comparison r1.dc.html (selected S03-C r2 sidebar surface), based on
Shared S03 Review Foundation r11. Reuse actual latest sources when construction
is separately authorized; do not reconstruct them from this brief.

This consultation receives a textual brief, not those HTML files or screenshots.
Do not claim to have inspected their appearance or invent measured layout facts.

- #307/#310 provide executable evidence for bounded row/section moves,
  saved-row Stash operations, local Undo, Sorting preview/Accept/Discard and
  editing saved row content outside Sorting. These are not proofs of nested
  planning notes or clip/note-to-row conversion.
- #310 specifically allows only structural commands in a pending Sorting
  session. The newly required conversion/untouched outline return, and proposed
  content editing with transactional Accept/Discard, need expanded executable
  proof; the old read-only rule is an implementation limit, not a reason to
  override the Producer's new placement requirement.
- Open #337 owns independent saved-row restore and optional Stash sections.
  It does not currently cover note hierarchies or the new conversions.
- #324 provides a bounded comment-anchor baseline, not a new cross-app service.
- Corrected first-interruption music behavior remains under open #326. Do not
  expand that interaction or use old starting-row-only shortening as equivalent.
- Stage directions exist in the product model and rendered examples. A working
  create/convert/pair-delete interaction was not found in the retained S03 source.
  These new editing/Undo promises still need exact executable proof.
- #59 owns later supporting planning/collaboration design; #77/#78 are existing
  later implementation placeholders requiring reconciliation with unified Stash.
  #62 owns the complete behavior inventory, #125 S03-facing design and #126 its
  later alignment. These owners are not prerequisites for their own proofs.

No new working depiction of an unproved operation is authorized by calling it
simulated. This is consultation and prompt preparation only. Identify the minimum
missing proof; do not demand a finished backend or repeat delivered row proofs.

### Proposed scope split — critique this

In #125 now: settle the S03-facing contract and smallest representative
integration treatment: mixed compact sidebar contents, identifying a note versus
a clip versus a saved row, inspection/access from normal writing and Sorting,
explicit placement and parent-branch result, spoken/direction editing affordance,
and how existing pending Sorting restrictions constrain those actions. Establish
the required states and exact proof gaps before asking for working construction.

Later #59: full focused planning workspace and comprehensive outline-authoring
flow (create/edit, indent/outdent, section/branch organization), broader role,
collaboration/save/offline/error states, reusing #125's chosen S03 contract.
Production UI/persistence/conversion implementation remains separate.

This split is a recommendation, not a Producer-approved scope deferral. If an
essential creation/organization interaction must be settled now to make the
sidebar honest, identify the minimal addition rather than silently postponing it.

### Unresolved product decisions — do not make them for the Producer

1. The compact appearance/input of default-direction notes. Their default
   nonspoken meaning is now settled; do not ask the Producer to choose speech
   versus directions again. Exact bracket affordance during note entry must fit
   that default without making every reminder look like a full script row.
2. Incomplete bracket typing/paste, literal/escaped or nested brackets, and when
   typing commits a direction. Existing-pair deletion does not settle these.
3. Untouched converted material DOES recover its outline form; edited material
   returns as a row. Undo restores previous outline-return eligibility. Still
   unresolved: fine input/attachment boundaries, complete mixed-branch recovery
   interactions and empty-parent behavior. The parent-present versus parent-absent
   child-return rule above is settled. Existing script rows remain independent;
   do not invent persistent mandatory bundles or script sections.
4. What the Stash count means with notes, clips and rows together. The earlier
   count of saved rows cannot silently become a misleading total.
5. Full editing of any expanded script row during Sorting is now adopted; all
   session writing/organization stays pending together, with read-only
   script-format review, default Accept-all and the selective-acceptance dropdown
   above. This is no longer a product question, but its expanded domain/session
   proof is still missing. Row deletion is an edit, and the edited-note-to-Stash
   and child-return cases are settled. Remaining dependency/conflict results need
   consistent dispositions before construction. Do not describe the older
   structural-only session as sufficient evidence.

### Smallest representative scenario and evaluation

Use one Stash section containing:
- Parent note: Explain the sensor.
- Child: a prospective spoken sentence, This instrument measures the water every
  thirty seconds, plus the direction [hold up the notebook].
- Child: standalone Sensor housing at the waterline clip.
- An unrelated saved script row with an existing comment and citation.

Evaluate compact recognition without expanding every item; insertion of one note,
one clip and the parent branch; preserving the unrelated row's contents; and the
return-to-Stash/hierarchy ambiguity. Include empty Stash, a missing clip, keyboard
placement, cancellation/Undo and an already pending Sorting session. Use
1280×800 and 1024×768 when eventually comparing layouts; preserve the adopted
ten-row Sorting density target. No audio asset, playback, actual build or Resolve
operation is needed for this consultation.

### Requested response — keep it bounded

1. At most six substantive problems, each with a concrete user sequence and the
   smallest correction. Separate adopted requirements from recommendations.
2. Recommend the exact #125-versus-#59 boundary, including anything that cannot
   safely be deferred. State whether full Stash design is being smuggled into #125.
3. Give the three most consequential Producer questions, with a recommended
   answer and tradeoff for each. Do not treat your answers as adopted.
4. Recommend the smallest focused comparison/pilot after decisions and proof.
   Propose materially different compact treatments only if the hierarchy really
   needs comparison; do not generate new numbered pages, full-app designs or exports.

Stop after critique. No design-app submission or implementation.

## Initial CLI consultation outcome and disposition

Historical consultation below preceded the Producer clarifications now included
in the prompt above. It is not authority to reopen settled defaults, block Stash
placement or general script-row editing during Sorting, or assume outline
hierarchy is never recovered. Adopted later decisions also supersede its
statements that Undo eligibility and full-authoring/Accept/Discard are unresolved.

One tools-disabled Opus/high subscription consultation completed 2026-10-27.
It received this textual brief only; no live artifact inspection or edits.

- Carry forward: #125 needs a coherent compact sidebar contract, including the
  location of Add note, basic indent/outdent entry, count meaning, placement
  results and the rule during pending Sorting. A later full planning workspace
  must reuse that contract. This is a recommended split, not a newly approved
  deferral or permission to render unproved operations.
- Carry forward as unresolved: note speech/direction defaults, hierarchy on
  return to Stash, and whether note/clip conversion participates in Sorting's
  Accept/Discard session. Existing row operations do not prove these additions.
- Carry forward as proof needs: note/clip/branch conversion and atomic Undo;
  paired direction editing/Undo; keyboard placement; active-output exclusion.
  Reuse existing row evidence without claiming that it covers the new types.
- Correct a reviewer misreading: the parent itself already becomes the first
  row. The unresolved issue is its text's speech/direction meaning, not whether
  it is included. Separate clip descendants become their own rows; automatic
  attachment to a neighboring narration row is not adopted.
- Do not adopt the reviewer's claim that hierarchy recovery necessarily means
  permanent mandatory bundles. Provenance-based recovery and independent rows
  are technically compatible; product intent remains unresolved. One-way
  conversion with exact immediate Undo is a recommendation, not settled policy.
- Do not silently adopt recommendations that plain notes/unmatched brackets are
  spoken, that only saved rows count, that missing clips are placeable, or that
  note/clip placement is disabled during Sorting. Defaults require a Producer
  decision; any missing-media action stays within existing supported limits.
- Do not accept the suggestion to skip comparison merely because the items
  share a list. Compact mixed-item hierarchy and input mechanics are not yet
  Producer-selected. After decisions/proof, use the required focused comparison
  if information hierarchy or interactions remain open, then one bounded pilot
  at both viewports. No full Stash redesign is authorized by this consultation.

No Claude Design submission, numbered artifact, export, new issue, dispatch,
production implementation or capability clearance resulted. The adopted source
remains #62; these reviewer recommendations do not change it.
