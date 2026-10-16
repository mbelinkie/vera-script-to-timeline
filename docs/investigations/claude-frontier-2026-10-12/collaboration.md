# Claude engineering frontier review — collaboration

Advisory review, 2026-10-12. Model: claude-opus-5-5; session: 881907b5-a44d-4474-bea2-4d1a72f73913. Public issue-body packet only; no code/runtime inspection or implementation.

Steward limitations: Claude returned text wrapped in pseudo-tool calls; tools were disabled and those calls were not executed. Only the advisory content is retained. #125/#73 and related future scopes remain open, not accepted implementation/design outcomes. Yjs behavior and #172 arbitrary-merge validation require primary code/documentation checks; no missing contract or automatic-repair defect is proven by this packet.

## Retained Claude response (unverified recommendations)

# VERA collaboration-lane advisory review (read-only)

## Context
This is a bounded advisory review in the collaboration lane, requested by the Producer. It asks whether the accepted pure single-writer authoring layer (#172, closed) can support planned multi-client work: #73 live editing and undo, #74 anchored comments, #75 history and restore, and #72 roles and revocation. The constraints are #64 Q1 persistence, #125 S03 semantics and the #153 prompter guard.

- **Evidence:** only the supplied issue bodies. No repository, no #62/#147/#156/#140/#59 text and no samples were available.
- **What "V1" means here:** Q1 single-writer, per the #147 refinement on #72: "Live presence/comments/history extensions stay A1." This mapping is unverified.
- **No defect claims:** nothing below alleges a bug in accepted #172. The findings are issue-scope gaps or proposed pre-code acceptance gates for the steward.

## Bottom line
Yjs convergence plus per-user undo is **not sufficient**.

- Convergence only guarantees that all replicas end up with the same state. It does not guarantee that state passes #172's validator or #125's identity and no-silent-deletion rules.
- What is missing is a semantic commit boundary with four steps:
  1. Authorize the actor against the current epoch.
  2. Validate or classify the merged state with #172.
  3. Apply #125 §4 linked multi-item sets atomically.
  4. Produce an explicit outcome plus an attributed record.
- No supplied issue owns this boundary. #125 explicitly excludes "collaboration merge" and the "anchor/transition/timing repair engine". #73 names only Yjs, merge and undo.
- One item is a real V1 blocker: head revision and writer epoch in #64. The rest are A1 pre-code gates.

## Findings

### F1 — High — A1 pre-code blocker for #73 — Missing semantic commit/repair boundary — **Missing**
**Evidence**
- #172 requires "deterministic success/refusal tests" for "refused mode/destination changes, null/stale/equal/crossed bounds, Unplaced promotion and inconsistent two-of-three inputs."
- #125 §4: "Identify linked multi-item updates that review must treat atomically."
- #125 §6 distinguishes "identity-preserving moves" from "new-identity duplicates" and states "no claimed automatic repair." Its acceptance criteria require moves, duplicates and parking "without silent deletion/repair."
- #125 excludes collaboration merge. #73 names only Yjs collaboration and reconnect/merge.

**Gap:** #172 commands check preconditions against one base. A CRDT merge never refuses. So a merged state can contain conditions #172 would have refused, even though no actor was ever refused.

**Failure scenario:** see the proof below. A row silently vanishes, or appears twice with the same ID, after two valid concurrent reorganizations.

**Minimal safe next action:** before #73 is Ready, its plan must do three things.
- (a) Name an owner for concurrent structural-edit semantics, and decide which #172/#125 operations are server-sequenced commands and which are CRDT-merged fields.
- (b) Adopt a pairwise concurrency acceptance matrix. For every pair of {#172 structural command, #125 move/park/duplicate/section move, transition-boundary edit, cutaway-bound edit} from a common base, the merged head must either satisfy I1–I4 (below) or land in an existing named #172/#125 state that both actors can see: refused-as-conflict, stale, Unplaced, or missing neighbor.
- (c) Do a read-only check of #156 plan §4/§7: is #172's validator/resolver total over arbitrary documents, or only over command outputs?

### Minimal technical proof
**Setup.** Base state: S1=[R, N], S2=[]. Transition T sits on the boundary (R, N).
- Actor A moves R from S1 to S2.
- Actor B, offline, deletes S2 (or parks it).

**Serially, either order is valid and explainable:**
- A then B: B's delete sees R inside S2, and #125's affected-content warning names R.
- B then A: A's move is refused because the destination is gone (#172 "refused … destination").

**Merged, representation α** (nested sequences, move = delete+insert; no atomic move primitive is in evidence):
- R is deleted from S1 and inserted inside the deleted S2, so R is reachable nowhere.
- Nobody deleted R. This violates I2 and #125's "no silent deletion".

**Merged, representation β** (flat rowId→{parent, orderKey}, last-writer-wins per field):
- R.parent = S2, but S2 no longer exists.
- The renderer must either hide R (silent deletion), resurrect S2, or relocate R (silent repair). Each is a product decision that convergence does not make.

**Corollary.** If A and C concurrently move R to S2 and S3:
- α produces two rows carrying R's ID, violating I1 and #172 stable IDs.
- β silently discards one actor's move.
- In both, T's (R, N) boundary is no longer adjacent. #125 §4 requires this to surface as "missing neighboring event", not be retargeted.

**Refutation test.** Take two replicas of the chosen representation, apply A and B, and merge both directions. The finding is refuted if the merged state satisfies I1–I3 and both actors see the outcome without any post-merge semantic pass.

### F2 — High — A1 pre-code blocker — Per-user undo is item-level, not semantic — **Missing**
**Evidence**
- #73: "per-user undo for script authoring."
- #172 defines commands with refusals.
- #125 §4 requires atomic linked updates.
- #64's #147 refinement: "preserve authorized head."

**Failure scenario** (assuming α):
- A moves R. B then edits R's narration in its new location. A undoes.
- An item-level inverse deletes the inserted R, including B's edit, and restores the original R with its pre-move text.
- B's wording change is silently reverted. Under #153's whole-row rule, this triggers temp-VO regeneration for text nobody chose.
- Separately, undoing part of a #125 linked set (the move reverts, the transition re-link does not) leaves an unexplained boundary.

**Next action:** the #73 plan should define the undo unit as one accepted semantic command, including the whole #125 linked set.
- Undo is a new forward command, validated against the current head.
- If dependent concurrent edits make it invalid, undo is visibly refused and names the blocking edit.
- **Test:** in the scenario above, B's edit survives, or the undo is visibly refused.

### F3 — High — **V1 (Q1) blocker** — Single-writer head integrity is unspecified — **Partial**
**Evidence**
- #64: "single-writer app shell … durable typed document persistence."
- #64's #147 refinement: "Retry/reload/permission loss must preserve authorized head and expose failures."
- #72's #147 refinement: "current permission checks and prompt session revocation even before collaboration."
- Both issues exclude "destructive migration."
- The intent is stated; the mechanism is deferred to plan refinement. That is expected for a placeholder and is not a defect.

**Failure scenarios**
- Two tabs, or a reconnect after a network split. Tab 2 saves state based on revision 7 after tab 1 has committed revision 8. With whole-document replace and no base precondition, tab 1's rows vanish with no error.
- A writer is revoked at t0. An in-flight retry at t1 commits because the role was checked only at session start.

**Next action:** #64's plan acceptance should require:
- A monotonic head revision.
- Every write carries the expected base revision, the actor, and the session/writer epoch.
- A mismatch produces an explicit conflict. There is no merge in Q1.
- Revocation bumps the epoch, so retries fail closed. Unsaved local edits stay visible as rejected; they are neither committed nor silently dropped.
- Each accepted write retains actor, base and a #172-level change record. This part is recommended rather than strictly blocking: it is cheap now and lets #75 attribution and semantic comparison extend Q1 history without destructive migration.
- **Tests:** a stale-base write is rejected, and a post-revocation retry is rejected. In both, the head is unchanged and a visible error is shown.

### F4 — Medium-High — A1 — Authorization and epoch-gated state at replication ingress — **Partial**
**Evidence**
- #72: Producer/Editor/Viewer roles, "Writer/Viewer/Release authority," "current permission checks," "prompt session revocation."
- #75: "approval labels."
- #153: "Prompter generation begins the left-side authoring lock." Unresolved there: "per edit or per session" and "state persistence and recovery."

**Gap:** a replicated document applies whatever updates reach it. Client-side role checks cannot constrain stale offline queues or crafted updates. No per-field CRDT authorization is in evidence, and none is assumed here.

**Failure scenarios**
- (a) An Editor goes offline, edits rows, and is demoted to Viewer. On reconnect, the queued updates merge into the authorized head.
- (b) B rewords VO offline before A's prompter export. B's update arrives after the lock, so there is no warning or override and no reshoot indication. The #153 guard is bypassed.
- (c) An Editor client writes a Producer-only approval-label field.

**Caveat (unverified library behavior):** rejecting one update probably invalidates that client's later causally dependent updates. If so, rejection must reset the client to the authorized head and surface its rejected local edits.

**Next action:** the #73 plan should do two things.
- List the server-only state that only authorized commands may mutate, never CRDT writes: roles, approval labels, release authority, prompter lock epoch, last-prompter baseline, build pins.
- Check every update at ingress against the actor's current role, writer epoch and lock epoch.
- **Tests:** (a) and (c) leave the head unchanged with a visible rejection. (b) routes through #153's accepted override once that design exists.

### F5 — Medium — A1 (#74/#75) — Anchors and restore need domain identity; dependency edges are missing — **Partial**, plus issue-scope contradiction
**Evidence**
- #74: "anchored … stale handling, and no build leakage"; its only listed dependency is #62.
- #125 §5: "stale/ambiguous-anchor reattachment" across "edits, move, duplicate, section moves and scratchpad parking."
- #125 §2: "distinct logical/occurrence identities from #140."
- #75: "semantic comparison," "restore-as-new-head."
- #73, #74 and #75 each list only #62.

**Failure scenarios**
- (a) Comments anchored to raw CRDT text positions under α moves either go falsely stale on every move or get reattached to the nearest text, possibly another author's content. That is the automatic repair #125 rejects.
- (b) Duplicate-as-new that silently copies a thread leaks it to a new identity.
- (c) A restore applied as diff operations while B edits concurrently yields a head that is neither the checkpoint nor B's view. It is non-destructive, but it is not a restore.

**Next actions**
1. For the steward (metadata only): consider adding dependency edges #73←#64, #72, #172/#156, #125; #74←#73, #125; #75←#64, plus #73 if history spans multiple writers.
2. #74's anchor should be {logical/occurrence ID, intra-row anchor, content fingerprint}. On mismatch it becomes stale or ambiguous with an explicit, attributed reattach.
3. #75's restore should be one semantic command against an explicit head revision. Concurrent edits produce a conflict, not an interleave.

## Invariants
**Accepted (supplied evidence):**
- Stable IDs and row-local ordinals.
- Primary-before-overlay order; host state derives from the topmost primary picture, and overlays are independent. Keyboard and pointer input share one pure result (#172).
- Moves preserve identity; duplicates get a new identity.
- No silent deletion or repair. Affected anchors, visuals, transitions, citations, comments and timing are warned about, never auto-repaired (#125 §6).
- Transition picture-only is the default; audio requires explicit intent; anchors are never silently repaired; linked sets are atomic (#125 §4).
- Comments never enter narration, prompter, duration or timeline (#125 §5, #74).
- The scratchpad is lossless and build-excluded (#125 §6).
- The authorized head is preserved and failures are exposed (#64).
- Permissions are checked against the current role, revocation is prompt, and a Research link grants no Research rights (#72).
- VO rows are replaced whole, never spliced. Changed wording never inherits an old approval. Historical exports, recordings and builds are preserved (#153).
- Restore is non-destructive and creates a new head (#75).
- Build evidence is immutable.

**Derived for concurrency (proposals):**
- **I1:** each logical row ID occurs exactly once across sections ∪ scratchpad. Occurrences keep the distinct identities defined by #140.
- **I2:** no content becomes unreachable without an explicit, attributed delete.
- **I3:** every transition boundary, cutaway bound, comment anchor and citation resolves, or sits in an explicit stale, missing-neighbor or Unplaced state.
- **I4:** every merged state is classifiable by #172 without throwing.
- **I5:** every applied change is attributed to an actor who was authorized at application time.
- **I6:** lock and Producer-only epochs cannot be bypassed by late-arriving updates.
- **I7:** builds read only a validated head snapshot. Comments, scratchpad and presence are excluded.

| Concurrent operation | Must hold |
|---|---|
| Row/section moves | I1, I2. Comments and transitions follow by ID; adjacency loss shows as missing neighbor. |
| Cutaway changes | Crossed or stale bounds after merge → the #172 stale/Unplaced class, never silently clamped. Host and overlay rules unchanged. |
| Token/narration text edits | Character merges are allowed. VO regeneration is keyed to committed row text at the head. Post-lock edits are gated by I6. |
| Stale anchors | Explicit stale or ambiguous state plus an attributed reattach. No nearest-match guessing. |
| Scratchpad moves | Lossless. References into parked rows show explicit states, not silent removal. |
| Revoked writers | Nothing applies after the epoch bump. Queued edits are shown as rejected, neither merged nor silently dropped. |

## V1 vs deferrable
- **V1 (Q1) blocker:** F3, the head revision and writer epoch with fail-closed revocation. The attributed per-write record is a strongly recommended part of F3.
- **A1 blockers, before any #73 code:** F1, F2, F4.
- **A1, gated behind those:** F5 (#74 anchors, #75 restore).
- **Deferrable:**
  - Presence and mentions UX.
  - Interleaved-text review cues.
  - Interplay between changed-row pickup export and merges (#153 does not block Q1).
  - Dependency-edge metadata, which is cheap and could be done now.

## Dependency / interface map
```
#156 ─► #172 (closed: commands, validator, D24 resolver, projection)
#72  ─► #64   (actor, roles, revocation)           [edge exists]
#172 ─► #64   (Q1 persists validated head)          [via #156; exists]
#64  ─► #73 ─► #74, #75                             [MISSING edges]
#125 ─► #73 merge semantics / #74 stale semantics   [MISSING owner/edge]
#153 lock epoch + last-prompter baseline ─► #73 ingress  [MISSING]
Missing boundary (proposal, not design):
  commit(actor, epoch, base, semanticChange)
    → accepted(newHead, attributedRecord) | conflict(namedState) | rejected(reason)
```

## Verification / falsification
Each finding includes a test that would refute it. The F1 proof is refuted by one two-replica merge test that passes I1–I3 with no semantic pass. The steward should not change the roadmap on the strength of this review alone.

## Unverified
- Contents of #62, #147, #156 §§4/7/8/9, #140 and #59.
- D24 two-of-three semantics.
- Whether #172's validator is total over arbitrary documents.
- Mapping V1 to Q1, and the A1 milestone definition.
- What "token" and "cutaway" mean in VERA's own terms.
- All Yjs facts: atomic array move, UndoManager scoping and inverses, relative positions across delete+insert, snapshot/GC requirements, nested deleted-type integration, server-side update filtering, causal rejection behavior.
- Whether #64's draft plan already specifies compare-and-set and epochs.
