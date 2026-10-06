# Issue144 seam matrix

The entries describe implemented seams. Final review and identified-commit full
validation are retained separately before acceptance. Tests are synthetic;
no real integrated result or #145 qualification is claimed.

## Starting authority

Dedicated branch `codex/issue-144-roundtrip-harness`, task
`01a103aa-e47a-79e0-88b5-62e6d9637d1b`; clean accepted task baseline
`9c8973de6b02eb89cb57a03c0bd50480af73f9e1`.
Accepted #34 source2586dde/integration7065715, #35 source4354c63/integratione3bb5fd,
#141 publication03ef585 are pinned and compared in the main plan. #131's retained
representation evidence817d0e5 and handoffac0f5d9 are evidence, not merged code.
Checkpoint12f source29059f8 fully validated (329 Python/231 contracts).
Checkpoint12g2 source8d072fa combines all three edits and has retained focused
checks/regressions/Claude review. Checkpoint13a source7dc501c adds the reviewed
stdlib WI reader/effects. Final evidence pins the completed executable source
and its full checks. No real effects occurred here.

## Actual boundaries

| Entry / authority | Literal input → retained output | Binding and evidence |
| --- | --- | --- |
| PreparedBuild / `python -m vera_timeline_agent.roundtrip_build` | proof-request.json, script-document.json, compiler-dependencies.json, materialization-plan.json → immutable run inputs, durable job and core-stage/package receipts | Exact operator JSON gate, pinned Node24.19.0/Python3.12.14, source/lock/input/media hashes; local_prepared before native integration. Native boundary missing → waiting. |
| driver preflight / explicit resume-build and resume-rebuild | Four inputs → local preflight receipt without job/boundary; retained waiting/failed job → guarded immediate continuation or recovery_blocked | Full positive profile remains explicitly unchecked by preflight. Resume under proof lock requires completed-stage integrity and no creation intent, or exact verified result plus fresh read-only reconciliation. Missing/unverified/foreign evidence remains terminal; never clear intents/retry uncertain effects. |
| Actual compiler stdout / issue-144-compile-cli.ts | Validated document/dependencies → literal manifest/report and envelope | Runtime, source/schema/lock/raw input hashes; compiler_only. Existing frozen golden bytes remain exact. |
| NativeStages explicit adapter factory + independent inspector | Actual verified package/manifest → exclusive intent, accepted #34 assembly result, complete native identity/readback | Durable #35 job, package-relative source bytes, track/clock/source/record geometry and UID association. Tests inject fake native objects and label synthetic_injected; expected package facts never establish live provenance. |
| Isolated proof-link setup | Verified fresh native pairs → reciprocal exactly-two links | Explicit setup precedes initial binding AND rebuilt-target promotion; capture never links. Premature refusal retains hash-addressed validation evidence and can be corrected with a fresh capture. Unlinked use_source pairs cannot bind. Narration omission also requires one muted full-row video companion with identical geometry and reciprocal links. Live setup qualification belongs to #145. |
| ProofSession `bind-baseline` | Two complete equal pristine captures → baselines/hash/baseline.json and root/baseline.json pointer | Actual compiled baseline and managed birth UID/source map, native target/settings, input/code hashes. Rebinding a superseded original cannot advance the pointer. |
| File-staged `_capture_files` | captures/basis/nonce/request.json → response.json, consumed.json or refusal | Exact request hash/nonce/schema, adjacent complete equal observations and purpose-specific validator. Unknown facts refuse; file hashes are consistency, not authenticity. Missing fresh response → needs_action. |
| `propose` / unchanged proposeVisuals | Actual baseline/current document/deps/manifest and visual captures → deterministic report | Unique linked +25 move/-25 end trim; unchanged source/control/UID facts, actual compiler token-boundary reproduction, track clearance and coverage. Moving a visual never reorders narration. |
| `decide` / applyVisualDecisions | Exact reportHash and all explicit proposal choices in decisions.json → canonical revised document/deps or rejected receipt | Re-derives actual report and fresh capture; new IDs from actual canonical revision. Unsupported/malformed/stale choices refuse. Historical identical replay verifies retained authority. |
| `bind-omission-evidence` | Exact selected row request and pristine complete native graph → immutable preparation/profile/source/calibration evidence | Actual primary Narr source selected by compiler; sources are verified independent mono48k PCM16/24, frame-aligned, unique and non-aliased. Explicit synthetic supplier only; real qualification refuses. |
| `propose-omission` / complete audio verifier | Fresh split-pair raw capture + pristine profile/calibration + complete edited render → full audible report and canonical prepared omission candidate | Complete observed routes/controls/source supports and both channels; bounded full reconstruction, interior contiguous primary token omission, no partial/residual inference or unrelated route changes. Picture-only/disabled/offline/unknown facts cannot authorize text deletion. |
| `decide-omission` | Exact report hash and accept/reject in omission-decisions.json → prepared_revision + script/request, or rejected receipt | Re-derives full raw report/evidence/actual transformation and fresh capture; no provider/native effect or pointer promotion. Rehashed status/text claims have no authority. |
| `generate-omission` / actual NarrationService | Accepted prepared script + explicit synthetic whole-row service → generation-inputs.json, actual cache, row-handoff.json, canonical new dependencies/plan/preview and generation.json | Immutable decision/service/request/normalizer/cache binding plus one shared request call intent across all decision keys, published after validation immediately before service processing. No intent allows safe preparation retry; existing intent requires retained synthesis. Actual full revised text generates one asset; actual new marks replace old timings. Replays compare all selected cache metadata/payload bytes and rerun actual handoff/finalization without another provider request. Missing boundary waits; changed/missing retained cache refuses. |
| `rebuild --decision-key` | Re-derived accepted receipt/replacement + current fresh edited capture → new actual compiler/package/job/native target | New source is exactly the replacement full-row recording; unrelated source declarations/origins stay equal. Durable manifest/report bytes must equal preview before native intent/factory. Old authoritative files/targets persist through failure. |
| `promote --decision-key` | Verified new target with complete pristine readback → one new immutable baseline and CAS pointer replacement | Compare previous pointer, fsync/atomic replace only after verification. Interrupted publication reconciles without another advance or native effect. Identical historical decision replays do not authorize new effects on an obsolete baseline. |
| Composed request / propose-omission / decide-omission | issue-144-composed-request/v1 rowId + raw same-target three-edit capture → issue-144-composed-proposal/v1, actual canonical revision through one explicit issue-144-composed-decisions/v1 accept/reject | Implemented. Temporary projection stays in memory; two linked visual candidates use unchanged accepted semantics, auxiliary route allowances come from actual compiler preview. One row/document revision and full-row replacement; no mixed choices or cross-row composition. |
| roundtrip_wi.py inspect_native / capture | Explicit Resolve handle, pinned version/UIDs/package/source/code and literal host request → adjacent actual raw-N.json, exact response.json or refused.json | Implemented stdlib-only reader; actual getter/source bytes, no expected geometry/default controls. Exact managed tracks plus observed empty intermediate slots; unknown gap items/fractional/media facts refuse. Declared evidence label is not qualification. |
| WI perform link / render / inspect_render | issue-144-wi-action/v1 + current complete observation hash and exact pair/output/settings → exclusive fsynced intent/effect/complete records | One effect per target/pair/output. Lost responses only read-only reconciliation; never repeat uncertain link/queue. Explicit qualified renderer required; stable bounded full stereo PCM and job identity. #145 qualifies actual live boundary. |
| python -m vera_timeline_agent.roundtrip_driver | Existing host actions + explicit boundary-file/SHA256/FILE_PINS → same ProofSession receipts and immutable operator-boundary.json | No discovery/default connection. Existing exact NativeStages/NarrationService only. Retained changed code/pins refuse before module execution; callback/source guards before/after. Boundary code is explicitly trusted, not sandboxed. |
| compare --decision-key | Verified accepted canonical preparation → decisions/key/canonical-comparison.md | Actual before/after wording, section headings, host visibility, visual anchor/audio policy, script hashes, key/evidence; read-only formatting, not approval/current-native certification. |
| tests/issue144_wi_demo.py --output-directory | New owned directory → numbered literal CLI records, demo-result.json and full host/WI evidence | In-process actual CLI and compiler/package/job/assembly/service with stored fake native getters, fixture supports/calibration/render/provider. Host audio supplier job IDs are not WI-bound; calibration bypasses WI. Three linked edits, picture-only and unlinked-promote negatives, whole-row regeneration, explicit fresh-target links and replay; synthetic_injected only. |
| operator-runbook.md | Numbered exact input/command/WI/decision/output procedure → #148 input preflight and conditional #145 three-edit run | Real native/audio/service gates remain closed until #145 qualification, including the exact WI-to-host audio render bridge in audio-evidence-contract.md. Independent source supports/calibration/controls/render/provider are named blockers; no all-refused or narrower substitute. |

