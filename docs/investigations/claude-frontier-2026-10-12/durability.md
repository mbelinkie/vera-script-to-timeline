# Claude engineering frontier review — durability

Advisory review, 2026-10-12. Model: claude-opus-5-5; session: 69911a4e-e4e9-4fb9-a780-227ae6d7dbd0. Public issue-body packet only; no code/runtime inspection or implementation. Supplied issues: #157, #158, #159, #35, #114, #175, #176.

Steward correction: the text below says #156's frame-rate implementation package does not exist. That is false against the current roadmap: #174 and #177 already own those outcomes; they were outside this bounded packet. Missing canonical links or unresolved interface scope are review candidates, not proof that a new implementation ticket is needed. Lease/effect/auth claims are hypotheses until checked against accepted code and plans. Do not automatically add every proposed blocker or reopen accepted #35/#114.

## Retained Claude response (unverified recommendations)

# Durability Review: #157 Real-Stage Composition and the App/Service/Companion Boundary

**Basis.** This review uses only the supplied issue bodies. I did not inspect any code, baselines or adapter documentation. Every finding below is a gap in issue scope or a contradiction between issues. None alleges a defect in the accepted #35 or #114 code.

## Findings

### F1: High. #157 does not name its authoritative job store and lacks the blockers it needs (Missing; scope contradiction)

**Evidence**
- #159 says: "Keep API/Postgres authoritative and local companion media authority" and "No local-database substitution is selected."
- #35 delivered a "persistence adapter suitable for deterministic tests and later API wiring." It excluded "production database migration."
- #157 is blocked only by #35, #34 and #156. It lists "app/service/companion authority" as unresolved.
- #176, by contrast, is blocked by #64 and #72.

**Failure scenario**
1. #157 passes its force-quit walkthrough using #35's test adapter or a store held by the companion.
2. API/Postgres later becomes authoritative.
3. Idempotency keys and receipts now live in two separate job stores.
4. A resubmission through the API with the same key cannot see the receipt the companion holds, so it creates a second Resolve timeline.

This is testable at plan time. The plan's persistence entry must either:
- cite a #64/#72 interface version, in which case the blocker is missing, or
- cite a store that is not authoritative, which contradicts #159.

**Next action.** Before #157 goes to Ready, the steward obtains one decision:
- (a) add #64, #72 and the labeled #159 development-QA mode as blockers; or
- (b) the Producer approves a labeled interim Q1 job store with a documented one-way cutover that drains or imports keys and receipts.

Either way, the plan names exactly one authoritative job store. The companion keeps only subordinate journals.

### F2: High. Lease fencing stops at the job-store commit; side effects run by the companion are unfenced (Missing)

**Evidence**
- #35: "expiring worker leases/epochs … late lease holders cannot commit." This was proven with "slice-owned fake stages," and Resolve reconciliation was excluded.
- #157 lists "exact stage executor interfaces" as unresolved.
- #159 owns backup and restore.

**Failure scenario (lease expiry)**
1. Executor W1 holds the lease for the delivery stage at epoch 7.
2. The host sleeps and the lease expires.
3. Executor W2 takes epoch 8 and creates timeline T.
4. W1 wakes and calls the Resolve adapter before attempting its commit. The commit is correctly refused, but timeline T′ now exists with no receipt.

**Failure scenario (restore)**
1. Postgres is restored from a backup taken before epoch 8 was issued.
2. The job store issues epoch 8 again.
3. A stale request carrying epoch 8 passes any check that looks only at the epoch number.

**Next action**
- The #157 plan defines a fencing token made of (job-store incarnation ID, job, stage, epoch).
- The executor validates that token immediately before each irreversible call. If it fails, it refuses and reports.
- Every restore rotates the incarnation ID. #159's restore evidence includes a test showing a stale token is refused.
- First check whether #35 exposes the epoch to stage code. If it does not, this becomes the "approved service-interface change note" #157 already allows for.
- A check-then-act window remains for the duration of the call itself. That is why F3 is still required.

### F3: High. The uncertain-effect window has no intent record, no deterministic effect key and no declared adapter class (Partial)

