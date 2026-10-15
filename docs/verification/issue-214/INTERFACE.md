# Pure output-consistency interface for #209 and #215

Pure implementation has actual independent review02/03 GO. Complete final local
acceptance remains pending; see ACCEPTANCE.md and retained review limitations. Accepted authority and exact operative plan are
in `docs/plans/issue-214-output-consistency.md` (unchanged copied bytes,
SHA256 c701b997ed448cf581377dfc819be4e8f0e547d719172f76bafd62ef67f7fa56).
No contract, fixture, golden, accepted test or dependency changes.

## Placement and operations

Production consists only of qualification_output_records_v2.py (stdlib) and
qualification_output_v2.py (stdlib plus that records sibling). All old modules
are test-only oracles. New Python files enter proof_source_hashes_v2's existing
glob and invalidate old source-bound preparation/release authority. No old
preparation or physical qualification is inherited after source adoption.

The four public operations are validate_prediction_intent, create_prediction,
verify_prediction_commitment and compare_committed_output. The additional
compare_prediction_pair operation is for audio-changing B/C evidence only;
video-only A uses per-output consistency and separately owned native geometry
proof. The pure package cannot accept a decision, install native code, queue a
job, render, decode a MOV, synthesize, or grant future authority.

PredictionInputs carries only bounded immutable byte snapshots: a closed
verified-package input binding, authenticated raw geometry, every raw context
input, original source WAV bytes and SourceProof records. No paths or request-
selected module/verifier/route/gain configuration exists in the JSON interface.
The trusted controller must supply an OutputTrust implementation statically.
There is no permissive default, dynamic resolver, or production fake verifier.
The owned SealedTrust is strictly a test oracle, not evidence of actual
provenance/native/clock authenticity.

OutputTrust.authenticate must time-invariantly verify seal authenticity and
provenance of the exact expected complete payload using the actual
preflight/package/decision/source/capture/native records. Matching caller hashes
alone cannot authenticate it. Live native/input/target currentness is checked
when issuing the receipt and by #209 before reservation; authentication of
historical evidence must not require those inputs or targets to remain current.
Only #214 applies expiry, through OutputTrust.checked_now's accepted UTC clock.
Source proof
calls retain narration_preparation and private_preparation authentication;
new lane receipts use only output_geometry_snapshot,
output_prediction_commitment, output_render_reservation, output_decode_record,
and output_residual_comparison. They cannot issue legacy observation/render
receipts. Future revised integration remains default-deny until its separately
owned accepted-decision/revised-package verifier is implemented and qualified.

## Closed normalized inputs

The new qualification-output-inputs/v1 record is exactly schemaVersion, lane,
context, delivery, sourceEntries, tracks, itemMappings, nativeSources.
Each delivery row is exactly eventId, kind, recordRange, sourceRange; ranges
are the authenticated package's startFrame/durationFrames derivations.
Each item mapping is exactly itemUid,eventId,sourceId,mediaUid. Each native
source row is exactly sourceId,nativeSourceSha256. Geometry sourceMappings
contain sourceId,nativeSourceSha256,sourceEntrySha256 for the complete audio
source-entry inventory. Track/item/source-entry tuples are enumerated in
records constants and independently pinned in the owned record tests.

A geometry envelope binds schemaVersion,lane,geometry,inputBindingSha256,
capturePhase,capturedAt,expiresAt,receiptSha256. Its receipt authenticates all fields except
its own receipt reference. geometrySha256 hashes only the closed semantic
geometry object (including full context); capture times and receipt bytes are
outside that projection. Both raw snapshot hashes survive in the result.
The authenticator also receives the COMPLETE closed inputBinding, not just
its digest. pre_render is mandatory for input capture. post_render is mandatory
for the distinct post raw bytes and also authenticates renderLineage, allowing
the product adapter to verify capture-after-completion. The marker/receipt stay
outside semantic geometry. Geometry equality never claims continuous stability.