## #148 input requirements to carry forward

The actual issue body currently lists dependencies #144 and #24. Prepare the
producer-approved60–120-second private source snapshot, exact canonical script
revision and readable projection, stable source-cell/row/token/asset identities,
mapping/exclusion decisions and media map. Preserve approved wording/order,
OC/VO intent, parked material and citations. Unsupported authoring intentions
belong in the private coverage record; do not invent canonical fields.

Supply all four literal build inputs with verified already-available local
narration, source bytes, marks and usable handles. Hash the snapshot and local
assets; keep private roots/source out of committed fixtures. Pin accepted harness
commit/runtime and proposed three-edit identities. The selected old timings must
allow the actual compiler's unique +25 linked move and -25 linked trim, while
the interior omitted primary token has retained neighbors and no removed anchor
endpoint. Missing source/audio/timings or unsuitable boundaries are readiness
blockers. #148 authorizes no synthesis, acquisition, upload or native build.
If narration is absent, name preparation/authorization ownership explicitly;
do not claim narration-dependent preflight passed.

## Evidence level and remaining real gates

Compiled/file consistency is compiler_only or local_prepared; fake native,
supports/provider/render are synthetic_injected. Historical W1 complete PCM
consistency is retained and unqualified when controls/support topology cannot
be independently proven. `real_issue145` is a declared future lane, not a
self-attesting operator flag. A matching nonce or rehashed JSON cannot promote
an injected result into live evidence.

