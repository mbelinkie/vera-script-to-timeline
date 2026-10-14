# Proposed CN-178-Q1 — audited native qualification bootstrap

Status: proposed, not approved or implemented. Source examined:
`bd6048b02604954df037bf0b2dd01906e986d19d`. This note is a concrete review
artifact for the Producer/coordinator, not permission to remove current guards.

## Why and ownership

#177 accepts v2 packages but refuses fractional/native-source-audio builds
before constructing its adapter. #190 calls that public delivery, ships no
installed proof bootstrap, requires an unbound complete control reader, and
renders audio only. Consequently #178 cannot acquire the evidence needed to
qualify those capabilities using the current audited flow.

Owning boundaries: #109 installation/injection/source integrity; #177 public
package/delivery/placement/readback; #190 proof authentication, observation and
owned job evidence. #178 owns real qualification. Coordinator must explicitly
assign the amendment of those modules and settle whether a bounded prerequisite
issue is required: #178 currently excludes package-adapter implementation.
This note does not reopen their accepted tasks, message another implementation
owner, expand #192, or grant code ownership by itself.

## Exact proposed change

| Boundary | Proposed amendment | Retained limits |
| --- | --- | --- |
| Public native entry | Add a distinct public qualification operation to the #177 owning module, calling the same single `PublicResolveAdapter` and shared checked orchestration. It consumes a separately versioned operator request and independently validated local authority receipt. Bind issue #178, exact case/package/preflight/source/release hashes, finite capability set, approved roots, unique fresh nonproduction target, effect intent and External Scripting None. Ordinary delivery continues to refuse unqualified fractional/source-audio capability. | No JSON boolean sets qualification, no package self-authentication, no second adapter or direct private effect calls. Qualification result is explicitly an experiment pending External acceptance, never `nativeRateQualified: true` or a routine capability certificate. |
| Finite capability scope | Experiment only at reduced 24000/1001, accepted prepared same-rate picture, No/Quiet/Full using manifest gain -18/0 dB, root/child/return, independent overlay, existing qualified contain treatment and exact audio geometry. Map the rational explicitly to the documented native setting token `23.976`, not via a generalized float conversion. Verify native getters/settings and later decoded picture cadence against the rational. | No 30000/1001 native target, retiming, subtitles, unqualified slate/cover/native treatment, silent gain normalization, or widening of source ranges. Unknown property/control/version refuses. |
| Installation/request | Extend the existing repository-owned release/request/launcher mechanism with an explicit qualification request version and complete declared runtime inventory. Bootstrap injects the native object and invokes only approved public ports. Validate release/request before import, reject loaded runtimes/undeclared files/symlinks, disable bytecode caches, retain immutable started/refusal/result hashes. | No new connection discovery, external scripting, Resolve MCP raw script, console exec, UI automation, or installation side effect. Quit/archive/copy/restart stays in the accepted operator product flow. |
| Host-to-native proof binding | Trusted host integration supplies actual receipt verification and actual decoding/probing, then binds immutable #190 preparation/package outputs and checked repository source graph to installed source. Native controller consumes those pins; it does not import a host compiler/provider or accept a no-op verifier. | Preserve original/execution distinction and finite private profiles. Initial R16 document AND dependency raw bytes remain pinned. CN192R1 is not approval for this route. |
| Complete controls | Name an exact independently accepted reader/evidence source for clip, track, bus, master, destination and channel map; recheck it on adjacent reads, save/reopen and render. Include observable clip pitch, pan, voice-isolation and dialogue-leveler effects as relevant. No reader is yet supplied by this proposal. | No default zeros, empty effects/sends/automation, inference from a fresh project's defaults, or a claim that setting a preset observes its state. If current documented sources cannot establish completeness, STOP and propose a separately reviewable boundary change; do not silently weaken #190. |
| Picture render | Add a finite #178 picture-review operation at #190's existing audited render boundary, or name an accepted equivalent port before implementation. Require explicit independently qualified format/codec, full-programme exact range, frame-rate/dimension/audio settings, actual queue/job/current target/settings/output binding, adjacent state checks and independently decoded bytes. Keep the existing WAV operation for acoustic proof. | No generic renderer/upload/service. Retain job/output reservation, exclusive intent/effect/start/completion, no uncertain retry, no overwrite/deletion. Audio-only WAV cannot satisfy final picture criteria. |

## Proposed file and version assignment

The following names fix the review proposal; none exists as a usable
qualification API today. The coordinator may revise this exact assignment
before approval. Files outside this table require a bounded amendment.