All context raw hashes must have independently supplied current bytes in
PredictionInputs.blobs, including BOTH original and execution document AND
dependency snapshots, package/preflight/manifest/report/preparation, both source
graphs, installed release, runtime and profile. These are raw64 digests.
There is no separate invented package-binding receipt. The geometry receipt's
expected inputBinding plus full context binds these independently verified
inputs. At receipt issuance, #209 must verify them against the actual accepted
package, preflight and current input identities. Historical authentication
verifies that exact captured payload's provenance without renewing authority.

The stable binding excludes invocationId, preflightSha256, preparationSha256
and its own bindingSha256, with no caller-selected exclusions. Names remain in
the binding and in authenticated exact-target checks. History chains use
immutable projectUid+timelineUid+caseId+phase. Plan-owner clarification supplied
with the implementation-review continuation: a rename is a disclosed new
binding within that SAME UID chain. This grants no native rename operation.

### Exact blob domains and coverage of excluded references

All blobs are independent immutable bounded snapshots (<=8MiB each), never
paths to reopen. packageSha256 hashes the exact accepted package delivery-view.json
bytes (resolve-native-view/v2), after the trusted adapter independently verifies
the COMPLETE original package and inventory. The pure checker compares this
view with the manifest/dependencies, derives visual/placeholder ranges, matches
track id/kind/index/name, native source hashes, complete event inventory and
v2Event copies; audio q/r and narration ranges are independently derived too.

runtimeSha256 hashes qualification-output-runtime/v1, exactly schemaVersion,lane,
implementation,pythonVersion,nodeVersion,npmVersion,uvVersion,system,release,
machine. Locked versions are checked; the trusted adapter verifies the actual
current host. installedReleaseSha256 hashes qualification-output-release/v1,
exactly schemaVersion,lane,files: a bounded safe-relative-path/raw64 map of
independently qualified installed FILE CONTENT, with no issue times or authority
nonce. This is a new content projection, not a legacy receipt upgrade.
profileSha256 hashes qualification-output-profile/v1, exactly schemaVersion,lane,
container,videoCodec,audioCodec,audioBitDepth,sampleRate,channels,rate,width,height.
The codec/audio/rate choices are fixed in code, dimensions match the manifest.
No request-selected policy is admitted. #209 owns generating/authenticating
these normalized host projections from actual qualified retained source data.

Native track names must equal manifest names, as well as matching id/kind/index.
The owned fresh-compiler oracle checks manifest/dependency track equality and
name/index presence. It does not prove #177's native naming behavior. #209 must
verify that naming/capture assumption before admitting actual captures.

Incoming #209 feasibility checks also retain the inherited source-audio exact
grid and sidecar-profile restrictions: 44.1kHz endpoints at24000/1001 must map
exactly (the owned q=0 examples use80frame multiples); 48kHz mappings require
the accepted q offset to align with2002sample frames. Original signed24 WAV,
48kHz, exact channels/extent and canonical decoded int32 hashes remain required.
Audit actual R16 AV-event endpoints, q offsets, sidecar profiles and track names
before downstream readiness; this synthetic oracle does not show they pass.
The real-shaped owned sidecar is all-zero Python-wave synthetic PCM, proving
profile/extent/hash domains only. It does not qualify negative signed decoding,
channel interleave or FFmpeg WAVE_FORMAT_EXTENSIBLE. Real sidecars remain a209gate.
No padding, resampling, rounding or tolerance change is authorized by this note.

The two excluded raw references are NOT content-free authority envelopes.
The preflight contains content and a requestHash that changes with authority.
The preparation request likewise contains authority references. Excluding the
whole reference coarsens eligibility (cannot reopen an existing attempted key).
Their raw bytes/full context still authenticate, and admission/currentness is
mandatory; their prediction-relevant content is covered as follows:

| Referenced content | Stable identity / independent check |
| --- | --- |
| original and execution input hashes | four dedicated document/dependency hashes; both byte sets checked |
| manifest/report and compiler needs | manifestSha256/reportSha256 plus compiler/source graph and execution dependencies; full preflight validity remains adapter-checked |
| sidecar raw bytes | package delivery-view sources[].contentHash, also source-entry PCM/file hash checked against actual bounded WAV bytes |
| original AV/stream/probe/profile/mapping | complete preparedMedia binding in execution dependencies; exact receipt binding equality, manifest provenance/sourceTimeMapping and stream hash; full preparation authenticity remains adapter-checked |
| prepared q | fixed manifest a,b,r plus exact package-local sourceRange determine q; independently derive q/r from authenticated receipt, refuse any discrepancy |
| narration receipt row/tokens/review/boundary | exact execution-dependency row match; independent narration receipt and pin verification; authenticated manifest/compiler TS boundary hash, never Python-rehashed |
| runtime/source/release/profile | dedicated closed content snapshots and both source-graph hashes, independently current in adapter |
| revised lineage | all closed revised-binding hashes plus exact revised execution/manifest guards; future adapter remains default-deny until qualified |
| status/evidenceLevel/lane, unchecked/verification/admission | independently checked preflight/preparation validity in the full authenticated context, never accepted merely because the stable key matches |

No excluded field can select prediction intent. Renewed authorization, formatting
or snapshot time cannot erase an attempted key. Genuine changed input identity
still needs separate authority and disclosure of all prior attempts in the UID
chain. Original document/dependency, source and current-target guards remain.

## Hash domains and origins

Narration native sourceId is manifest provenance.sourceId; nativeSourceSha256,
pcmFileSha256 and narrationAudio.audioHash bind the whole original WAV file.
The authenticated narration row AND package WAV-first-sample delivery rule
supply origin (0,0). The event interval is exactly its record duration*2002,
bounded by actual durationSamples. Unaligned CEIL duration refuses; no padding,
resampling, shortening, rounding change or source mutation is supported.

For source_audio, accepted _delivery_view uses the eventId as native sourceId
and the prepared PCM sidecar as native media. Its nativeSourceSha256 equals
pcmFileSha256, distinct from provenance.deliveredSourceHash (the delivered AV
raw file) and manifest audio.audioHash (original selected-stream packed-s24
hash). private_preparation binds all original/delivered/probe/stream/mapping
links. Manifest sampleRange retains the existing startFrame/endFrame key names
although its counters are samples. Local endpoints are exactly a*48000/r-q
and b*48000/r-q, with q=audio.resampledFirstSample. Both must be exact integers
on the 2002-sample frame grid; no approximate conversion is accepted.

The only supported origin is the package-derived (0,0). Supplied origin records
refuse for every source kind, including geometry-kind seals over origin data.
No new mapping-authentication authority is invented. Nonzero original AV/sample
positions remain supported through the exact q/r derivation and package oracle.
A future generic native/PCM origin needs a separately owned approved authority
and cannot replace the accepted package source-range derivation.
pcmMappingSha256 hashes sourceId,nativeFrameOrigin,pcmSampleOrigin,
sourceSampleRate,sampleRate,resampledFirstSample,startSample,endSample,
provenanceRecordSha256. Both origins are explicitly checked as derived zero.

Canonical decoded samples hash little-endian int32 interleaved signed24-domain
samples (PCM16 promotes by exactly256). This hash is neither the WAV file hash
nor the original selected-stream packed-s24 hash. Prediction bytes are finite
little-endian float64 interleaved stereo, normalized by2**23, fixed ordered +=
mixing and exact manifest 0/-18dB intent. No alignment, source, gain, pan or
residual fitting occurs. Python JSON bytes and codepoint order are normative;
TS215 must verify these exact bytes, not localeCompare/its old canonicalJson.

## Lifecycle and result handoff

create_prediction returns an unsigned payload and deterministic PCM. #209 must
obtain the independent output_prediction_commitment receipt, add its raw hash
as commitmentReceiptSha256, persist immutable bytes, and verify/recompute those
bytes before a reservation or native effect. The receipt-payload projection
excludes exactly its own receipt reference, avoiding cyclic hashes.

