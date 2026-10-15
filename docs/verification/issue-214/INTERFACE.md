# Pure output-consistency interface for #209 and #215

Candidate implementation; independent implementation review and final local
acceptance are still required. Accepted authority and exact operative plan are
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

OutputTrust.authenticate must independently authenticate the expected complete
payload using the actual preflight/package/decision/source/capture/native
records and currentness guards, not simply accept matching caller hashes.
OutputTrust.checked_now supplies the accepted checked UTC clock. Source proof
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
capturedAt,expiresAt,receiptSha256. Its receipt authenticates all fields except
its own receipt reference. geometrySha256 hashes only the closed semantic
geometry object (including full context); capture times and receipt bytes are
outside that projection. Both raw snapshot hashes survive in the result.
Geometry equality at endpoints does not claim continuous stability.

All context raw hashes must have independently supplied current bytes in
PredictionInputs.blobs, including BOTH original and execution document AND
dependency snapshots, package/preflight/manifest/report/preparation, both source
graphs, installed release, runtime and profile. These are raw64 digests.
The package binding receipt authenticates their independently verified meaning.

The stable binding hashes full closed input identity except invocationId,
preflightSha256 and preparationSha256, and removes its own bindingSha256.
Those two explicit raw authority-envelope references remain in the full
context/authentication but do not reopen the key on authority renewal. Content,
policy, original/execution input, package/manifest/report, source, release,
runtime, profile, target, case, phase and revised lineage identity stay bound.
createdAt/expiresAt and authority-file references never enter the key. No
caller-selected exclusions are accepted. Review must assess this projection
against the actual downstream receipt shapes before integration.

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

The default prepared origin is (0,0). A generic nonzero prepared origin needs a
new independently authenticated qualification-output-origin/v1 record binding
context,sourceId,preparationReceiptSha256,nativeFrameOrigin,pcmSampleOrigin and
its receiptSha256. Narration never accepts an origin override. pcmMappingSha256
hashes sourceId,nativeFrameOrigin,pcmSampleOrigin,sourceSampleRate,sampleRate,
resampledFirstSample,startSample,endSample,provenanceRecordSha256. Origin and
range evidence is source-specific; no missing-field default is used.

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

The ledger is per target/case/phase and spans bindings. Each entry carries full
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
hash inside the result. The terminal helper reauthenticates/recomputes and
refuses stale/interleaved appends; real atomic persistence remains #209's job.

Every result keeps internalControls=unverified, geometryStability=not_claimed,
controlStability=not_claimed, futureAuthority=false. Hidden compensating or
subthreshold processing can pass. Pair discrimination is not omission evidence,
listening, token support, edit inference, accepted revision or rebuilt proof;
those are #215's separate responsibilities.
