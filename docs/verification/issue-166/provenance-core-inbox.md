## Outcome

Implement the accepted #166 provenance contract as a bounded pure schema,
resolver and immutable content-operation seam, preserving exact accepted
#7/#20 identities. This is an Inbox placeholder, not Ready/dispatch authority.

## Scope

- First obtain explicit Producer approval of #166 CN-166-P1 at an exact
  revision. Record integration of accepted #7 `7cb942e4` and #20 `951c658b`
  separately from the chosen main baseline; do not rebuild their behavior.
- Implement the approved provenance snapshot/binding, v1/v2 interface mapping,
  validation, byte/canonical hash boundaries and diagnostic propagation.
- Implement pure create, repeat, explicit refresh and template migration
  operations over already authorized/retained synthetic inputs; atomic selection
  persistence stays #64. Implement explicit v2 legacy/manual/derived resolver
  classification and missing-record refusal, not a silent legacy fallback.
- Scope the approved frozen-boundary and generated-type changes in the plan,
  with new slice-owned tests/goldens and preserved legacy accepted outputs.

## Acceptance criteria

- [ ] #166 is explicitly accepted and CN-166-P1 approved at a named revision;
  exact implementation baseline and imported accepted source identities recorded.
- [ ] Decision-complete bounded plan lists interfaces, field defaults/migration,
  consumers, frozen approval, deterministic tests and actual later app owners.
- [ ] Synthetic tests cover #166's success/refusal/recovery matrix, hash material,
  manual/derived/legacy defaults, resolver-record loss, project isolation,
  replay/source unavailability, changed refresh and incompatible migration.
- [ ] Existing #7 semantic hashes/template IDs and #20 use/copy semantics remain
  unchanged; old legacy goldens remain byte-identical under approved migration.
- [ ] Generated-currentness, focused/fast checks, separate adversarial Claude
  review/dispositions and applicable verification-policy final evidence pass.
- [ ] #64 persistence, #8 Studio/#10 Free and #9/#67/#69 UI handoffs are explicit;
  no pure test claims actual application or provider acceptance.

## Dependencies

- Blocked by #166
- Blocked by #7
- Blocked by #20

## Existing-owner audit

#7/#20 are closed foundations; #8 is scoped EV24 Studio placement, #9 authoring
form, #99 registration, #167 cues and #64 durable persistence. Open/closed
issue title and provenance-body search on 2026-10-15 found no owner of this
new standalone provenance-core implementation. These owners retain their
scopes; this follow-up implements the shared seam they consume.

## Exclusions

No new library, renderer, template design, UI/registration/cue implementation,
provider calls, Resolve operations, production data, uploads, merge/deployment
or dispatch. No frozen changes before explicit approval. No changes to source
acquisition/auth or existing lifecycle behavior.

## Unresolved decisions and tentative routing

Producer must accept #166 and separately approve CN-166-P1. Before Ready,
choose integration baseline, retained-evidence resolver/persistence adapter
seam with #64 and migration rollout. Refine bounded size if integration reveals
larger work. Tentative model:sol / effort:high; Size M; P2; Contracts and
Compiler; Acceptance Producer for new contract/migration judgment. Actual
Studio/Free acceptance stays with #8/#10; this placeholder grants none.