The ledger is per immutable projectUid/timelineUid/caseId/phase and spans bindings. Each entry carries full
context, sequence, priorHeadSha256, state, commitment raw/payload hashes,
prediction hash, reservation raw hash, result raw hash and entrySha256. The
exclusive key is stable binding/target/case/phase. Only expired_unused permits
an identical-prediction recommit. Reserved, uncertain, consistent and refused
keys cannot restart under another invocation or authority reference.

The record helpers validate pure complete-chain transitions and a
prior-terminal-head compare-and-swap projection. #209 owns authenticated complete
persistent history, exclusive-create, locking, fsync, truthful partial effects,
read-only recovery and actual effect order. Passing an empty/truncated history
from an untrusted request is never controller integration. Partial attempts
and errors must be retained, not silently replaced or retried.

CommittedOutput includes raw commitment/reservation plus receipts, prediction,
post-geometry and receipt, decoded signed24 stereo int32 bytes and decode
receipt, closed render lineage and the complete current ledger. Decode
authentication must independently bind the exact delivered MOV/ProRes422/lpcm
24-bit48k stereo, decoder/tool/source/command, actual native job/output and
intent/effect/start/completion lineage. A separately rendered WAV cannot qualify
the MOV's audio. Actual decoding/profile/offset evidence remains External209/178.

Comparison returns an unsigned terminal payload with all input/native/decode
hashes, zero-lag unity metrics, signal/non-vacuity metrics and
priorLedgerHeadSha256. Seal with output_residual_comparison, add
comparisonReceiptSha256, then append the raw result hash only if the actual
current head still equals that prior head. Never put the post-terminal ledger
hash inside the result. The private test helper reauthenticates/recomputes and refuses stale/interleaved
appends; real atomic persistence remains #209's job. #209 consumes the public
operations and closed records; private transition helpers are pure specification
models, not an additional installed/native controller API.

Every result keeps internalControls=unverified, geometryStability=not_claimed,
controlStability=not_claimed, futureAuthority=false. Hidden compensating or
subthreshold processing can pass. Pair discrimination is not omission evidence,
listening, token support, edit inference, accepted revision or rebuilt proof;
those are #215's separate responsibilities.

## Implementation review corrections and completion semantics

The private_preparation source kind uses an explicit NEW-LANE expected payload:
context,preparationBindingHash,recordSha256,binding. It is not the old #190
originalInputs/binding/sourcePins payload. Statically wire this lane in the
trusted adapter; tests require each shape's seal to refuse the other. Receipt
rows/bindings are first matched exactly to executionDependencies narration lists
or preparedMedia, including requirementKey and boundary-list membership.

Identity limits apply to consumed identity fields, not arbitrary foreign text.
Foreign accepted JSON retains duplicate/nonfinite/unsafe-int/depth/size checks.
Raw records require strict UTF8 without BOM/UTF16/UTF32. Malformed shapes/enums
become OutputConsistencyError. Current frozen R16 dependency and manifest JSON
were audited read-only; their old identity-string limits happened to pass too.
Six artifactLocator values name media, not #174 receipts; no receipt JSON was
inferred from those media paths. Audit does not qualify PCM/native/currentness.

create_prediction rejects either vacuous expected channel before any commitment
or reservation. The same gate remains at comparison. Expiry gates verification
for a NEW reservation/effect; a validly reserved effect may compare and terminal-
append after pre/commitment expiry. Checked order is pre capture <= creation <=
reservation <= commitment expiry, with actual now and post-completion capture
checked independently. Recomputing a completed effect never renews render authority.

compare_prediction_pair now takes two TerminalOutput values: CommittedOutput,
sealed comparison bytes+receipt, and complete CURRENT ledger including the
terminal entry. It authenticates the terminal and chain, projects the committed
prior-terminal-head internally only for independent recomputation, and retains
both full current chain heads in the pair result. Supplying only a pre-terminal
prefix refuses. All four unverified/not-claimed/no-authority labels remain.
