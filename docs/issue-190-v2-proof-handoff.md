# #190 v2 proof handoff

This is the local preparation and explicitly injected evidence port from
[issue #190](https://github.com/mbelinkie/vera-script-to-timeline/issues/190).
Automated tests use local synthetic inputs and fake injected objects. They do
not qualify installed Studio, media decoding, acoustic evidence or live render.
The accepted meaning is #189 B1 and CN-189-A; #178/#145 retain real gates.

## Delivered interfaces

| Interface | Input and retained result |
| --- | --- |
| `PreparedProofBuildV2(proof_root, authenticate=..., read_probe=...)` | Private `proof-request-v2.json`, exact original/execution bytes, trusted receipt/probe ports. No native object. |
| `preflight()` | Deterministic strict v2 compile/needs, actual media/PCM checks and public #177 package verification; immutable `preflight.json`, manifest and report. `local_prepared` never grants execution. |
| `prepare_package()` | Public `build_v2_package`, `verify_v2_package`, `attest_package_v2` and `load_verified_package_v2`; immutable package attestation and `proof-package.json`. |
| `NativeProofBoundaryV2(resolve, *, attestation_path, attestation_hash, proof_package_path, proof_package_hash, evidence_root, authenticate, authority, code_hashes, read_controls=None, adapter_factory=None)` | An already injected object, exact local preflight/package/code/input correspondence, trusted authority and control reader. No discovery or installation. |
| `deliver()` / `recover_delivery()` | Public `run_workflow_delivery_v2` once, retained intent/result/partial target; read-only recovery consumes no native effect. |
| `capture(target, mapping, name)` | Two consistent complete reads, raw native record, derived audio record, hash/mapping receipt. |
| `render_complete_programme(*, target, mapping, observation_hash, output, render_format, render_codec)` | One owned local whole-programme stereo 24-bit/48k WAV job, or read-only poll; independent PCM extent/bytes/hash verification. |

These are Python library ports. There is no #190 connection-discovery CLI,
installed menu item, fallback `scriptapp` connection or background scheduler.
Caller variables in the examples below must come from the approved integration;
a JSON flag cannot select executable callbacks or authenticate itself.

## Local preparation

Use the checked delivered repository, Node **24.19.0**, npm **11.17.0**, uv
**0.12.5**, locked CPython **3.12.14** and the existing lockfiles. The host
preparation environment needs the existing verifier dependencies; the native
module imports only standard-library/accepted dependency-free runtime modules.
The proof runtime currently requires the checked repository source graph for
hashing, including Python, TS, imported JSON/SVG assets, schemas and locks.
An installed-only smaller bundle is not interchangeable with that graph.

`proof-request-v2.json` is a closed `issue-189-v2-prepared-build/v1` object:

- `lane`: `synthetic_local` or `r16_private`.
- `originalInputs`: exact raw document/dependency `sha256:` identities;
  `originalFiles`: independently readable `{path, sha256}` pins for those
  actual retained original files. `executionInputs`: separate document and
  dependency pins. Absolute regular independent files only; no links.
- `sourcePins`: the exact `proof_source_hashes_v2()` inventory.
- `media`: complete public #177 source/original/event key-to-file pins.
- `preparations`: each requirement maps to closed `receipt`, `original`,
  `delivered`, `audio` pins; `audio` is explicitly null when absent.
- `narrationReceipts`: every narration block maps to closed `timing`, `review`,
  `receipt` pins. Actual timing/review bytes and complete WAV PCM are checked.
- `authority`: an independently hash-bound local receipt file.

Every pin has exactly `path` and `sha256`. Raw hashes are not canonical
compiler document/manifest identity hashes. Records and outputs stay private:
they contain absolute locators, source mapping and authored content.

The R16 lane rechecks the accepted original document/dependency raw hashes
from the #189 plan and requires both execution input files to be byte-identical
to those originals. Execution receipts remain separately pinned. This initial
lane refuses document or dependency substitutions; a revised specimen needs
explicit Producer-approved ownership and a separately reviewed consumer.
Revised-document integration and decision ownership belong to #192;
this initial R16 preparation port does not infer an edit authorization.

Only `issue-148-private-verified-reuse/v1` and
`issue-148-private-png-still-cfr/v1` are consumed. Their actual original,
delivered, decoded probe, PCM, mapping, profile/tool/source and authorization
evidence must pass. Existing private originals/receipts are read-only; separately
identified execution records use #177's accepted preparation receipt shape.
This does not claim generic P5 generated or qualified those private profiles.

The integration supplies `authenticate(kind, receipt_bytes, context)`: it
returns normally only after independently checking the indicated local trusted
receipt and authority, or raises a refusal. Kinds are `proof_preparation`,
`private_preparation`, `narration_preparation`, `native_proof_binding`,
`native_delivery`, `native_item_mapping`, `native_observation`, `native_pcm_render`.
The verifier must bind the exact operation, original/execution distinction,
approved decision if applicable, current file/code pins and target/output.
The test no-op verifier is exclusively fake evidence and is not an installed
authority implementation. Hashes alone do not establish acoustic truth.

`read_probe(path, receipt_inputs)` must actually decode/probe that pinned file
with the independently accepted tools/profile and return the exact complete
probe record. Returning the receipt's stored probe is not actual verification.
An absent reader refuses. #190 does not run new conversions, pad original PCM
or repair a compiler/package discrepancy. #177's saved identity, settings,
diagnostic, full source and whole-frame audio coverage checks remain intact.

Inside the prepared host integration:

```python
from vera_timeline_agent.roundtrip_v2_build import PreparedProofBuildV2

build = PreparedProofBuildV2(
    proof_root, authenticate=trusted_receipt_verifier, read_probe=actual_probe_reader
)
local = build.preflight()
proof = build.prepare_package()
```

The request hash selects a distinct `execution/<request-hash>/` directory.
Inspect original/execution input hashes, verified files, compiler outputs,
package verification and explicit unchecked gates. Keep that whole directory
stable; do not add Finder metadata to its attested package. Exact unchanged
local preparation may reuse immutable identical outputs. Changed inputs need a
separate authorized request, not overwriting a prepared result.

## Existing installed connection and the missing proof installation gate

#177's actual release/request CLI remains supported for its own delivery:

```sh
rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_v2_cli release --output out/issue190/operator-v2-release
rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_v2_cli request <attestation-path> --release out/issue190/operator-v2-release --output out/issue190/operator-v2-preflight.json --evidence-dir out/issue190/operator-v2-evidence --action preflight --external-scripting-none
```

The operator installs the generated `VERA Delivery v2.py` and `vera-delivery-v2/`
entries in `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/`,
following [#109's exact quit/copy/preferences/restart flow](resolve-workflow-integration-v1.md),
using the v2 filenames/release/request. Resolve's Workspace > Workflow
Integrations > **VERA Delivery v2** injects `resolve`; External scripting remains
**None**. Installation/preferences/launch are later operator actions, not
#190 implementation side effects. The release hash and declared source
inventory are checked before imports. Never merge undeclared proof files into
that installed release or reuse an already-loaded runtime.

That existing release deliberately does **not** bundle or launch #190's new
proof controller. There is currently no qualified #190 installed bootstrap,
complete control reader or receipt/probe integration. #178 must retain exact
installed-source/checked-repository correspondence and qualify the explicitly
injected caller under the owning #109/#177 installation interfaces. Any shared
release/launcher amendment needs precise ownership and an approved change note.
No independently run console script, external scripting fallback or custom
second delivery adapter substitutes for that gate.

`deliver()` calls the public #177/#109 handoff, with explicit trusted
`native_delivery` authority. It preserves the public refusal **before adapter
construction** for fractional native creation, source audio, unsupported
picture treatments or subtitles. Thus R16 cannot currently be created through
this public path. A fake injected success is not a qualification flag and
cannot remove those refusals. #178 owns the required amendment/real evidence.

## Native capture and PCM interface for that later injected caller

Native candidate identities are Studio **21.1.0 build 14** and **21.1.1 build
10**, exact product/version/suffix; this list is a refusal filter, not external
acceptance. Target is exactly `{projectUid, timelineUid}`. Names must match the
attested unique nonproduction project/timeline. Code, preflight, original and
execution/media bytes are rechecked. Evidence must not contain or overwrite
an input/package/source file. Effect locking uses POSIX file locks.
Delivery recovery verifies binding/owner/intent/effect/completion ancestry and
the public result's attestation. Captures and render parameters retain either
the owned verified-delivery completion hash or an explicit externally supplied
target marker. An incomplete or failed delivery in this evidence root refuses
capture/render; it cannot be relabeled as an external target.

`mapping` has every observed native item UID exactly once, each mapped to
exact `eventId` and `sourceId` in the verified public view. An unknown, missing,
duplicate, disabled, offline, unqualified-speed or out-of-extent item refuses.
Links must be reciprocal. Raw records retain the authored v2 event and its
logical source mapping separately from #177's native timeline-rate frame
coordinates. Do not manufacture edit ancestry from copied marker stamps.
The trusted verifier authenticates the full actual observation separately.

The reader uses current project/timeline UIDs/names, timeline rate/settings/
extent, complete video/audio/subtitle track inventory, item/media IDs, source
file bytes, each track's enabled/locked state, integer and fractional record
getters, source endpoints, links,
enabled status, markers and documented `GetSpeed()` options. All four speed
options must be observable; only 100% with no stretch/ripple is supported.
Absent optional API fields are not defaulted to safe values.
Disabled tracks and unavailable/nonboolean track states refuse. Locked state
is retained without changing it. PCM profile checks parse the same bytes that
were hashed through a securely opened descriptor; a pathname is not reopened
for WAV parsing. Local source PCM reads are bounded to 64 MiB. Larger source
files require a separately reviewed consumer. Render reads are bounded by the
exact expected PCM payload plus at most 64 KiB of WAV header/metadata.

`read_controls(project, timeline, target)` must return exactly
`{programControls, routes}`. Programme fields are `gainDb`, `effects`, `limiter`,
`automation`, `destination`. Each audio route has `itemUid`, `sourceId` and
`controls` containing `enabled`, `mute`, `solo`, `gainDb`, `pan`, `effects`,
`sends`, `automation`, `destination`, `channelMap`. The reader must independently
account for clip/track/bus/master controls and routing; it cannot invent empty
effects/sends/automation or zero gain when the API cannot expose them.
Supported controls are zero programme gain, no limiter/effects/automation,
stereo programme destination; enabled/unmuted/unsoloed routes, gain 0 or -18 dB,
centred pan, no effects/sends/automation, mono-dual or stereo-direct mapping
matching actual source PCM. Unknown or incomplete controls refuse explicitly.

`capture()` writes `observations/<name>.json`, `.audio.json`, `.receipt.json`
exclusively. The receipt binds binding/raw/derived/mapping hashes, target and
adjacent consistency. Derived routes preserve multiple ordered, nonoverlapping
segments of one source only with identical complete controls and verified
WAV-local bounds. This is #191's audio observation input, not acoustic proof.

The renderer uses actual documented `SetCurrentRenderFormatAndCodec`,
`GetCurrentRenderFormatAndCodec`, `SetRenderSettings`, `AddRenderJob`,
`GetRenderJobList`, `GetRenderJobStatus`, `StartRendering([jobId], False)`.
The caller supplies exact independently qualified format/codec identifiers;
test `wav`/`LinearPCM` identifiers do not prove those installed capabilities.
Settings are whole-programme inclusive MarkIn/MarkOut, no video, audio 24-bit
48k, explicit target directory/custom name, unique filenames disabled and
replacement disabled. Output is a new `.wav` below owned `renders/`.

The actual queue must expose matching `JobId`, `TimelineName`, `TargetDir`,
`OutputFilename`, `IsExportVideo`, `IsExportAudio`, `MarkIn`, `MarkOut`,
`AudioBitDepth`, `AudioSampleRate`, `AudioCodec`, `RenderMode` and
`ReplaceExistingFilesInPlace`. These fields are optional in the API stub;
their absence is an explicit unavailable gate. Poll status must belong to
that actual queued ID. Complete requires 100%, independently read stereo
uncompressed 24-bit/48k WAV bytes and exact rational programme sample count,
plus unchanged adjacent source/control/target facts. R16 initially requires
2,216,214 samples; the proof cap is 3,000,000 samples.

## Effect recovery and later operator acceptance

Delivery records are exclusive intent/effect/completion. A partial or uncertain
creation consumes its intent and retains the named target. `recover_delivery()`
reads records only. Render ownership reserves the output path independently
of parameter hashes before configuration/queueing. Queue and start intents,
actual effect and returned-start records must agree; a changed codec cannot
retry an already reserved path. An uncertain call is not retried. A known
started pending job may only be polled through the same parameters/current
observation. No deletion, rollback, promotion of partial targets or job restart.

Later #178/#145 operators must retain exact installed release/repository/input/
receipt/tool hashes, Studio/interpreter identity, preferences, authorized unique
target, actual complete controls/mapping, adjacent readbacks, queue/poll/job/
settings/output records and independent WAV evidence. They must perform the
separately accepted codec/framing/audio/save-reopen and real edit/listening/
provider/visual checks. Those gates remain unavailable until real evidence and
their own acceptance authority exist. #190's Automated closing evidence must
never relabel local/fake records as that external result.
