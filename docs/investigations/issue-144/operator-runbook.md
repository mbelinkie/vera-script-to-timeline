# Issue144 operator runbook

This describes the implemented harness and synthetic file/WI walkthrough.
Final review and identified-commit validation are recorded separately before
acceptance. No real integrated result is claimed. #144 Automated acceptance
covers the harness/safety checks; #145 requires actual real three-edit evidence.

## 1. Pin code and prepare the four literal inputs

Use branch `codex/issue-144-roundtrip-harness` and the executable source commit
identified in final evidence. Baseline9c8973de6b02eb89cb57a03c0bd50480af73f9e1
includes #34 source2586dde/integration7065715, #35 source4354c63/integratione3bb5fd,
and #141 publication03ef585. #131 representation817d0e5/handoffac0f5d9 is retained
evidence, not merged code. Do not assume main includes accepted work.

Use Node24.19.0/npm11.17.0, Python3.12.14, locked `npm ci` / `uv sync --frozen`.
Source/lock/input/media hashes bind the proof; do not change them during a run.
The proof directory must be an independently owned existing local path, with
no symlink parents or symlink/hardlink files. Exact inputs:

- `proof-request.json`: exactly schemaVersion=`issue-144-prepared-build/v1`,
  evidenceLevel=`synthetic_injected` for the demo, verifiedAt=fixed valid package
  verification timestamp. `real_issue145` is a future declared lane; it cannot
  establish qualification or enable the current real execution gates.
- `script-document.json`: validator-passing ScriptDocument v1, producer-approved
  canonical revision with stable row/token/visual/media identities.
- `compiler-dependencies.json`: actual compiler frame/time/track/source/narration
  inputs, matching complete row text/version/audio and actual timing marks.
- `materialization-plan.json`: actual compiled source IDs mapped to exactly
  artifactId, origin and policy=`copy`. Narration artifactId is its dependency
  assetId; every origin is already available verified local media.

Outputs retain raw input/source hashes, actual manifest/report, package bytes,
durable job/stage receipts and target identity under the input-derived run ID.
No manually invented compiler IDs or expected-package echo counts as readback.

## 2. Reproduce the executable synthetic walkthrough

From the pinned checkout, choose a new absolute independently owned directory:

```sh
ctx-wire run rtk proxy npm exec --yes --package=node@24.19.0 -- uv run --frozen python tests/issue144_wi_demo.py --output-directory /absolute/new/owned/demo-directory
```

The script calls the actual `roundtrip_driver.main` CLI in one process so its
explicitly fake native world/cache persist between commands. Actual accepted
assembly calls populate that world; WI getters read stored state and explicit
fake editorial actions mutate it. Compiler/package/jobs/assembly/cache/service,
staged requests/responses, guarded proof links and current full-program stereo
queue/inspection use their actual implementations. The host audio verdict uses
trusted synthetic supplier receipts; it does not bind their job IDs to the WI
render records. Pristine calibration bypasses WI. Supports, calibration,
renderer and provider remain synthetic. This is not cross-process
native-app execution or real qualification. Test command:

```sh
ctx-wire run rtk proxy npm exec --yes --package=node@24.19.0 -- uv run --frozen pytest -q tests/test_issue144_wi_flow.py
```

Expected success: one provider request, two targets, six proof-link calls,
picture-only refusal without canonical/pointer/provider change, linked move(+25),
linked end trim(-25) and interior primary Charlie omission accepted together;
one revision, complete replacement row, fresh marks retiming anchored cuts,
unchanged following row/local cuts, an unlinked rebuilt-target promotion refusal,
explicit links on that new target, and stable decision/generation/build/promote
replay. Failed/interrupted directories are retained; no overwrite/cleanup.

Expected artifacts: `demo-result.json`, numbered `commands/*.json`,
`proof/operator-boundary.json`, captures with request/raw-0/raw-1/response/consumed,
WI intent/effect/complete records, canonical comparison and all host receipts.
Link completion is effect.json; render completion also has complete.json.
Every receipt records or binds its evidence level. Reject and other refusal
branches are tested separately. Synthetic success cannot close #145.

## 3. Prepare #148 and settle real readiness blockers

#148 retains the approved60–120s private source snapshot/hash, canonical script,
readable two-column projection, stable source-cell/row/token/asset mapping,
exclusions and actual OC/VO/visual intent. Keep private bytes/paths out of fixtures.
Supply the four files above, matching already available narration/marks, source
bytes and usable handles. Missing audio/timing is a named preparation gate;
#148/#144 authorize no synthesis, acquisition, upload or native effects.

Choose one narration row with two distinct ready use_source visuals and a muted
full-row video companion. The exact compiler must yield unique supported +25
move and -25 trim candidates, with coverage/clearance/handles. Choose an interior
contiguous primary word/phrase omission with retained neighbors; no removed
visual/host/annotation/beat anchor endpoint. Edge deletion, punctuation in joining
gaps and partial-word ambiguity refuse. Keep the following unchanged row.

