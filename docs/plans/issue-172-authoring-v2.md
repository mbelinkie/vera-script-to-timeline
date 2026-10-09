# Issue #172 — authoring v2 pure sequence edits, validation and projection

## Scope and authority

Implement the P3 pure authoring surface from the Producer-accepted #156 plan
at `e32727f0c0e65dc5a8561e0f470ed28e59bd1809`. The scope is the v2 semantic
validator, derived row projection, structural edit transactions, and the D24
two-of-three placement resolver. `@vera/contracts/authoring-v2` is the only new
package entry point. Host state is derived from topmost primary picture;
overlays remain independent. Commands either return one new document or leave
the original document unchanged with diagnostics.

Successful edits increment the affected sequence/entity versions and return
operation evidence. The pure P3 API does not publish or acknowledge a live
collaboration snapshot: `liveStateVector` is explicitly acknowledged state
evidence, and `liveHeadSequence`/`liveContentHash` remain owned by the
application snapshot boundary. App or persistence callers must register the
edited canonical document through their existing acknowledgement transaction
before advancing those fields. This seam makes no CRDT, persistence, or remote
sync claim.

The slice uses the accepted v2 schemas and generated types from #170/#171.
There is no schema, generated type, v1, production fixture, golden, UI,
persistence, migration, compiler, timing-inference, media, native-application,
or external-service change. Test data is synthetic and owned by this issue.

## Contracts and files reached

- Add `packages/contracts/src/authoring-v2.ts` and the smallest cohesive
  internal modules needed for validation, projection, placement resolution,
  and edits.
- Add the explicit `./authoring-v2` export in
  `packages/contracts/package.json`.
- Add `packages/contracts/test/authoring-v2.test.ts` with inline synthetic
  documents and deterministic success/refusal cases.
- Add this plan and `docs/verification/issue-172/` records for exact source,
  toolchain, and passing-command evidence.
- Keep `/contracts`, `/fixtures`, all existing accepted v1 tests/goldens, and
  #170/#171 schemas, generated surfaces, and fixtures unchanged.

## Dependency decision

No dependency is needed. Use the installed Ajv/schema types, Node APIs,
TypeScript, and existing workspace conventions.

## Acceptance and verification

The focused automated matrix covers continuous roots with nested cutaways and
returns, a reversed advancing root, independent crossing overlays, row-local
ordinals and primary-before-overlay ties, exact shared-word boundaries,
stale/null/equal/crossed boundary refusal, atomic swaps and base swaps,
mode-switch and destination refusal, base deletion promotion, Unplaced
promotion, consistent and inconsistent two-of-three timing, zero/negative/
out-of-row timing refusal, and identical pure projection data for pointer and
keyboard consumers.

Run focused contracts tests, TypeScript lint, and TypeScript typecheck under
Node `24.19.0` / npm `11.17.0`. The repository owner runs the complete
`npm run validate` gate after review; no long full-repository suite is part of
this worker's bounded verification. Acceptance authority is **Automated**:
retained passing commands and exact tool/source pins are the closing evidence.

## Automated acceptance and review checklist

- Confirm the public v2 API matches the accepted #156 P3 seam and leaves v1
  callers/bytes unchanged.
- Confirm projection derives structure, host state, human ordinals, and stale
  renderability without persisting derived display state.
- Confirm each failed edit preserves the original document and each successful
  edit changes only the command's stated identities/boundaries/payloads.
- Confirm automated acceptance evidence and the parent-run repository gate
  pass before closing #172 as Done.

## Forecast

Issue size is M. The main transaction, validation, projection and resolver
surface is implemented; the 17-case authoring suite, contracts lint and
TypeScript typecheck pass. The additional full contracts workspace run
reported 282/284 passing; two existing #144 CLI tests exceeded their default
five-second test timeout under package-wide concurrency. No #144 tests or
timeouts were changed. Worker remaining work is final diff review and an
issue-scoped commit, estimated at 10–20 active minutes with medium confidence.
The parent owns broad repository validation and any targeted rerun of those
existing timeout cases. External or Producer waits are not part of this slice.