**Evidence**
- #157 requires tests of "restart before/after side effects, uncertain results, duplicate delivery."
- #157 leaves "uncertain-effect receipt reconciliation" and the "narration/privacy/cost policy" unresolved.
- #35's reconciliation "by job/idempotency identity" was proven only against fake stages, whose state the engine fully controls.

**Failure scenarios**
- **Narration:** the TTS service returns audio, but the process is killed before the artifact commits. On restart TTS is called again: a second charge, a second egress of private text, and possibly different bytes.
- **Drive delivery:** the upload succeeds but the response is lost. The retry uploads a duplicate file.
- In both cases, without a durable record written before the call, a restart cannot tell "never attempted" from "attempted, outcome unknown."

**Next action.** The #157 plan requires:
1. **Intent before effect.** An intent record is committed before each external call. Its effect key is a hash of (job, stage, snapshot hash, adapter ID/version), so it does not change between attempts.
2. **Declared adapter class.** Each selected adapter declares one of:
   - idempotent by key;
   - reconcilable by probe, meaning a read-only lookup by effect key returns complete, partial or absent;
   - non-reconcilable.
3. **No blind retry.** An intent with no receipt for a non-reconcilable effect moves the job to waiting/needs-action. It is never retried automatically.
4. **Staged payloads.** Effects that return a payload, such as narration, write the response bytes to content-addressed staging before commit. A restart then commits without calling the service again.