| Proposed file reach | Responsibility |
| --- | --- |
| `python/vera_timeline_agent/workflow_v2.py` | Public `run_workflow_qualification_v2`, same single adapter/common checked orchestration, explicit rational setting map. Routine `run_workflow_delivery_v2` keeps all current qualification refusals. |
| `python/vera_timeline_agent/workflow_v2_cli.py` | Prepare the declared qualification inventory and immutable versioned request from independently checked inputs; no installation or native connection. |
| `python/vera_timeline_agent/workflow_v2_launcher.py` | Dispatch the exact approved qualification request version after normal integrity checks, retain experimental result; existing delivery-request semantics remain. |
| `integrations/resolve/VERA Delivery v2.py` | Bootstrap the declared revised release only; no second native connection or script path. |
| New `python/vera_timeline_agent/native_qualification_v2.py` | Closed request/authority consumer and capability-preflight controller; explicit installed receipt/control-reader integration. It calls public #177/#190 ports. No compiler/provider conversion or private delivery helper call. |
| `python/vera_timeline_agent/roundtrip_v2_native.py` | Public qualification-delivery wiring and bounded `render_picture_review` with the existing job/effect ownership model; PCM behavior unchanged. Complete controls remain required. |
| `python/vera_timeline_agent/roundtrip_v2_records.py` | Explicit source-inventory/binding support for the owning installed integration and any newly versioned evidence, without excluding consumed code from hashing. |
| New `tests/test_issue178_qualification_boundary.py` and `tests/test_issue178_picture_render.py` | New request/authority/ordinary-refusal/experimental-effect/control/readback/job/recovery coverage. Existing accepted tests remain read-only. |

Reuse release schema `vera-injected-delivery-release/v2` with a new exact
inventory/digest. New closed records proposed:

- `vera-native-qualification-request/v1`: `schemaVersion`, `issueNumber`,
  `action` (`capability_preflight` or `qualify_build`), `releaseSha256`,
  `repositorySourcePins`, `attestationPath`, `attestationSha256`,
  `proofPackagePath`, `proofPackageSha256`, `authorityPath`, `authoritySha256`,
  `caseId`, `target`, `capabilities`, `externalScripting`, `evidenceDir`.
  Preflight target is the exact operator-approved existing disposable
  `{projectUid,timelineUid,projectName,timelineName}`; build target is the
  exact attested fresh `{projectName,timelineName}` and gains actual UIDs only
  from the retained effect. Capabilities are a finite enum, not qualified flags.
- `vera-native-qualification-authority/v1`: trusted independently issued local
  receipt binding operator identity/decision provenance, issue/case/action,
  release/source/package/proof hashes, exact target intent, approved read/write
  roots, finite requested operations and None confirmation. A hash alone is
  insufficient: the installed verifier validates that provenance and exact
  context. Request preparation cannot issue its own authority by hashing JSON.
- `vera-native-qualification-result/v1`: operation/request/authority/source
  identities, actual connection/runtime, observed capabilities and explicit
  unavailable fields, effect lineage/target and evidence references.
  `qualified` is always false; native case results are retained as observations
  for external acceptance. No routine capability registry is modified.
- `issue-178-v2-picture-render-{intent,effect,started,complete}/v1`: operation
  kind plus binding/target/observation hashes, whole-programme parameters,
  owned output reservation, actual job/settings/start/poll/completion and
  independently hashed/decoded output receipt. Distinct from #190 WAV records;
  do not reinterpret an existing audio record as picture evidence.

The owner must finish exact scalar/union validation and hashes for these
records in its accepted implementation plan. No executable callback, module
name or arbitrary script path is chosen by request JSON. The explicit
capability preflight cannot grant build authority. Approval of this note alone
does not establish that the control reader is feasible.

## Minimal actual-app feasibility action, after approval and grant

Prepare a hash-pinned `capability_preflight` request through the amended
product release. Operator quits/copies/restarts using #109's flow, confirms
None, selects an already saved disposable nonproduction project/timeline
listed in that request, then launches **VERA Delivery v2** once. Read only:
`GetProductName`/`GetVersion`, current target UIDs, complete project/timeline
settings, track count/subtype/enable/lock, item properties/speed/channel maps,
documented control evidence supplied by the approved reader,
`GetRenderFormats`, `GetRenderCodecs`, `GetRenderResolutions` and existing
queue facts for this target. No setter, creation, save, export, queue insertion
or render start. Retain raw source-tagged results and missing-field reasons.