Bounded audio profile:25fps, frame-aligned mono48k PCM16/24 independent sources
(actual narration build inputs require PCM24),
unique/non-aliased, at most8sources and64primary tokens, complete programme at
most3million samples. At25fps/48k this permits1562 complete frames=62.48seconds.
#148's snapshot must map to an approved complete programme within this bound;
a longer programme is a readiness blocker. Do not truncate, pad, silently reduce
coverage or enlarge the cap. Target an approved complete programme close to
60seconds; the upper part of the nominal60–120s range is not usable here.
Ready AV only: the WI reader does not qualify still,
placeholder/Fusion items. Music, cross-row composition, mixed bundle choices and
general human finishing are outside this positive profile.

#145 first qualifies one installed Studio build, actual assembly/readback and
compensation, observer/getters, complete mixer/route/FX/control reader,
independent full source word supports, original stereo calibration, edited and
rebuilt full-program renderer, source/time/sample bounds, whole-row provider/
service provenance and approved data/cost policy. Historical positives from
separate builds do not prove all three on one build. Matching hashes/nonces
prove consistency, not qualification. Current real native/audio/service gates
remain closed; #145 must supply separately reviewed qualification changes.
No boolean, synthetic relabeling or all-refused real run satisfies that gate.
Transcript use would require accepted #146 first; this lane uses no transcript.

Run the local preflight before any boundary is supplied:

```sh
ctx-wire run rtk proxy npm exec --yes --package=node@24.19.0 -- uv run --frozen python -m vera_timeline_agent.roundtrip_driver preflight --proof-root /absolute/owned/proof
```

Expected `prepared`, evidenceLevel=`local_prepared`, actual compiler outputs and
`runs/<snapshot-id>/preflight.json`. No job, boundary loading, synthesis or target
effect occurs. The receipt explicitly lists the full three-edit/audio/native
profile as unchecked: it verifies local bytes/compiler inputs, not every positive
case above. #148 must retain separate suitability checks; #145 must qualify the
external seams. Supplying boundary flags refuses before loading the boundary.

## 4. Build a fresh target, link proof pairs and bind baseline

Exact host entry, repeating these flags for every action:

```sh
ctx-wire run rtk proxy npm exec --yes --package=node@24.19.0 -- uv run --frozen python -m vera_timeline_agent.roundtrip_driver build --proof-root /absolute/owned/proof --boundary-file /absolute/reviewed/operator-boundary.py --boundary-sha256 sha256:<reviewed-file-digest>
```

The explicitly trusted boundary file defines `FILE_PINS` (absolute-file/SHA256
mapping, at most128 additional entries) and `make_boundary(proof_root)` returning
only existing native_provider, capture, omission_evidence, narration_service
arguments. The native provider returns an actual NativeStages for the exact
PreparedBuild; the service is the existing NarrationService. Review import/
factory construction for no native/paid effects. No automatic discovery/connect.
The immutable root operator-boundary.json binds all pins. Changing a retained
boundary/pin refuses before its changed module loads; code changes need a
separately approved fresh run. Hashes do not sandbox explicitly trusted code.

Actions: preflight, build, resume-build, bind-baseline, propose, decide,
bind-omission-evidence, propose-omission, decide-omission, generate-omission,
rebuild, resume-rebuild, promote, status, compare.
generate-omission, rebuild, resume-rebuild, promote and compare require the returned
`--decision-key <64 lowercase hex characters>`. JSON successful statuses exit0;
waiting/needs_action/failed/refused/recovery_blocked exit2;
process/OS/import faults exit70.
Retain all outputs. Missing boundaries wait/refuse. For real runs these commands
are conditional on #145's qualification changes, not authorization under #144.

Build verifies a fresh disposable project/timeline, source bytes, actual settings,
full tracks/clock/source/record geometry and birth item/media UIDs. Name collision
or lost creation response returns recovery_blocked with retained evidence;
never blindly create another target. Explicitly link the move and trim video/
audio pairs and primary narration/muted full-row companion. Read back equal
geometry and reciprocal links. No protected target is mutated.

The independently stageable stdlib file is
`python/vera_timeline_agent/roundtrip_wi.py`. Load the pinned file in the approved
WI environment and supply an explicit Resolve handle; it imports no host/provider
modules and never connects/selects a target. Callable interfaces:

