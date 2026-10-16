# CN-211-Q2 r1 — evidence-bound qualification build and picture route

Status: **PROPOSED; Producer acceptance pending.** Design only, issue #211.
Owner chat `01a13c5b-9099-73f3-8642-7e1efc9c2cd6`, Sol/high; branch
`codex/issue-211-qualification-route-design`. Accepted source baseline:
`f0cd85cb8d0e7dbd8950aa3094fef19044bac11f`, tree
`0cde2fce2837c0b42b02f636c76144115cb0fa07` (#208 / PR #210).

## Decision and exact unresolved boundary

Recommend one finite experimental build plus a MOV/ProRes422/linear-PCM picture
proof route through the common public adapter and audited native boundary.
Keep complete-control refusal. No compliant complete-control reader is
established by the actual report; **#209 must remain Inbox until that narrow
evidence boundary is resolved and this note is accepted**. This note specifies
an operator-evidence consumer candidate, not an assertion that its evidence
can currently be collected. Accepting the envelope with this blocker recorded
is a valid #211 design decision; it does not make #209 Ready.

The bounded next action is a separately authorized, read-only feasibility
assessment of complete control evidence on an already saved, disposable,
populated synthetic target. Produce one field-to-visible-source map covering
every row of the control matrix and a demonstrable independent capture and
freshness mechanism. Use only the product's audited operator flow. No setter,
installation, new target, queue, render, agent UI/MCP/console fallback or
operator confirmation by the agent. A screenshot, saved-project assertion or
fresh-default inference alone cannot establish completeness. If a field has
no complete supported source, retain that field as unavailable and stop.
Any proposal to weaken completeness needs a new exact Producer decision;
this note grants no such weakening. This action belongs to #209's existing
unresolved reader decision; if it needs independent implementation, the
steward creates a bounded Inbox prerequisite before Ready.

This extends the proposal sections of CN-178-Q1, raw SHA256
`c8ec4e9abf427a5e99ba8951abcc463745938aa1f35a3c4613f7b037a80e2740`.
Its staged approval covered read-only preflight only. Accepted CN-207-ID1
SHA256 `e02da9eacd54fb90b7ca4ba63f1c3f72f37b997e426828ad8237d0bd1adc6006`
and #208 identity/one-use receipt semantics remain the identity foundation.
Do not change those accepted schemas to issue build authority.

## Evidence retained and interpretation

The [complete factual matrix](../verification/issue-211/capability-matrix.md)
retains all 71 entries: 5 supported, 23 ambiguous, 43 unsupported. Capability
result raw SHA256:
`2d1141bda6942baa0f83da2cb49f0f104801ce2ea853bccee5aab37d24dc4943`.
Identity result raw SHA256:
`92be8c49f5efbee2b53c11efcd749e8ae43aa9061c33b1bc471b4851baeebc9d`.
Private locators are retained privately; no target names/UIDs appear here.
Actual runtime: Studio 21.1.1 build 10, injected CPython 3.14.7. The report
contains 677 context-verified observations (674 supported, 3 ambiguous).
Four target identifiers each agree across 32 guarded capability reads.

The target contained one video and one audio track, no items and an empty
render queue. Clip and job facts were unexercised, not successful tests.
Track enabled was observed; bus/master/programme and most mixer controls have
no complete reader. Aggregate codec/resolution gaps are ambiguous because
some formats have empty codec maps. The supported current-format getter
returned `format=unknown`, empty codec: no usable preset. Output cadence,
PCM, quality and effective mix were not measured. Saved/nonproduction/None
statements are procedural operator attestations, not independent state proof.
Historical consumed/expired authority authorizes no future effect.

#204's private independent assessment is completed raw evidence. Its owner
has now retained closeout documents on the tree-equivalent integration
`0df343d30ed7e8c1dbe8f74c7a0e711fbe66b33a`; the complete 71-row gap table
and remaining-route handoff agree with this proposal. At handoff inspection,
#204 is still Open / In review. Reconcile its final accepted handoff and
Closed/Done state before #209 Ready;
no reverse dependency on #211. #208's accepted native assessment and
[acceptance handoff](../verification/issue-208/acceptance.md) remain intact.
Its local full pass is historical evidence, not a #211 rerun: tested
`3261abc410483757eff7a946a0a562660e4505ad`, 1,145 Python / 465 Vitest /
61 Node, zero skips. Remote CI's 1,143 Python plus two macOS alias skips
was correctly rejected for cloud substitution. No new runtime is qualified.

## Finite build semantics

Expose `run_workflow_qualification_v2` as a distinct public operation in
`workflow_v2.py`, using the same single `PublicResolveAdapter` and common
checked orchestration as `run_workflow_delivery_v2`. Requests cannot select
an adapter/callback/module/script. Qualification context is verified before
adapter construction; ordinary callers retain all #177 guards.

Only issue #178 synthetic cases: reduced rate `{numerator:24000,
denominator:1001}`, native setting token exactly `23.976`, 1920×1080,
programme length 1–1498 integer frames (48 kHz count = frames × 2002,
within #190's 3,000,000-sample bound). This bound concerns #209's finite smoke;
#178's full matrix remains separate. Prepared picture must have exactly the
same rational source rate. No generalized float conversion, 30000/1001,
retiming, subtitle, unqualified slate/cover/treatment or provider acquisition.
Allow the already accepted contain treatment, root/child/return and
independent overlay placements. Refuse unsupported diagnostics and temporary
Presenter picture unchanged. Real R16 input cannot be relabeled synthetic.

Manifest ranges remain half-open integer-frame ranges: source `[s,s+n)`,
record `[r,r+n)`, nonnegative starts and positive lengths. Preserve manifest
ownership, track and event stamps. Convert to a native inclusive boundary
only at a documented and tested API seam; do not silently change the current
public adapter's append convention. Pin actual source start/end/duration,
record start/end/duration and native counter interpretation in readback.
Any unresolved endpoint convention refuses before effects. Source audio
uses the manifest's safe timeline-frame projection and identical picture
coverage, without widening range or rate conversion. No = no audio event;
Quiet = -18 dB; Full = 0 dB. Check actual item gain, enable and channel map;
`AudioVolume` setter success alone is insufficient.

Authenticate original document **AND dependencies** raw bytes, execution
preparation/media/package/attestation identities, installed/repository source
inventory and runtime before every stage. Preserve #192's separately versioned
revised-input lineage and `from_revised_proof` guard. #209 smoke uses genuinely
new synthetic input; neither original nor revised private lanes lose guards.

Reserve one exact new nonproduction project/timeline intent, with operator
approved names containing a unique case nonce; refuse name collision, existing
UID substitution and concurrent consumption. Record prior target identity
read-only. Creation acquires real UIDs from returned native state and pins
them in effect lineage. Every subsequent operation rechecks those UIDs/names,
source pins and authority. No selection or mutation of an unrelated target.

Save/close/reopen uses the existing guarded adapter operation only on the owned
target. Require the same actual target UIDs, timeline settings, item/source/
track inventory, ranges and stamps after reopening. Capture complete controls
freshly after build, after reopen, and adjacent to render; an earlier control
receipt cannot bridge reopen. Failure leaves partial target and evidence.
Construction may yield an experimental partial target; it cannot yield a
complete proof or render authority while controls are unavailable.

## Proposed complete-control trust consumer

New closed record `issue-211-operator-control-evidence/v1` supplements native
raw reads; it never fabricates native getter results. Required top-level fields:
`schemaVersion, invocationId, challengeNonce, requestSha256, authoritySha256,
releaseSha256, sourceInventorySha256, runtime, target, phase, capturedAt,
expiresAt, observationSha256, topologySha256, inventory, programme,
evidenceAssets, issuerReceiptSha256`. Runtime is exact product/version/build/
Python identity; target has the four real identifiers. Phase enum:
`post_build`, `post_reopen`, `pre_render`, `post_render`. `inventory` is a
complete sorted census of clips, tracks, buses and masters with stable IDs,
edges and explicit values for every required field; programme contains all
five fields. Each value has `{value, sourceKind, sourceRef, assetSha256}`.
Source kind is `native_getter` or `operator_observation`; missing/unknown
values are failures, never null-as-neutral. Evidence assets bind immutable raw
bytes, MIME/type, capture interval, visible target/census correspondence and
field coverage. No arbitrary executable locator is permitted.

Operator observations require personally supplied decisions through an audited
flow and an independently authenticated issuer receipt binding nonce, target,
phase, observation/topology/assets hashes and declared completeness. Reuse the
existing independently verified authority provenance model; a JSON hash,
request preparer, agent statement or unchecked signature is not the issuer.
The installed integration chooses the verifier and source reader statically.
The consumer verifies raw bytes, provenance and exact target against adjacent
native reads and refuses disagreement. A small picture/audio sample cannot
prove that unobserved EQ, sends, effects, automation or limiter are absent.

Freshness is a proposed stricter bound: consume once in the same installed
invocation within 120 seconds of completed capture, with issuer expiry no later
than capture +120 seconds and within the containing authority window. Reject
future dates, clock rollback, elapsed timeout, nonce replay, changed source,
target/settings/items/topology, save/reopen, interrupted capture or process
restart. Use wall and monotonic clocks; both must satisfy the bound. Require
two identical complete raw reads around acceptance and immediately before an
effect. During a render, poll native context and validate post-render controls
before claiming completion. Human evidence cannot observe intervening hidden
changes by itself: an exclusive audited session and independently demonstrated
change detection/capture coverage are prerequisites. If they cannot be proved,
this candidate remains unavailable. Do not assume a 120-second window solves
that problem.

One-use consumption reserves one phase evidence receipt, not each read of its
immutable bytes. Adjacent guards may read that same reserved receipt only in
the bound invocation/phase while it remains fresh; it cannot authorize another
phase or effect. If a render outlasts pre-render freshness, completion requires
a newly challenged post-render receipt and independently proven continuous
change detection during the interval. A stale pre-render receipt cannot certify
the intervening mix. No completion is claimed without that evidence.

The accepted #190 `programControls/routes` shape is unchanged. The consumer
first verifies the richer census: every clip/track/bus/master field, master
limiter and programme fields from the matrix. Only then derive effective route
values. Clips have gain -18/0 per policy, neutral pan, enabled true, mute/solo
false, empty effects/sends/automation with positive completeness evidence and
exact mono-dual/stereo-direct mapping. All intervening track/bus/master gain
is 0, with the same neutral/complete controls and explicit destination edges;
programme is the accepted 0 dB/empty effects/false limiter/empty automation/
stereo-program object. Destination edges must connect every audible item to
the programme; no unlisted branch or bus. Rich evidence is retained alongside
the derived hash. Unsupported or non-neutral controls refuse; no lossy
projection may hide a control. **No such consumer or reliable capture source
is installed or accepted today.**

## Concrete render candidate and ownership

Select `mov` / `ProRes422` at 1920×1080, 24000/1001, with stereo 48 kHz,
24-bit linear PCM (`AudioFormat=mov`, `AudioCodec=lpcm`). Actual guarded
rows enumerate this codec, 1920×1080 and MOV linear PCM; they prove candidate
selection only. Separate acoustic proof keeps #190's WAV operation:
`AudioFormat=wav`, `AudioCodec=lpcm`, stereo 48 kHz / 24-bit. Its earlier
failed WAV/lpcm setter remains historical; no successful current setter is
inferred. MOV proof is distinct from the product spec's future H.264/AAC MP4
review delivery; no watermark/upload or #71 implementation here.

Proposed picture `SetRenderSettings` values: `SelectAllFrames=false`,
`MarkIn=T`, `MarkOut=T+N-1`, `TargetDir=<reserved private output dir>`,
`CustomName=<case nonce>`, `UseUniqueFilenames=false`, `ExportVideo=true`,
`ExportAudio=true`, `FormatWidth=1920`, `FormatHeight=1080`,
`FrameRate=23.976`, `AudioFormat=mov`, `AudioCodec=lpcm`, `AudioBitDepth=24`,
`AudioSampleRate=48000`, `ReplaceExistingFilesInPlace=false`.
The rational expected rate is retained separately; that numeric native token
is not rate truth. No fallback keys or presets. These key/value representations
are proposed and must be proven by setters AND actual readback/job/output.
`SetCurrentRenderFormatAndCodec(mov,ProRes422)` and exact current format/codec
readback are required. Missing settings refuse before starting a job.

Under the existing native lock, reserve output exclusively before setters;
no symlink, alias escape, overwrite, shared output, deletion or path under
source/package/research roots. Independently inventory prior queue. Add exactly
one job; returned real job ID must be new and uniquely bound to the owned
target and exact output. Required job readback: `JobId, TimelineName, TargetDir,
OutputFilename, IsExportVideo, IsExportAudio, MarkIn, MarkOut, FrameRate,
FormatWidth, FormatHeight, AudioCodec, AudioBitDepth, AudioSampleRate,
RenderMode, ReplaceExistingFilesInPlace`, plus current format/codec and target
UID binding in the retained context. Queue requires `RenderMode="Single clip"`
and exact typed values. Queue identity by name alone cannot replace UIDs.
No field is considered observed because it appeared in the setter request.

Retain immutable intent → queue effect → start-intent → start-returned →
completion. Start only the single owned job ID once. Status enum is
Ready/Rendering/Complete, integer percentage 0–100; Complete requires 100.
Read-only bounded polling of that job revalidates source/target/job/settings.
Independently hash and decode the final reserved regular-file bytes: exactly
one ProRes422 picture stream, 1920×1080, progressive rational 24000/1001,
N decoded frames with monotonic cadence; one stereo PCM stream, 48 kHz,
24-bit, N×2002 samples, zero start offset and matching programme extent.
Check endpoints and synthetic AV sync against authenticated source coverage.
Unknown padding, rate, channel layout, colour/picture interpretation or
undecodable bytes leaves an incomplete proof. A supplier completion flag
does not complete the experiment. Colour/quality judgment remains #178.

On a crash or ambiguous setter/create/queue/start/save return, preserve intent,
partial target, queue and all bytes. Resume permits read-only investigation
and polling only where exact effect/job lineage exists. Missing effect receipt
does not authorize reconstruction or retry. Completion grants no new effect.
Never clear queue, stop unrelated job, delete output or retry uncertain creation.
New attempt requires separately issued authority, fresh target/output nonce
and a human recovery decision; retained uncertain effects remain visible.

## Closed request/result versions and scalar rules

Use distinct `vera-native-build-qualification-request/v1` and
`vera-native-build-qualification-authority/v1`; do not broaden the installed
`vera-native-qualification-request/v1|v2` read-only action. Request fields:
`schemaVersion, issueNumber, qualificationIssueNumber, action, invocationId,
caseId, releaseSha256, repositorySourcePins, installedInventorySha256,
attestationPath, attestationSha256, proofPackagePath, proofPackageSha256,
originalInputPins, executionInputPins, authorityPath, authoritySha256,
targetIntent, capabilities, renderProfile, externalScripting, evidenceDir,
outputRoot`. Issue=209, qualificationIssue=178, action=`qualify_build`.
Capabilities exactly fractional_24000_1001/source_audio_policy/picture_pcm_proof.
Target intent has exact new names/nonce and no preassigned UIDs. Render profile
is the fixed candidate above, not user-supplied arbitrary settings.

Authority fields: `schemaVersion, authorityId, issuer, decisionReceiptSha256,
requestContextSha256, approvedChangeNoteSha256, invocationId, caseId,
issuedAt, expiresAt, sourceInventorySha256, releaseSha256, inputPins,
targetIntent, approvedReadRoots, approvedWriteRoots, operations,
externalScriptingConfirmation`. Verify provenance independently and consume
once before import/effects. Operations are a closed ordered list: create owned
project/configure/bin/import/timeline/tracks/place/stamp/save-close-reopen,
capture controls, picture settings/add/start/poll/read-output, optional separately
authorized PCM job. No arbitrary setter, script or permission wildcard.
Fresh new build authority is separate from #208 identity/preflight receipts.

Avoid circular request/authority hashes: `requestContextSha256` is raw SHA256
of a separately retained canonical UTF-8 request-context object containing all
request fields except `authorityPath` and `authoritySha256`. Reject any other
projection or missing context field. Authority authenticates that context;
the final immutable request then binds the actual authority bytes/hash. Both
the issuer and installed consumer independently verify the projection, complete
context and final request. Context alone grants no effect.

Result `vera-native-build-qualification-result/v1` fields:
`schemaVersion, invocationId, requestSha256, authoritySha256,
approvedChangeNoteSha256, releaseSha256, sourceInventorySha256, inputPins,
runtime, targetIntent, actualTarget, stage, status, qualified,
futureEffectsAuthorized, partialTargetRetained, effectReferences,
observationReferences, controlEvidenceReferences, outputReferences,
discrepancies, startedAt, finishedAt`. qualified/futureEffectsAuthorized are
always false; status enum stopped_safely/partial/uncertain/experiment_complete.
Uncreated actualTarget is null, not invented identifiers. Each reference binds
raw SHA256 and a private path within its approved root.

Picture records `issue-211-picture-render-{intent,effect,start,complete}/v1`
bind invocation/request/authority/release/source/input/target identities and
prior stage raw hashes. Intent adds observation/control/mapping hashes, exact
parameters, prior queue and output reservation; effect adds actual job ID and
queue/context facts; start adds start-intent hash and observed return (uncertain
is retained separately); complete adds exact poll/adjacent observation/control
hashes and independent probe/decode/output hash/sample/frame receipt. The
existing #190 WAV record versions/consumer remain unchanged.

Every record is closed: reject unknown keys/version, duplicate JSON keys,
nonfinite numbers, bool-as-int, malformed or uppercase raw SHA256, duplicate
identities/references/capabilities, unsorted inventory and arbitrary flags.
Integers are safe nonnegative counters ≤2^53−1 with the tighter frame/sample
bounds above. Rates are reduced positive integer rationals. Required identity
strings are nonempty, bounded to 512 Unicode characters with no NUL/control
characters; nonce/invocation IDs are lowercase 32-hex. UTC timestamps have
explicit Z offsets and strict ordering. Paths are absolute, regular-file or
reserved-output intents, contained in approved roots after alias/symlink checks;
evidence and output must be disjoint from immutable input roots. Never confuse
raw file SHA256 with canonical compiler identity. Required schema validation
is implementation acceptance work, not merely this field list.

## Minimum owning files and change impact

| Proposed #209 file ownership | Bounded responsibility |
| --- | --- |
| `python/vera_timeline_agent/workflow_v2.py` | Distinct public qualifier and shared checked orchestration; exact native rational map; ordinary refusal unchanged; single adapter. |
| `python/vera_timeline_agent/workflow_v2_cli.py` | Prepare exact versioned request/inventory from independently authenticated inputs; no authority issuance or installation. |
| `python/vera_timeline_agent/workflow_v2_launcher.py` | Dispatch distinct version after integrity checks; immutable experimental result. |
| `integrations/resolve/VERA Delivery v2.py` | Declared inventory/bootstrap only; no new discovery or connection. |
| `python/vera_timeline_agent/native_qualification_v2.py` | Consume build authority and public qualifier; preserve accepted read-only actions and #208 identity. |
| New `python/vera_timeline_agent/qualification_controls_v2.py` | Statically injected evidence/provenance verifier and rich-to-complete-control consumer, only after source feasibility is established. |
| `python/vera_timeline_agent/roundtrip_v2_native.py` | Public qualification wiring and finite picture job; unchanged PCM/initial/revised guards. |
| `python/vera_timeline_agent/roundtrip_v2_records.py` | Explicit consumed source graph/binding for new sibling records; no omitted code pins. |
| New `tests/test_issue209_qualification.py`, `tests/test_issue209_controls.py`, `tests/test_issue209_picture.py` | Slice-owned synthetic/refusal/recovery tests; existing acceptance tests unchanged. |

Reuse release schema `vera-injected-delivery-release/v2`, with a new complete
inventory/digest including all consumed code. Existing requests, installed
releases, source bindings and authorities cannot be upgraded in place; new
source needs new preparation/attestation/release/request/authority pins and
a fresh interpreter installed through #109. Old consumers refuse new versions.

Why change: accepted delivery/preflight cannot currently construct fractional
source-audio experiments or produce a bound picture proof. Breakage is confined
to new experiment consumers and stale source-bound evidence; ordinary APIs
retain behavior. `/contracts`, generated TS/Python types, frozen fixtures/
goldens/accepted tests, v1 records and compiler: **no changes proposed**. No
generator run or new library dependency; existing stdlib, locked host tools
and public adapters suffice. If implementation cannot honor this inventory or
requires shared frozen changes, stop for an exact amendment before editing.

## Exact #209 scope/dependency and acceptance proposal

Keep canonical dependencies #211, #204, #208, #156, #174, #177, #190. Their
justification is accepted design, actual preflight/identity, authoring lineage,
prepared same-rate media and public package/proof seams respectively. No
reverse #204 dependency. After acceptance, replace #209's unresolved-decision
paragraph with: “Implement CN-211-Q2 r1 at its exact accepted SHA256, only
after complete-control evidence feasibility is resolved by a retained field/
source/freshness assessment and accepted #204 closeout is consumed. Unknown
controls or candidate job/output fields refuse. No global qualification.”
Keep its External acceptance and separate approved design requirement. Its
source baseline must contain the exact accepted #204 integration, not this
initial design baseline alone. Do not dispatch/promote from this document.

Before #209 Ready, retain (1) explicit Producer response/hash, (2) Closed/Done
#204 final accepted handoff/hash compared with this matrix, (3) complete
feasibility evidence for the consumer or accepted supported reader and any
bounded prerequisite Closed/Done, (4) exact owner/file/routing assignment,
(5) canonical resolved dependencies. This design acceptance grants no
installation, new authority, native effects, heavy job or synthetic smoke.

Test-first focused negatives: wrong/missing/self-issued/expired/replayed
authority; bootstrap source/inventory/load drift; original AND dependency
changes; revised lineage mismatch; ordinary fractional/source-audio/Presenter
refusal before adapter; rational/endpoint/gain/readback errors; target/name/UID
collision; incomplete census/effects/sends/automation/limiter; stale/forged/
duplicate control assets; hidden topology delta; save/reopen UID/range drift;
wrong queue/settings/codec/output; overwrite/symlink; uncertain create/queue/
start; interrupted render, duplicate invocation and read-only recovery.
Mutation traps count attempts before raising; assert zero forbidden attempts.

After implementation grant: focused checks → complete fast gate → required
independent adversarial review of identity/authority/path/source/rational/
controls/render/recovery seams (including Claude where required) → bounded
fixes/delta checks/review. Separately authorized synthetic Studio smoke then
runtime fixes and delta review → final complete qualifying validation on the
delivered state. Use VERIFICATION_POLICY and the heavy queue; affected slow
media checks serially, next costly pytest `--durations=25`. Locked toolchain
and all consumed input/output/environment hashes retained. Cloud does not
certify Resolve; reuse only proven equivalent complete coverage. No checks
or external/human gates are waived by this plan.

Synthetic smoke checklist after separate operator grant: personally install
exact reviewed release through #109; confirm None and approved disposable
names/roots; invoke the exact one-use build request once; verify real owned
UIDs/rational/ranges/source-audio and complete independently sourced controls;
save/reopen and compare fresh inventory/control evidence; reserve one MOV job
and inspect every required current/queue field before one start; inspect
independently decoded frame/sample/endpoints/sync and immutable result hashes;
reinvoke only the read-only recovery route and verify no new effects. Preserve
prior targets, packages, jobs and outputs. An uncertain effect stops the
checklist for human recovery. Failure remains failure. This proves only the
finite mechanism, not #178's full 23.976, No/Quiet/Full, topology, sync, judder,
listening, picture-quality and recovery matrix or #145's creative acceptance.

## Producer decision checklist

1. Open this note and the linked matrix. Expected: truthful 5/23/43 gap counts,
   no claim that enumeration/defaults prove a complete reader or render.
2. Read “Decision”, “Proposed complete-control trust consumer” and “Concrete
   render candidate”. Decide whether to accept this strict experimental
   envelope with the explicit unresolved evidence blocker. The new trust
   consumer's feasibility is still a required decision boundary before Ready.
3. Confirm the owning file table, ordinary/frozen guards, exact #209 Ready gates
   and separate operator smoke/qualification gates. Expected: no native or
   implementation authorization follows design acceptance alone.
4. Use the exact raw hash in the issue-owned evidence receipt. Record
   `Approve CN-211-Q2 r1 SHA256 <full hash>, with complete-control feasibility
   blocker retained; #209 stays Inbox pending its stated Ready gates`, or
   `Revise CN-211-Q2 r1: <section and required change>`.

The roadmap remains In review until that explicit Producer response. This
checklist is required by the Producer acceptance policy in
`.agents/skills/vera-roadmap-coordination/SKILL.md`: “leave the issue In review
until explicit producer acceptance.” It is a design judgment, not repeat
testing or an installation/authority request.