Expected result is a capability-gap report, not a pass. It must identify
whether clip/track/bus/master facts cover every #190 field and whether candidate
picture/PCM settings have documented native representations. A subsequent
owned synthetic calibration job is separately gated; read-only format lists
do not prove actual queued fields, output cadence or codec quality.

Supported fallback today: stop at the exact unavailable field and retain the
report. If controls cannot be observed through supported APIs, propose an
explicit versioned operator-evidence reader inside the same audited flow,
with independently authenticated current-target control evidence and freshness
rules, for separate approval. Manual screenshots/defaults cannot be fed into
#190's trusted reader without that accepted consumer. Similarly an accepted
existing picture port may be selected instead of adding `render_picture_review`
only if its real target/job/settings/output binding is proved equivalent and
the coordinator approves the owner/dependency handoff. No such fallback is
asserted installed or accepted here.

## Separate R16 package decision

#177 requires empty diagnostics/recovery actions. R16's accepted input contains
temporary presenter picture; inspect the actual strict preflight result after
the queue grant. If it cannot package unchanged, retain the refusal and write
a narrowly specified #177/#190 package-consumer note binding exact allowed
diagnostic semantics and acceptance. That decision is NOT included as an
automatic waiver here. Do not edit frozen R16 bytes, remove the warning,
rewrite the report, bypass public verification or label it synthetic.
Sanitized #178 cases must remain genuinely issue-owned synthetic inputs;
they cannot stand in for R16's private-input acceptance.

## What changes, what breaks and frozen impact

Changes: new qualification request/authority/result semantics, declared
bootstrap inventory and a finite public qualification operation; exact native
rate mapping and bounded picture-job evidence. Any shared extraction should
retain ordinary delivery behavior and #109 target/hash checks byte-for-byte in
meaning. Changed source pins require new attestation/release/request hashes.

Existing v1 installed releases and accepted v1 proof stay unchanged. Existing
v2 release/request consumers cannot read a qualification request; they should
refuse it. New code must not merge files into an old release or reuse a loaded
interpreter. Review each changed #177/#190 source-hash inventory and caller
binding together; old #190 bindings become stale for the new source graph.
Do not falsely advertise a new qualified production capability after a partial
matrix pass. A later exact-build capability activation requires explicit retained
acceptance and its own approved owning change.

Shared `/contracts`, generated TS/Python types, frozen fixture/golden files and
accepted tests: proposed changes **none**. No generator run is required for
issue-owned runtime records. Use new slice-owned tests and sanitized new
fixtures. If implementation requires changing a shared schema, accepted test,
fixture, golden or semantics above, return a precise amendment for Producer
approval before that edit. Dependencies: no new library; existing stdlib,
locked host tools and accepted public adapters suffice. A new canonical issue
dependency, if needed for owner scope, requires coordinator decision and its
Closed/Done handoff before Ready.

## Required checks and acceptance changes

After explicit ownership/approval and heavy grant: test-first missing/wrong
authority, drift, wrong source/release/target/rate/audio policy, collision,
ordinary-path refusal, unknown/incomplete controls, exact gain/readback,
fractional/source geometry, save/reopen identity, output reservation, uncertain
effect and interrupted recovery. Add picture-job settings/identity/output
negative coverage. Preserve accepted regression suites, fixtures and byte
goldens; compiler changes are outside this note.

Use focused checks/fast gate, required adversarial Claude review of identity,
hash/path/rational/native/control/recovery/render seams, fixes and delta
review, then final local full acceptance evidence with locked Node24.19.0,
npm11.17.0, uv0.12.5 and Python3.12.14. Next necessary costly pytest includes
`--durations=25`; run changed slow media tests serially. Do not start those jobs
while #192 owns the slot. #196 pure cloud substitution and #174's historical
exception do not qualify native behavior.

#178's External criteria remain unchanged: actual cadence/count/source cover,
PCM endpoints and sync, Quiet/Full measured levels, No absence, full topology,
save/close/reopen, owned final picture/audio output, refusal/recovery and genuine
visual/listening judgment. All newly exercised native operations need real
evidence. Automated/fake success cannot close the issue or #145's human gates.

Producer review steps: read the readiness findings, decide shared-module owner
scope and the finite public qualification request boundary above, confirm that
complete controls and picture render must be proven before qualification, and
record `Approved CN-178-Q1, owner/scope <exact assignment>` or the precise
section requiring revision. This is a proposed review response, not an approval
already received. Coordinator then validates route and Ready separately.
