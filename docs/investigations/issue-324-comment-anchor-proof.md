# #324: bounded S03 comment mechanics

This is a sequential authoring-domain proof for [#324](https://github.com/mbelinkie/vera-script-to-timeline/issues/324),
not the Phase 3 comment service. The public synthetic tests use two narration
rows, one clip card and an on-camera row appearance. No Resolve operation,
private media, provider or service is involved.

## Reusable entry points

`@vera/contracts/authoring-v2` exports `createCommentStateV2`,
`applyCommentOperationV2`, `serializeCommentStateV2`,
`deserializeCommentStateV2` and the `Comment*V2` types. Implemented in
`packages/contracts/src/authoring-v2-comments.ts`.

Comment state owns a materialized script value, threads and an attributed
operation log. The script schema is unchanged. Discussion never enters that
script value: create/reply/resolve/reopen/reattach advance only the local
comment revision. The caller supplies stable actor, operation, thread and
message IDs. Actor IDs are attribution inputs, never permission evidence.

Every command requires the exact current local comment revision and a new
operation ID. Thread IDs and message IDs must be unique within the state.
Repeated resolution, reopening an open thread, reattaching an attached thread,
an unchanged document replacement, missing targets and stale revisions refuse
atomically, returning the original state and history. A duplicate operation
refuses even if its payload is identical; this is not a network retry protocol.

## Exact supported limits

| Anchor | Bound identity and survival | Becomes stale when |
| --- | --- | --- |
| Text | One active-draft narration row, inclusive stable token endpoints; all interior token IDs/values and exact quoted text retained | Any selected token is lost, reordered, inserted, rewritten or replaced; quoted text changes or offsets stop resolving |
| Card | Active-draft narration block ID and primary sequence **content slot ID**, not payload identity or screen ordinal | Block or content slot disappears, including a move to another row |
| Block | One active-draft block ID, including a section | Block disappears from active Draft |
| Between blocks | Exact ordered adjacent active-draft block IDs, with no start/end sentinel | Pair ceases to be adjacent in that order |

Text outside the selected range can change while stable selected identities
survive. Row moves use the existing `applyRowEditV2` and preserve text/card/block
bindings; breaking a gap stales its thread. Card payload edits retain slot
identity. No text search, nearest-row rule or guessed placement repairs an
anchor. Old evidence remains on stale threads. Restoring identical words or
the old adjacency does not clear staleness. Only an explicit `reattach` to a
currently resolvable supported anchor restores it, retaining thread/message IDs.

`replace_document` accepts a schema/identity-valid local authoring value for
the same document/project, then rechecks attached anchors in one transaction.
It is the explicit integration seam for existing text/row edit functions;
calling an edit outside this state cannot update its threads. It does not
implement text editing, undo, stale concurrent script rejection, narration
regeneration or collaborative transactions. Unresolved authoring intent can
remain in the script, as in the existing authoring save/load APIs.

Save/load is a versioned JSON value round trip of the initial document and
accepted operations. Loading validates and replays the entire log; bad commands
throw without exposing a partial state. Saving verifies that replay recreates
the materialized state. This deliberately small proof retains full document
values for content edits in history. It is not a storage/compaction strategy.

## Executable evidence and downstream handoff

`packages/contracts/test/comments-v2.test.ts` covers all four anchors,
attributed create/reply/resolve/reopen, mentions of one injected stable actor,
text edits, actual row moves, deletion/rewrite, sticky staleness, explicit
reattachment, save/load and atomic refusals.

`packages/contracts/test/comment-consumers-v2.test.ts` compares the actual
`projectPrimarySequenceV2`, `exportPrompter`, `compileTimelineV2` and
`resolveMediaRequirementsV2` results after each comment-only command and reload.
The two-row fixture has 192 frames and one visual media requirement. Exact
prompter bytes/sidecar, projected narration, full compiler output/duration and
media needs must remain equal, including the script's original build identity.

For #74: reuse the pure operations and identity/stale rules, then provide the
service transaction/storage boundary. For #72: authenticate and authorize the
injected actor outside these functions. For #73: supply real collaborative
relative positions and integrate script/comment updates atomically. This proof
does **not** establish authentication, roles, revocation, concurrent convergence,
durable persistence, mention delivery, a finished editor or any UI.

The spec's Idea/Extra anchors, arbitrary card kinds, cross-row text ranges,
boundary sentinels, edit/delete-message operations and collaborative relative
positions remain unimplemented here. The S03 functional promise cannot be
cleared unchanged from this sequential proof alone; #74/#72/#73 still own
those missing mechanisms. No #125/#128 design work is resumed by this result.
