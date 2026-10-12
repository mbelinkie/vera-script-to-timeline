# Issue 12 plan — EV24 Lower Third registration

## Bounded slice

Register the producer-supplied EV24 Lower Third as one immutable external
package through the accepted issue #20 `TemplateLibraryService`. The package
contains the unchanged `.setting`, its declared atlas, and one package-owned
non-production badge image for validation. The accepted #20 library commit is
merged into this branch because it is the required registration dependency.

## Scope and authority

- Issue #12 is Ready, routed `model:sol` / `effort:high`, has Producer
  acceptance, and is blocked only by Done issue #20.
- The authored Fusion controls and 48-frame entrance, 16-frame exit, flexible
  hold, and 64-frame minimum are pinned as package metadata. VERA maps typed
  values to controls; it does not implement the authored Year/Country auto-fill.
- Validation checks exact file hashes, the graph fingerprint and exposed
  controls, Resolve compatibility, path safety, rights declarations, and
  duplicate/partial registration behavior before the #20 library commits.
- A project administrator must choose the exact approved project and attest
  package and font rights before the revision can be registered there.

## Exclusions and touched boundaries

- No visual or animation change, Resolve placement, production Resolve
  installation/project mutation, browser UI, arbitrary asset-path input,
  compiler/shared graphics contract, or Free fallback.
- No change to `/contracts`, `/fixtures`, golden files, generated types, or
  previously accepted tests. New slice-owned tests and assets live in
  `packages/contracts` beside the #20 library.
- No new dependency. Node's standard filesystem and crypto APIs suffice.

## Verification and Producer acceptance

Write focused tests first for the exact package and semantic values, then for
missing/altered/undeclared files, invalid rights/paths/compatibility, and
duplicate registration with no partial state. Run focused tests and the full
repository validation gate. Retain exact artifact hashes and registration
identity in the review handoff. The Producer checks the packaged artifacts,
the chosen project library, provenance and rights, and the immutable revision,
then records explicit acceptance or the failed step. Leave #12 In review until
that response.
