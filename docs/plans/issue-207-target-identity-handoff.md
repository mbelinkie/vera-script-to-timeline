# #207 — CN-207-ID1: trusted read-only Resolve target identity handoff

Status: **proposed; awaiting Producer acceptance**. This note selects a design
for [#208](https://github.com/mbelinkie/vera-script-to-timeline/issues/208).
It grants no implementation, installation, authority issuance or Resolve action.
Owner: chat `01a13a9a-6438-7cc1-8b22-c879e37d31d4`, Sol/high,
`codex/issue-207-target-identity-handoff`, accepted main
`deaa75c90b5486e500cb69266faa7bdf09697efc`.

## Decision, scope and existing evidence

Add one operator-invoked `target_identity_handoff` to the installed #109 injected
Workflow Integration route. The operator personally selects an **already saved,
disposable NONproduction current project and timeline**, supplies their two
visible names, and confirms read-only operation and External Scripting None.
The operation reads their real names and UIDs, retains an immutable unqualified
receipt, and stops. A later independent operator decision consumes that exact
receipt and all four identifiers before issuing #204 capability authority.
The operator never has to find or type invisible UIDs.

[The receipt audit](../verification/issue-207/receipt-audit.md) found no adequate
prior receipt for this selected-target bootstrap. The actual accepted #109
result was independently rehashed as
`ec802ea507524cc821b0215f989d7b01dd235796700f9e7ee10fee009be86797`:
it has names, no project/timeline UIDs. #109's adapter uses UIDs internally;
that does not make them retained evidence. #177's package attestation supplies
planned new-target names; #190's completion supplies UIDs only after separately
authorized new-target delivery. Synthetic #144 records do not prove this target.
No failed #204 result, guessed identifier or arbitrary script supplies authority.

Reuse the operator trust procedure, versioned release inventory, immutable JSON
publication and injected-object boundary of #109/#177, and #204's current-target
guards. [CN-204-ID1](../verification/issue-207/receipt-audit.md) is proposal
evidence from the same #204 owner, **not an accepted authorization**.
Spec anchors: Slice 1.6 and §§9.1, 9.3, 9.4; accepted #109 selects injection in
place of the spec's original external connection. This does not alter new-build
or rebuild semantics.

Exclusions: no target search/selection/creation/save, media/control enumeration,
import/export/settings/queue/render, external scripting, MCP/raw/console script,
UI automation, provider/upload/sharing, production or research-data operation.
No #178 capability qualification or #145 creative/listening acceptance follows.
Contracts, generated types, fixtures, goldens, accepted tests and v1 stay frozen.
No dependency is added: standard-library records and the existing loader suffice.

## Exact future ownership and integration baseline

#207 owns only this new note and `docs/verification/issue-207/*`.
#204 retains chat `01a1386b-1bc1-77d3-9390-bbc345b1c091`, f582,
`codex/issue-204-native-preflight`; #208 must use its own branch/worktree.

Accepted main above does **not** contain #204. Use #204's committed clean
checkpoint `de4ed9bb27748958bfa8720b60f0369fbad2e6c1` as a reviewed, unmerged
source input, including reviewed production source
`724a829f6913eec7f939597c454c54aec5407058`. The minimal source prerequisite is
its `native_qualification_v2.py`, `workflow_v2_cli.py`, `workflow_v2_launcher.py`,
`VERA Delivery v2.py`, pinned `docs/plans/issue-178-native-qualification-change-note.md`
and unchanged `tests/test_issue204_native_preflight.py` (including the later N1
test correction). It does not require #204 acceptance or Closed/Done.

During this design task remote accepted main advanced to
`017e7cfb350bf8f2608d08e27fac5b9b72a5809e` with #192. Read-only comparison
confirms none of the six prerequisite paths above changed from deaa75c; #192's
native/core/tests are separate. Use this current main plus the accepted #207
note for composition, preserving **all** accepted #192 changes, including
`roundtrip_v2_native.py`. Do not reset main to #204's older tree or broadly
cherry-pick an entire checkout. Any later main advancement requires the same
path compatibility check before the coordinator fixes the integration baseline.

Before #208 becomes Ready, the coordinator records accepted-main and this exact
input (or an explicitly re-reviewed replacement), freezes #204's shared seams
and grants #208 their exclusive integration ownership. In its own worktree,
#208 adopts the listed bytes onto accepted main plus the accepted #207 note,
retains a source comparison and commits that prerequisite before implementing
the new route. Conflicts or changed bytes require explicit delta review; do not
call the composed tree previously validated. The exact composed commit is
recorded as #208's runtime baseline. This grant covers only these shared seams:

- New `python/vera_timeline_agent/target_identity_v2.py`: identity records,
  host preparation, receipt validation, finite getter operation and consumption.
- `workflow_v2_cli.py`, `workflow_v2_launcher.py`, and
  `integrations/resolve/VERA Delivery v2.py`: finite CLI/action routing,
  declared inventory and pre-import provenance.
- `native_qualification_v2.py`: only the versioned receipt-backed capability
  authority/request branch and its freshness/replay guards; retain existing
  exact-target checks and capability observations.
- New #208 tests and operator/evidence documents only. Do not edit accepted
  tests, #190/#192 native/records, ordinary #177 build guards or v1 helpers.

No in-place edit/cherry-pick into f582 by #208. The coordinator returns one
reviewed integrated revision and source manifest to #204; its owner consumes
that revision and prepares fresh evidence. No reciprocal dependency: #208 is
blocked by #207/#109/#177/#190; #204 is blocked by #208. A baseline proposal is
not a shared-seam grant or dispatch. A missing grant keeps #208 unready.

## Change note: what changes and what breaks

Introduce the finite identity action and three new closed issue-owned records
below. Add a receipt-backed `vera-native-qualification-authority/v2` and
`vera-native-qualification-request/v2` for this route. Their consumer retains
#204's independently issued authority and exact four-field target requirement.
Existing v1 capability records remain unchanged for their existing trusted-input
route; they cannot be used to claim CN-207-ID1 receipt consumption.

The new schemas are local Python records, not shared contracts: no generator
or generated type changes. #109/#177 build/attestation contracts and approved
CN-178-Q1 remain unchanged. Identity approval does not approve preflight or
later effects. The new route additionally pins CN-207-ID1 approval.

Changing any declared runtime/source or note pin invalidates #204's prepared
release SHA256 `d4ec949a5a197a54bc58c969bcb2655553064e4600fb11c6ba2f748bf6f33d66`.
Build and review a fresh complete release; do not merge files into an old bundle
or carry its request/authority forward. Add `target_identity_v2.py` to the exact
runtime inventory and this note to host source pins. Keep pin provenance
external to the note itself; its raw SHA256 is in the acceptance checklist.

## Closed records and scalar rules

These are exact key sets, not extensible examples. `Hash` is raw lowercase
64-hex SHA256 of retained bytes; `Time` is timezone-aware UTC ISO8601;
`Id` is a canonical UUID. No compiler-canonical hash substitution. `Path` is a
canonical absolute local path validated as described below.

| Object | Exact fields and meaning |
| --- | --- |
| Named target | `projectName`, `timelineName`: exact operator-visible strings |
| Observed target | Named target plus `projectUid`, `timelineUid`: opaque native strings |
| Confirmation | `readOnly:true`, `savedDisposableNonproduction:true`, `externalScripting:"None"` |
| Issuer | `implementation`, `pythonVersion`, `hostUser`, `toolSha256`: observed locked host issuer; tool hash matches CLI source pin |
| Binding | `repositoryRoot`, `repositorySourcePins`, `releaseRoot`, `releaseSha256`, `installedRoot`, `evidenceDir`, `approvalPath`, `approvalSha256`, `target` (named target) |
| Authority | `schemaVersion:"vera-native-target-identity-authority/v1"`, `issueNumber:208`, `action:"target_identity_handoff"`, `operator`, `issuedAt`, `expiresAt`, `invocationId`, `issuer`, `binding`, `confirmations` |
| Request | `schemaVersion:"vera-native-target-identity-request/v1"`, `issueNumber:208`, `action:"target_identity_handoff"`, `binding`, `authorityPath`, `authoritySha256`, `invocationId` |
| Runtime | `injectedObjectAvailable`, `implementation`, `pythonVersion`, `platform`, `product`, `version`, `installedRoot`, `installedSourcePins` |
| Read | `readAt`, `target` (observed target) |
| Result | `schemaVersion:"vera-native-target-identity-result/v1"`, `issueNumber:208`, `action:"target_identity_handoff"`, `invocationId`, `status`, `qualified:false`, `verified:false`, `futureEffectsAuthorized:false`, `startedAt`, `finishedAt`, `requestSha256`, `authoritySha256`, `binding`, `runtime`, `reads`, `target`, `reason` |

Result status is exactly `identity_observed` or `stopped_safely`. Success has two
complete agreeing reads, their observed target, and `reason:null`. Failure has
`target:null`, zero to two complete reads and a bounded reason; partial raw
getter failures go in refusal evidence and are never a usable target. Runtime
facts not yet observed are null in a failure, never filled from expectations.

Reject unknown/missing/duplicate keys, wrong schema/action/issue, non-object
roots, nonfinite/overflowing numbers, excess size (2 MiB per record) and scalar
coercions. Booleans use exact boolean type (`1` is not `true`); issue/version
integers reject booleans. Names/UIDs/operator/host strings are nonblank strings
of at most 512 characters, no NUL or control characters. Match names byte for
byte; no trimming, case folding, substring or Unicode normalization. UIDs are
opaque: no conversion from names, UUID parsing or cross-namespace uniqueness
assumption. The version is the exact five-element list `[21,1,1,10,""]`;
product is `DaVinci Resolve Studio`. Future versions require a separate decision.
Actual injected interpreter/platform are recorded, not copied from host issuer.

Approval is a separately retained local receipt with exact keys `changeNote`,
`producerQuote`, `noteSha256`, `recordedAt`; validate `CN-207-ID1`, the exact
accepted response, raw note hash and Time. Source pins have the exact reviewed
inventory keys; installed pins have the exact release file keys. No JSON field
selects a module, executable, method, adapter or alternate credential port.

## Trust, paths and provenance before imports

The trust root is the operator personally invoking the reviewed locked host CLI
and later confirming its retained result, following the local #109 procedure.
`operator`/`hostUser`, timestamps, hashes and file permissions are provenance,
not human authentication or cryptographic signatures. A hash cannot authenticate
its own issuer. Agent request preparation never issues authority or supplies
operator confirmations. A file from an unverified origin is refused even if its
internal hashes agree; hostile same-user replacement is outside this local
procedure's trust model and must not be called authenticated.

Reuse locked CPython 3.12.14 host preparation; identity execution uses only the
declared installed injected runtime. Before importing any installed VERA module,
the stdlib bootstrap independently validates bounded request/authority/approval
bytes, equality of their binding and invocation, expiry, host/source/note pins,
prepared and installed release manifests, its own script bytes, exact runtime
inventory and output separation. Loaded VERA-module residue refuses; operator
restart is required. Undeclared code/imports refuse. Disable bytecode output.
Write `bootstrap-started-<invocationId>.json` exclusively in the checked private
evidence root, binding all hashes/pins and expected names before imports/getters.
This is also the one-use reservation; a concurrent or second launch refuses.
The controller revalidates these bytes/pins after imports before any getter.

Protect repository, prepared release, installed plugin, approval, authority and
both host/installed request inputs. Evidence and authority/request outputs must
not contain or overlap protected inputs in either direction. Authority/request
live outside evidence and source; only the validated immutable request copy may
occupy the declared installed `request.json` slot during the manual install.
Use private roots (0700), exclusive-create records (0400), regular bounded
single-link files, no symlink ancestry, descriptor/lstat identity and extent
checks before/after reads. Compare device/inode ancestry to catch APFS case and
firmlink aliases, not just text paths. Recheck safe output ancestry at each
publication. No overwrite, recursive cleanup or input mutation on success/failure.

An unsafe request's path cannot become a refusal output. Retain refusal only
under an independently validated safe authority binding with the same protected
root checks; otherwise report retention unavailable in the WI Console. No extra
console script is allowed. A report path alone is never proof of completion.

## Finite reads, target drift and honest limits

Allow only `GetProductName`, `GetVersion`, `GetProjectManager`,
`GetCurrentProject`, `GetCurrentTimeline`, `GetName`, `GetUniqueId`.
No general getter enumeration. Check injected object, actual product/build and
all inputs, then read one complete target:

1. Reacquire current manager/project; require project and exact project name
   before reading its UID or accessing its timeline.
2. Obtain that project's current timeline; require timeline and exact timeline
   name before reading its UID. Read only opaque nonblank UIDs.
3. Recheck request/authority/approval/repository/prepared and installed inventory,
   expiry and actual product/build. Reacquire the entire current target and read
   it again in the same order. Require all four values to agree.
4. Recheck all provenance/currentness pins after the second read, then publish
   immutable result and an independently computed result hash record. No
   successful receipt if any check fails or publication becomes unsafe.

Duplicate names elsewhere are not enumerated or resolved. The operator selects
the current target personally and accepts the resulting UID pair; names alone
do not establish global uniqueness. Same-name replacement between reads fails
on UID difference. Two reads are adjacent observations, not a native transaction:
they cannot prove absence of a switch away and back between calls or detect an
edit that preserves UIDs. Require no concurrent UI/job interaction; never claim
content, saved status, nonproduction status or preference None was API-observed.
Those remain explicit operator attestations. #204 independently rechecks its
current exact target; identity capture grants no content or capability approval.

## Freshness, replay, confirmation and receipt consumption

Select a 30-minute maximum local handoff window. Identity authority expires
exactly 1,800 seconds after issue; refuse future-dated/expired/reversed times
at preparation, bootstrap, each read boundary and publication. Refuse observed
wall-clock rollback during execution using monotonic elapsed-time checks. No
resume a partial invocation after process/Resolve restart: prepare a fresh
invocation and authority.

This is a proposed conservative procedure limit, not an experimentally measured
Studio timeout. It keeps observation and operator confirmation in one attended
session. One-use reservations make crashes/replays unambiguous. Their cost is
fresh capture/confirmation if installation, inspection or request transition
takes too long, or if publication is uncertain. The Producer may choose a
different window before acceptance; changing it changes the approved note hash.

An invocation reservation is single use even on failure, crash or uncertain
publication. Inspect retained files read-only; never rerun to complete the old
receipt. Recovery uses new authority/request/UUID/evidence root and fresh reads.
Missing reservation/result/hash lineage, edited records or duplicate completion
are refused; a hash-valid copied receipt without its original private lineage
is insufficient. No background service, signing system or durable job is added.

After success, the operator inspects actual report/runtime/hash and confirms
the displayed current target and all four returned identifiers. A proposed
`capability-authorize-from-identity` command (implemented only in #208) must:

- Validate original bootstrap/result/hash lineage, exact approved note/source/
  installed inventory, two agreeing reads, success and false qualification flags.
  Require the same release, unchanged pins and live operator-selected target;
  reject failed/synthetic/#204 observations and receipts from another invocation.
- Require a fresh operator invocation and explicit saved/nonproduction/read-only/
  None confirmations plus acknowledgement of the exact result hash and four
  identifiers. The CLI derives all four from the result and displays them for
  acknowledgement; no retyping invisible UIDs or editable target substitution.
  Request preparation cannot perform this decision.
- Issue capability authority/v2 with v1's exact top-level authority fields plus
  `identityReceipt` and `expiresAt`. `identityReceipt` has exactly `resultPath`,
  `resultSha256`, `invocationId`, `identityApprovalPath`,
  `identityApprovalSha256`, `confirmedAt`; target remains the four-field target.
  Keep CN-178-Q1 approval/binding and all existing #204 guard requirements.
- Require result age and new authority age each within 1,800 seconds; capability
  expiry is the earlier of its issue + 1,800 seconds and result finish + 1,800
  seconds. Atomically reserve `consumed-<resultSha256>.json` in original evidence
  before issuance; one receipt issues at most one authority, even on uncertain
  failure. Never delete/reset the marker to retry.

Capability request/v2 retains v1's exact request fields. Its hashed authority
binds the new receipt and expiry. Its bootstrap/consumer revalidate the receipt,
consumption ancestry, approval/source/release and freshness before getters;
reserve its own one-use invocation and enforce #204's exact current names/UIDs
before capability reads. Refusal or clock uncertainty requires fresh capture.
Changing target/name/release/source requires fresh capture and confirmation.
A completed receipt may survive the required #109 quit/archive/request/restart
transition to preflight within the same 30-minute window: preserve the original
identity request/receipts, install the new capability request through that flow,
and have the operator reopen the same saved target and confirm it again. The
new launch must independently match the receipt's UID pair before further reads.
An unexpected restart or uncertain target history requires fresh capture; a
partial invocation never resumes. There is no automatic progression from receipt to
preflight, and no progression from preflight to effects.

## Verification and Producer acceptance

#207 uses documentation confinement, whitespace and local-link checks plus
adversarial static review of the design. No fast/full/test/Claude/native job runs.
No existing validation is claimed as a new pass for this note. #208 must satisfy
[negative cases and actual-app evidence](../verification/issue-207/implementation-checklist.md):
focused/fast checks, required independent adversarial review/fix/delta review,
approved operator identity and #204 preflight evidence, runtime fixes/delta review,
then final qualifying full evidence on the delivered integration state. Actual
identity alone does not close #204; each issue retains its acceptance authority.

Producer reviews [the exact hash and short ordered checklist](../verification/issue-207/README.md).
The remaining product judgment is this name-bound, finite observed-identity route
with separate confirmation, 30-minute window and one-use retry semantics.
Approval accepts this design only. Keep #207 In review until explicit acceptance;
#208 stays undispatched pending Closed/Done design, ownership and runtime gates.