```python
wi.inspect_native(
    resolve_handle,
    manifest,
    package_root=package,
    version=pinned_version,
    project_uid=project_uid,
    timeline_uid=timeline_uid,
)
wi.capture(
    resolve_handle,
    request_path,
    proof_root=proof_root,
    source_root=pinned_checkout,
    version=pinned_version,
    request_hash=literal_request_sha256,
    code_hash=pinned_wi_sha256,
    audio_controls=qualified_complete_control_reader,
)
wi.perform(
    resolve_handle,
    action_request_path,
    proof_root=proof_root,
    source_root=pinned_checkout,
    version=pinned_version,
    request_hash=literal_action_sha256,
    code_hash=pinned_wi_sha256,
    render_boundary=qualified_renderer,
    inspect_render=False,
)
```

Capture consumes the host request at captures/<basis-hash>/<nonce>/request.json.
Exact14 fields: schemaVersion, purpose, binding, snapshotId, evidenceLevel,
manifestPath, manifestHash, identityPath, identityHash, expectedIdentity,
packageRoot, sources, nonce. Schema is issue-144-capture-request/v1 or
issue-144-omission-capture-request/v1. Matching response schema carries exact
nonce/requestHash and observationA/B. It retains two actual structural raw-N.json
reads before response publication; failure retains refused.json and no successful
response. The host's consumed.json binds the fresh response.

Readbacks compare actual product/version/current UIDs, names/settings/extent,
all native track counts/slots/names, all item/media UIDs, online verified bytes,
enabled/speed, reciprocal links and integer/fractional geometry. WI capture does
not include marker readback; NativeStages verification separately checks markers.
Intermediate slots created by accepted assembly must be observed empty; their
actual names are retained in raw emptySlots. Unknown fields, hidden gap items,
unavailable controls or fractional uncertainty refuse. Managed IDs/roles are
assigned after actual slots/names agree. NativeStages keeps its existing exact
readback shape; raw captures additionally retain empty-slot facts.

For proof-link/render, retain a separate request.json under a unique owned nonce
folder. Copy the14 bound request fields, set schemaVersion=issue-144-wi-action/v1,
add action, parameters, expectedObservationHash (SHA256 of wi.encoded of the
current adjacent complete wi.read_native facts). Link parameters are exactly
`{"pair":["actual-video-item-uid","actual-audio-item-uid"]}`: two distinct
unlinked enabled100%-speed items with equal record/source geometry. Call perform
with the literal request hash. Linked means the sole observed change is reciprocal
links. Exclusive fsynced intent precedes the effect; uncertain intents never retry
or acquire new effect permission through a different nonce.

Render parameters are exactly outputPath (new owned absolute WAV) and settings:
format=wav, scope=full-program, sampleRate=48000, channels=2, sampleWidth=2 or3,
startFrame/durationFrames equal the full manifest extent. Qualified callable:
`renderer(resolve_handle, "queue"|"inspect", parameters, retained_job_or_None)`.
Exact job: jobId, projectUid, timelineUid, settings, outputPath, state (queued,
rendering, complete). After queued, inspect the identical request with
inspect_render=True. Inspect never starts/restores/deletes jobs. Complete means
stable full stereo PCM48k16/24 and integer frame-aligned sample count within the
cap. Pending returns needs_action. Lost queue response requires qualified
read-only unique owned-job lookup with job=None; otherwise preserve uncertainty
and never queue twice. Real calibration/controls/supports and full-program
rendering remain #145 gates; the demo calibration is an independent fixture.
The exact supplier files, strict fields, limits and required WI-to-host render
bridge are in [audio-evidence-contract.md](audio-evidence-contract.md).
Executed WI render records currently do not authorize the host audio verdict.

Run bind-baseline only after proof links/facts pass. Expect immutable
baselines/<hash>/baseline.json and root baseline.json pointer. Old original
rebind cannot advance a promoted pointer. Write omission-request.json exactly:

```json
{"schemaVersion":"issue-144-composed-request/v1","rowId":"<canonical row UUID>"}
```

Run bind-omission-evidence BEFORE edits. Expect immutable pristine preparation,
complete selected primary/source profiles, controls and original calibration.
No provider word-end guesses or assumed neutral mixer fill missing facts.

## 5. Make all three linked edits and propose

On the qualified disposable target, move the selected linked visual pair+25frames
without source/control changes. Trim the distinct linked pair's end by25frames,
starts unchanged. Excise only the interior spoken primary support interval with
its linked muted companion; retain complete neighboring supports. A mute or
picture-only cut does not authorize narration deletion. Capture all actual
occurrences/source/control facts and complete stereo edited render. New split
UIDs belong only to the selected primary pair; all others retain birth UIDs.

Run propose-omission. Expect deterministic issue-144-composed-proposal/v1,
exactly two actual compiler-confirmed visual candidates, complete audible omission
verdict and canonical prepared candidate. The temporary visual projection stays
in semantic memory; auxiliary route allowances derive from compiler output.
Refused/unsupported reports are retained and cannot be accepted. Fix readiness
through its owner; never rewrite reports/script JSON or silently drop a positive.