Whether Resolve, Drive (#71) or the TTS provider can support a probe is unverified. The classification itself is the deliverable.

A duplicate request returns the existing immutable receipt. It does not certify that the external target still exists; re-delivery must be an explicit new request.

### F4: Medium. Authorization is checked at admission and resolution, not on resume or before each effect (Partial)

**Evidence**
- #114 makes sources unresolvable after the project switches from library A to library B.
- #114 invalidates capabilities issued before reconfiguration only "if a local-only capability issuance API is needed." It otherwise keeps the project/source `JobAccess` model.
- #35: worker capabilities are "job- and project-scoped."
- #157 requires a "refused authorization" test; #159 requires "authorization/revocation evidence."

**Failure scenario**
1. User U submits a job.
2. Normalization (the #156 route) produces verified derived media from library A.
3. U's project access is revoked, or the project is reconfigured to library B.
4. On restart, the job resumes from the verified artifact without re-resolving sources, as #35 intends.
5. Delivery performs an external effect for a revoked user, using bytes from a library that is no longer authorized.

#114's check never runs on this path. Whether resume actually re-resolves sources is unverified.

**Next action**
- Record an authorization snapshot at admission: the user, the #72 project-authorization version and the #114 library-configuration revision.
- Re-validate the snapshot on every resume and immediately before every external effect.
- On a mismatch, stop at a safe boundary with status refused or needs-action. Leave earlier receipts unchanged, matching #35's cancel semantics.
- Tests:
  - revoke access between stages and across a restart;
  - reconfigure A→B between normalization and delivery.
- The Producer must decide whether derived artifacts with identical hashes survive a library reconfiguration. The safe default is to refuse until the B relink succeeds.

### F5: Medium. Migration activation, cancel and rollback are unspecified for in-flight and receipt-pinned builds (Missing; cross-issue)

**Evidence**
- #176: "Cancel discards only the unactivated candidate reference."
- #176: rollback preserves "v2 history and builds," with "no unrelated service or job-engine behavior changes."
- #175: v1 stays "readable and buildable."
- #157: receipts bind the "input revision" and an "immutable build snapshot."

**Failure scenarios**
- **(a) Candidate discarded under a receipt.** If preview builds of a candidate are allowed, cancel discards a candidate that a receipt references. Resume cannot load the pinned input, and the receipt can no longer be verified.
- **(b) Mixed-revision output.** Activation lands mid-job. Any stage that reads the project's live head compiles v2 for the remaining stages, while the receipt claims v1.

**Next action**
- In the #157 plan:
  - stages read only the snapshot pinned at admission;
  - no stage reads the live head after admission;
  - jobs pinned to v1 resume through the v1 compile path.
- In CN-4/#176:
  - candidates are either not buildable, or are retained once any job or receipt references them;
  - activation and rollback never cancel or redirect in-flight jobs.
- Tests:
  - activation and rollback during an in-flight job;
  - cancel while a job references the candidate.

## Accepted invariants to reuse, not reopen

**From #35**
- Duplicate submissions converge on one logical job.
- Late lease holders cannot commit.
- Resume happens only from verified immutable outputs, with attempts retained.
- Cancellation happens only at documented safe boundaries and never relabels an earlier success.
- Free and Studio stage states are explicit.
- Shared schemas change only under a contract-change note.

**From #114**
- Usable source access requires the currently configured library plus a hash-verified relink.
- Wrong project or source identities are rejected.
- Absolute roots and capabilities are runtime-only and never serialized.

**Stated in open #157/#156, not yet delivered**
- Original assets are never mutated.
- Mismatched media never proceeds.

## Minimum durable state and receipt invariants

| # | Invariant | Coverage |
|---|---|---|
| D1 | One authoritative store for jobs, attempts, leases, intents and receipts | Missing (F1) |
| D2 | Admission pins a snapshot: revision ID, content hash, schema version and profile; no live-head reads afterward | Partial (#157; F5) |
| D3 | Fencing token (incarnation, job, stage, epoch) checked at commit and before every effect | Commit: covered (#35). Effect: missing (F2) |
| D4 | Intent committed before each effect, with an effect key that does not change between attempts | Missing (F3) |
| D5 | Each adapter declares its effect class; an unknown outcome for a non-reconcilable effect becomes needs-action | Missing (F3) |
| D6 | Outputs are staged, verified by probe/hash and atomically moved to an immutable location before the receipt commits; partial targets are retained under a distinct status that is never reused as complete | Partial (#35, #157 mixed-frame-rate addition) |
| D7 | Append-only receipt containing: input hash; adapter, version and profile; package attestation; frame-rate mapping; authorization snapshot; effect key; epoch; output hash or locator; verification evidence | Partial (#157 lists the first four) |
| D8 | Authorization re-validated on resume and before each effect | Partial (F4) |
| D9 | Restore never reissues tokens; intents without receipts reconcile through D5 before any re-execution | Missing (#159; F2) |

The D3 token fields and the D7 receipt fields change the shared job/RPC schema. Under #35, that requires a contract-change note.

## Dependency and interface map

```
#34 assembly ─┐  (+#109 only if injected delivery selected)
#156 decision → [selected frame-rate impl package: not yet an issue] ─┐
#35 job engine (accepted) ────────────────────────────────────────────┼─▶ #157 ─▶ #160 cross-product test
#64/#72 persistence/auth ─▶ #159 deploy/backup ┄┄ missing edge (F1, D9) ┄┄▶ #157
#43/#114 library resolution ─▶ companion media authority ◀─ #158 pairing ┄┄ token auth (F2) ┄┄▶ #157
#175 ─▶ #176 activation ┄┄ pinned revision / candidate retention (F5) ┄┄▶ #157
#157 receipts ─▶ #70 UI; #71 Drive/review adapters
```

Interfaces the #157 plan must name:
- **Job store:** the #35 adapter, mapped onto #64/#72.
- **Stage executor:** the service→companion RPC, carrying the fencing token.
- **Effect adapter:** declared class, `invoke(effectKey, token)`, and `probe(effectKey)` where supported.
- **Authorization snapshot:** the #72 authorization version plus the #114 library revision.
- **Receipt schema:** the D7 fields.

## Unverified

- Whether #35 persists attempt records before a stage runs, and whether it exposes the epoch or incarnation ID to stage code.
- Whether resume re-resolves sources through #114 or reuses stored artifacts directly.
- Whether the selected Resolve route (#34/#109), Drive (#71) or the TTS provider supports idempotency keys or read-only lookup. No such capability is assumed.
- Whether candidate revisions can be built.
- Whether #64/#72 head and version counters stay monotonic across a restore.
- Whether a companion pairing identity is available to authenticate executor requests (#158, Research M7 patterns, #109). #158's blockers, #6 and #107, were not supplied.
- #156's selected implementation package does not exist yet, so #157's dependency on it is still a placeholder.
- The scope of #160, and the accepted contents of #34, #64 and #72.
