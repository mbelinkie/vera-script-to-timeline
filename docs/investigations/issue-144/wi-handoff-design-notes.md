# WI handoff design notes — pending executable plan and Claude review

These notes record the remaining handoff boundary while checkpoint12f full
validation runs. They authorize no implementation or live action and are not
an operator runbook or a completed acceptance artifact.

## Existing executable host seams

`ProofSession.run(action)` is the actual shared file-driven implementation.
`python -m vera_timeline_agent.roundtrip_proof` exposes build, bind-baseline,
propose, decide, bind-omission-evidence, propose-omission, decide-omission,
generate-omission, rebuild, promote and status. The CLI constructs the session
without native/capture/evidence/service injections. Build and capture therefore
wait for the guarded boundary, and generation requires an explicit service.
No CLI flag silently authorizes live or paid effects.

The root owns four literal build inputs: proof-request.json,
script-document.json, compiler-dependencies.json and materialization-plan.json.
The authoritative pointer is root/baseline.json. Immutable baseline content is
baselines/<hash>/baseline.json. `_capture_files` emits
captures/<basis-hash>/<nonce>/request.json with target, purpose, binding,
snapshot, evidence lane, manifest/identity path+hash, package root and source
hash inventory. Response must contain exactly schemaVersion, nonce,
requestHash, observationA and observationB. Two adjacent complete equal reads
and the action-specific host validator are required before consumed.json.
Hashes/nonces establish file consistency, not live capture provenance.

Visual capture includes verified birth occurrence IDs. Omission capture has its
own raw complete schema and deliberately carries no invented event IDs for
split items. Only the selected linked narration/companion can associate split
UIDs through the complete source/media/track binding. Composition's projected
visual observation stays transient inside TypeScript; WI must never emit it.

## Exact existing support and missing qualification

Accepted #141 retained direct SDK reads include project/timeline GetUniqueId,
full track/item inventory, item GetStart/GetEnd/GetDuration and fractional
variants, source bounds, speed/enabled state, reciprocal GetLinkedItems, media
GetUniqueId/GetClipProperty and local source-byte reachability. That evidence
does not prove complete bus/mix/effect routing. Unknown getters or controls must
be retained as unknown/error and fail qualification; manifest expected facts
cannot fill the missing native facts. Defaulting missing controls to neutral
would create a false complete-mix claim.

Historical positives use different builds: linked +25 placement/-25 end trim
on Studio21.1.0 build14; W1 rendered omission on Studio21.1.1.10. #145 must
select one actual build and qualify all three, standalone row narration topology,
proof-link setup, complete controls/routes, independent source supports,
calibration and edited/full-rebuild renders, actual assembly compensation,
saved/reopened targets, provider preparation and audio timing provenance.
Existing `real_issue145` gates deliberately refuse automatic qualification.
These are named readiness blockers, not a claimed real integrated result.

## Small WI entry requirements for the later reviewed plan

One issue-owned stdlib-only file, independently stageable into the already
approved WI boundary, can read an exact request file and an explicitly supplied
Resolve handle. Do not import Python3.12 host/package/provider dependencies into
WI or derive native facts from package echo. Current target identity, declared
disposable ownership, request/code/source drift and path safety must be checked
before effects. Capture is read-only; linking/rendering requires their explicit
request and an exclusive pre-effect record, with uncertain results waiting for
read-only reconciliation rather than retry. No project selection, broad folder
search, installation, service call, live effect or protected-target mutation is
authorized by writing this entry.

The next plan must settle which facts the stdlib entry itself reads, which
qualified independently observed complete-control/support/render adapters #145
must supply, how the host consumes exact file responses, and how the existing
actual NativeStages factory/inspector receives its explicit boundary. Do not
pretend the current no-injection CLI is an operational real-run driver. Supply
one executable synthetic demonstration plus the numbered real operator flow
with the exact named qualification gates. A manually rewritten script, forged
observation, unqualified render or all-refused case cannot pass either run.

## Required operator ordering

Prepare and validator-check accepted #148 input/media/narration; build a fresh
uniquely named disposable target through actual #34/#35; verify initial native
facts; explicitly link the selected proof pairs; bind baseline; bind pristine
complete-route/source-support/calibration evidence **before editing**; perform
and retain the named linked move, safe trim and spoken omission; capture and
inspect the deterministic proposals; explicitly accept/reject the described
bundle; validate the new canonical script/readable comparison; generate one
complete revised-row temporary recording through the separately approved
service; rebuild/verify/save/reopen a new target; promote only after verification.
Confirm old source/script/timeline inputs remain intact. Preserve every refusal,
interrupted job and uncertainty as visible state.

The final matrix must name every input/output schema, canonical/raw hash binding,
actual build/job receipt, observation authority, decision file, replacement
asset/marks, verification/promotion boundary, evidence level and readiness owner.
No paid/cloud generation, fixture/contract migration, transcript route or source
acquisition is introduced by this handoff. Final code and runbook both require
Claude review and exact retained automated checks before #144 can finish.
