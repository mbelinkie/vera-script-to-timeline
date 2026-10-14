# Proposed CN-204-ID1 — name-bound read-only target identity handoff

Status: proposed only. No implementation, authority issuance, installation or
native execution is authorized by this document. The current reviewed release
hash remains `d4ec949a5a197a54bc58c969bcb2655553064e4600fb11c6ba2f748bf6f33d66`.

## Exact missing boundary and Producer action

The operator can select an already saved disposable NONproduction project and
timeline and provide their visible names. Project/timeline UIDs are not visible
in Resolve's ordinary UI. #204's closed preflight authority requires all four
identifiers before any native call. The accepted #109 result, independently
rehashed as `ec802ea507524cc821b0215f989d7b01dd235796700f9e7ee10fee009be86797`,
records the accepted target names but neither UID. Asking the operator to find
invisible UIDs, guessing them, or adopting a failed #204 preflight's observations
would not establish a trusted handoff.

Proposed Producer decision: approve a separate, finite **name-bound identity
handoff** through the same declared installed Workflow Integration. Operator
chooses and saves the disposable target, supplies its two visible names, and
explicitly confirms None and read-only/nonproduction. The agent prepares the
exact reviewed release and name-bound request; the operator installs/restarts
and launches it once. The operator never needs to discover or type UIDs.

## Proposed finite operation and owned reach

Add only `target_identity_handoff` to the #204 owning controller/CLI/launcher/
bootstrap stage. Exact scope: current injected Studio product/version/build,
current project/timeline names and `GetUniqueId()` values. Call only
`GetProductName`, `GetVersion`, `GetProjectManager`, `GetCurrentProject`,
`GetCurrentTimeline`, `GetName`, `GetUniqueId`.

Check the current visible project name before accessing its timeline, then the
timeline name before accepting its identity. Take two complete agreeing reads,
with request/authority/source/release rechecks around them. A different name,
missing UID, unsupported version, changed object/input or inconsistent read
refuses and retains unqualified evidence. No selecting/searching targets,
creation, save, import, source/media/control enumeration, export, queue, render
or settings mutation. No external scripting, UI automation, MCP script, console
helper or code selected by request JSON.

New closed records proposed: `vera-native-target-identity-authority/v1`,
`vera-native-target-identity-request/v1`, `vera-native-target-identity-result/v1`.
Authority binds operator provenance and explicit saved/nonproduction/read-only/
None confirmations, the two named targets, approved read/write roots and exact
approval/source/release hashes. Request consumes that separately issued local
operator receipt. Result binds actual four identifiers, two agreeing current
reads, request/authority/source/version hashes and `qualified:false`; it grants
no subsequent action. Trust remains the explicit local operator procedure,
not a signature or an assertion that hashes authenticate human identity.

The later existing `capability_preflight` authority must explicitly consume the
retained successful identity result hash and exact four identifiers together
with a fresh operator request/decision. It cannot adopt UID values from a failed
identity/preflight result. It still rechecks the exact current target. This is
a new approved identity route, not reinterpretation of the accepted #109 result.

Reach, only if approved: `native_qualification_v2.py`, `workflow_v2_cli.py`,
`workflow_v2_launcher.py`, `integrations/resolve/VERA Delivery v2.py`, new
issue-owned tests and operator/evidence documents. No #177 ordinary build guard,
#190/#192 native/records, shared contract/generated output, fixture, golden,
accepted test, lock or dependency changes. No generator needed for these
issue-owned records. Changed runtime pins invalidate the currently prepared
release/authority; produce a new exact release, never merge files into the old
installed bundle.

## Required checks and acceptance

Test exact name match before further reads, duplicate/extra/scalar refusal,
wrong authority/source/release/version, missing/duplicate/changing UIDs, target
switch between reads, symlink/hardlink/alias paths, immutable report and zero
non-getter attempts including stopped cases. Add tests proving failed identity
records cannot supply subsequent preflight authority. Run affected focused/
fast checks and independent adversarial delta review of the new authority seam
before installation. Actual operator handoff/identity result is required;
synthetic getter tests do not prove this route exists in the app.

Following actual identity and preflight reports, fix any runtime findings,
re-review deltas and run final full validation on final delivered source.
Neither operation qualifies fractional builds/audio/render or closes #178.

Review response, if the Producer chooses this route:
`Approve CN-204-ID1 name-bound read-only target identity handoff, target
<visible project name> / <visible timeline name>.`
That response is proposed, not received. Coordinator must grant the exact
bounded implementation and later operator/runtime step before work begins.