## 6. Decide and inspect the validator-passing canonical revision

Read actual proposed text, tokens/anchors, source/geometry/audio evidence and
limitations. Write omission-decisions.json exactly:

```json
{"schemaVersion":"issue-144-composed-decisions/v1","reportHash":"sha256:<actual report digest>","choice":"accept"}
```

Reject rejects all three; mixed choices are unsupported and no missing choice
means accept. Run decide-omission. Expected prepared_revision plus canonical
script and regeneration request under decisions/<decision-key>/build; rejection
retains a receipt without replacement. The host rederives report/transformation
and captures fresh state. Stale/forged choices refuse before provider/native
changes; original script and pointer persist.

Run compare --decision-key <key> with the same flags. Expected
`decisions/<key>/canonical-comparison.md`: actual before/after wording, unspoken
section headings, OC/VO ranges, visual labels/anchor quotes/audio policy, script
hashes, decision and evidence. Formatting this retained canonical revision does
not approve execution or certify current native state. Use host validation, never
a handwritten replacement. The standalone visual lane's decisions.json uses
issue-144-decisions/v1, reportHash and explicit decisions entries; the required
three-edit proof uses the composed format above.

## 7. Generate one whole replacement row and rebuild a fresh target

Run generate-omission --decision-key <key> with the reviewed service. Request is
COMPLETE revised row wording; one new recording, new marks/provenance/cache
binding, no splicing/old timing reuse. Expect finalized plus immutable generation
inputs, actual synthesis/normalization/cache, row-handoff, canonical new dependency/
plan/preview and generation receipt. Untouched rows preserve content/audio/source/
local cuts; absolute starts translate. generation-inputs.json records preparation.
Only `generation-calls/<request-hash>/intent.json`, written immediately before
the actual service call after validation, reserves a possibly attempted request.
An earlier validator fault can retry with no provider call. Once that shared
intent exists, missing synthesis cache refuses across all decision keys; cached
synthesis may safely finish normalization. Final generation binds the intent
hash and complete cache bytes. Replay never creates a missing call intent.

Run rebuild --decision-key <key>. Compiler/package/job output must match the
retained generation preview before native intent. Build a new target; verify
actual source/record geometry and replacement recording after save/reopen.
#145 additionally qualifies the complete rebuilt programme render. Failure leaves
prior authoritative script/pointer/targets intact and retains jobs/evidence.

On the NEW rebuilt target, repeat section4's three explicit WI link actions:
the move pair, trim pair and narration/muted companion. Use the rebuilt identity,
package/manifest/source hashes and actual new item UIDs from its capture request;
initial target links do not transfer. Each action needs the current adjacent raw
observation hash, equal geometry and reciprocal exactly-two link readback. Then
capture fresh complete pristine observations for promote. The fixture makes
this setup a numbered explicit step; capture itself never links. Premature
unlinked promotion refuses and retains content-addressed validation inputs. After
explicit links a new capture/validation record can succeed without overwriting
that refusal, another provider request or another rebuilt target.

For a retained waiting/failed job, use `resume-build`, or `resume-rebuild
--decision-key <key>`, with the same reviewed boundary flags. The proof lock,
literal inputs/source/media, #35 completed-stage integrity, current accepted
decision/capture and compiler preview gates apply before immediate continuation.
Known safe cases are no native creation intent, or an exact verified result with
fresh independent read-only reconciliation. The latter never calls creation again.
Ordinary build/rebuild does not silently resume a waiting job.

Missing/partial/foreign intent/result, unverified/stopped_safely result, failed
mutation, or retained integrity failure returns `recovery_blocked`. Preserve all
files and targets; do not delete intent or change decision whitespace to retry.
This terminal boundary requires #145's independently qualified operator recovery.
A separately authorized fresh baseline run may use fresh compiler build IDs and
retain the old proof. Rebuild IDs are deterministic from the accepted revision:
changing a decision key cannot authorize a fresh uncertain target or service call.

## 8. Promote once, replay and preserve all evidence

Run promote --decision-key <key> only after new-target verification AND the
explicit rebuilt-target proof links and fresh capture above. Expected
promoted, new immutable baseline and compare-and-swap pointer advance. Replay
identical decide-omission, generate-omission, rebuild, promote; receipts/provider
request count/target count/pointer stay unchanged. Preserve old script/media/
timeline and all failure evidence. Equality of untouched rows is proved through
a fresh rebuild; native reuse/arbitrary human-finishing preservation is #104.
Prompter lock/override/reshoot/pickup script behavior is #153, outside this lane.

Final evidence identifies executable commit, exact commands/results/hashes and
compact seam matrix. Real #145 acceptance still needs all three actual positives,
real revised whole-row VO, fresh verified target and full-program output. Harness
tests, hand-written JSON, synthetic output or all-refused real flow do not suffice.