#145 must qualify initial assembly/readback and proof links, same-build +25/-25
edits, standalone narration split topology, full enabled route/control inventory,
independent full token supports and sample/time bounds, unchanged calibration,
complete stereo edited and rebuilt renders, exact render-job/settings/output
identity, whole-row service provenance/approved cost and data policy, fresh
targets after save/reopen and old-target preservation. Account for non-frame-
aligned production audio explicitly; this bounded profile rejects EOF partial
frames rather than silently dropping or padding samples. Without those gates,
the real three-edit run remains blocked and no narrower/all-refused result
counts as acceptance. Transcript use would require accepted #146 first.

## Supported mapping, refusals and future scope

Supported synthetic mapping: linked visual+25 move → its anchored range; distinct
linked end-25 source trim → its anchored range; independently verified complete
audible interior primary omission → one complete new row text/version/audio/marks.
New marks retime every anchored cut. Untouched following row content/source/local
cuts remain equal; absolute placement translates through a new target. Visual-only
changes retain VO. No row reordering inference from visual movement.

Tests refuse wrong target/source, duplicate/ambiguous occurrences, stale edits,
malformed/forged decisions, partial support uncertainty, residual speech,
picture-only cuts, unavailable/offline media, unknown controls and uncertain
native effects. Rejection/refusal never replaces canonical input/pointer. No
baseline advance before successful result verification; replay has one authority.

Full programme is bounded to3M48k samples. At25fps that is1562complete frames
(62.48s); #148's approved60–120s snapshot must yield an approved complete programme
within this cap or an explicit blocker. No padding/truncation/lower coverage/cap
expansion. Reader is ready AV only; still/Fusion/placeholder readback is unqualified.

Live three-edit/provider feasibility is #145, including local word-support timing
selection (#51/#63 research lacks a qualified selection; #45 still needs one).
Human finishing/preservation (#104), cross-row music (#100), richer graphics (#8),
transitions (#88), post-prompter guard/reshoot/pickup export (#153) are separate
requirements. Their roadmap coverage/risk audit is retained; no production feature
or priority change is implemented by this harness.
