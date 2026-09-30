# Issue 131 — reconciliation technical-feasibility proof

## Scope

Prove representability, or fail closed, for the accepted #123 inbound design
and its paired #136/#128 outbound cases. The proof covers stable row, token,
logical-item and occurrence identities; anchor changes; row merge/split
lineage; linked appearances; verified audio cuts; dormant and preserved media;
section-boundary razors; conflict/Defer persistence; and missing-media safety.

The output is a supported/unsupported/ambiguous matrix for #139, a deterministic
synthetic proof, a current-contract and tested-bridge audit, and a separate
proposed contract-change note. A synthetic model proves only that the state and
operations can be represented; it does not prove that Resolve exposes stable
enough observations to populate that model.

## Exclusions

- No production reconciliation or compiler/adapter implementation.
- No Resolve connection, project/timeline mutation, or real-media mutation.
- No browser UI or replacement design artifact.
- No edit to accepted #123, #135, #140, the paired #136 authority, or #137's
  concurrent work.
- No contract, fixture, golden, generated-type, accepted-test, dependency, or
  lockfile change.

## Authority and evidence boundary

- Product behavior: Product Spec §§6.13, 6.15, 6.16, 7, 8.1–8.2 and 13.
- Accepted inbound design: #123 handoff and annotation guide at commit
  `70dfcf265bc17028875e05e0e9b7e7a2d0362f7d`.
- Accepted paired planning: #136's two #128 planning documents at commit
  `db16cec` and the retained #136 handoff at `cf72d58`.
- Accepted authoring sources: #135 export SHA-256
  `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea`
  and #140 export SHA-256
  `08aca68edc5f1de6cbf180b2104a611d67561088fc3240972cd6e1f4108e7c0d`.
- Concurrent #137 evidence is read-only and not a prerequisite. Record the
  exact private rules/change-log snapshots used without publishing private
  paths or verbatim discussion. Treat explicitly approved decisions separately
  from unaccepted artifact behavior and open suggestions.

## Evidence method

1. Audit the current frozen ScriptDocument, compiler-dependency and timeline-
   manifest schemas plus the tested Studio bridge. Record what exists, what is
   absent, and what the current bridge has actually verified after save/reopen.
2. Run one stdlib-only deterministic synthetic proof from frozen JSON input.
   The proof must preserve both source snapshots byte-for-byte and exercise:
   stable identity/anchor matching, merge/split lineage, linked occurrences,
   verified versus ambiguous audio cuts, dormant hide/reveal, preserved-media
   fit/collision, structural-boundary blocking, stale-review rejection,
   persisted Defer/conflict decisions, and missing-media blocking.
3. Separate three evidence levels in the matrix:
   - **Supported**: deterministic current evidence is sufficient for the stated
     bounded claim.
   - **Unsupported**: the current contracts or bridge cannot represent or
     observe the required fact safely.
   - **Ambiguous**: representable in a sidecar, but a named read-only real
     Resolve observation is still required.
4. List the smallest real-Resolve evidence needed to retire every ambiguous
   result. Installed API documentation is capability evidence, not observed
   save/reopen, duplicate, razor, relink, offline-media or Fairlight behavior.
5. Put every proposed schema/type/migration/fixture implication in a separate
   change note. This issue does not authorize that change.

## Touched boundaries and dependencies

- Touched contracts, fixtures, goldens, generated types and accepted tests:
  **none**.
- New package/service dependencies: **none**; the representation proof uses
  Node's standard library. The boundary tests reuse locked Vitest and the
  actual validator/compiler. Bootstrap only existing locks and the pinned
  Node 24.19.0 runtime; never update a lock to make checks pass.
- Canonical dependency: #123, closed and Done. #137 is concurrent evidence and
  is not required to finish.

## Automated checks

- `node docs/prototypes/issue-131/check.mjs`
- `npx vitest run docs/prototypes/issue-131/contracts.test.ts`
- focused existing contract/compiler and Studio-spike tests
- frozen-boundary diff against `c9a047f`
- `git diff --check`
- `npm run validate`

Any toolchain failure is retained as a blocker with the exact command and
error; no dependency is added merely to make the evidence pass.

## Producer acceptance

1. Open the retained feasibility report and confirm every named issue behavior
   has a supported, unsupported or ambiguous result with a reproducible check.
2. Confirm the report never treats the synthetic model or installed API
   signatures as real Resolve proof.
3. Review the proposed contract-change note and confirm it is isolated from
   this branch's implementation.
4. Confirm the #139 constraints and the exact follow-up real-Resolve evidence
   are practical and do not silently amend #123 or the accepted paired plan.
5. Respond `Issue #131 feasibility report accepted.` or identify the first
   result whose status, evidence or constraint needs correction.

#131 remains In review until that explicit Producer response.
