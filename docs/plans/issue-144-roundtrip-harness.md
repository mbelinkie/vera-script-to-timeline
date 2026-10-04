# Issue 144 — bounded file-driven round-trip harness

**Corrected through checkpoint 2:** completed Claude reviews are retained under
`docs/investigations/issue-144`. Producer selected the tested linked cases with
an isolated proof setup step. The compiler-only entry is the first implemented
segment; all affected semantic/native seams below remain planned. No new native
action has occurred. #145 must verify actual setup and edits on one selected build.

The prepared-build core segment is now implemented and pending checkpoint 4
review: actual compiler/package/job stages with 18 new passing tests, strict
input gate and explicit native wait. Semantic/native seams remain planned.

Checkpoint 4 completed: integer/refusal correction and current-folder recovery
boundary retained. Prepared checks now total 20. The next implemented segment
injects the actual accepted Studio assembly with exclusive pre-effect intent,
immutable result/UID receipts and fresh inspection on replay; checkpoint 5
reviews it. No real observer, linking, render, semantic revision or baseline
promotion is implied. The operator CLI still stops before native actions.

## Authority, ownership and starting evidence

Issue [#144](https://github.com/mbelinkie/vera-script-to-timeline/issues/144),
Project 2, Automated acceptance. Claimed by task
`01a103aa-e47a-79e0-88b5-62e6d9637d1b`, `gpt-6.1-sol/xhigh`, on
`codex/issue-144-roundtrip-harness`. Clean starting HEAD is
`9c8973de6b02eb89cb57a03c0bd50480af73f9e1` (PR152). The October 3 readiness
comment and issue closure evidence supersede #141's historical pending text.

- Accepted #34 source `2586dde`, integrated `7065715`: `studio_assembly.py`
  is byte-identical, SHA256
  `57ba08ce20390f9f0222e592e9b1e2c77648b12b3049f3da512b5a150570b624`.
  Retain the Studio-only acceptance exception; no Free parity claim.
- Accepted #35 source `4354c63`, integrated `e3bb5fd`: `build_jobs.py`
  is byte-identical, SHA256
  `fa7814047965266e362d0662ce3358a0db52e58fd761ede70318155fe8b01490`.
  Its durable stages intentionally have no compiler/package/Studio adapters.
- #141 PR151 publication `03ef585` is an ancestor of this HEAD. Publication
  verification passed: 5,670 records, 5,530 sanitized text records, zero native
  actions. Read report, final findings, PUBLICATION, publication manifest and
  accepted #149 design inputs. Preserve historical versus sanitized hashes.
- Read #131 representation evidence at `817d0e5ab76219fdc3df95b196f84fbad0382f0a`
  and accepted handoff `ac0f5d9ecca9439160885e08f2a51c87a4092756` separately.
  They are not merged implementation or approval for a new contract.

## Scope and exclusions

One local proof directory, literal JSON inputs/outputs, pinned host build process
and separate file-staged WI observation/link/render entry. Reuse the existing
compiler, package writer/verifier, Studio assembly and durable job store.
Implement deterministic proposals, explicit local decisions, new canonical
revision and verified fresh rebuild. Retain old files and targets. No frontend,
general importer, production reconciliation, services, paid synthesis, private
upload, acquisition, sharing, existing-project mutation, new live Resolve action
or transcript generation here. #148 prepares real input; #145 owns the actual
disposable run. Its input availability/consent gates do not authorize services in
#148/#144 and do not turn injected #144 tests into a real run.

No frozen contracts, generated types, fixtures, goldens or accepted tests change.
New implementation, test data and evidence are issue-owned. No package dependency
is added: use the accepted libraries and standard-library file/hash/SQLite APIs.

## Seams and decisions

| Seam | Input and output | Binding / safety |
| --- | --- | --- |
| Host CLI | ScriptDocument, CompilerDependencies, materialization plan → proof request | Node24.19.0 compiler; Python3.12 locked package/jobs/accepted external Studio adapter. Validate and hash literal inputs. No accepted imports inside the WI runtime. |
| Durable build | Request → #35 job/stage receipts → actual compiler manifest/report → actual #34 package/Studio result | Use stable input-derived build IDs and idempotency keys, existing job IDs/leases, immutable files and package verification. Request no #35 render/upload stages; neither has a proof adapter. |
| Prepared inputs | All #35 core stages run: `generating_speech` and `resolving_media` verify local files before compile | Speech verifies prepared/spliced dependency text/revision/audio hash and actual bytes; media verifies approved local materializations. No NarrationService/provider/Polly/boto3 import, synthesis, acquisition or cloud call. Missing assets refuse. |
| Proof link setup | Verified fresh target + uniquely mapped video/source-audio pair → pre/post link journal | Separate source files/IDs; `SetClipsLinked`, reciprocal exactly-two links, identical ranges and 100% speed. Only links may change. Post-link capture is the baseline. Reapply for each fresh proof target. |
| WI capture | Guarded verified target → two complete observations and managed UID map | One WI entry for both reads. Exact project/timeline UID, settings, source hashes, source/record ranges, track, speed, links, availability. Initial binding requires one unique pristine candidate per manifest event. Later matching uses retained UIDs; signatures never prove ancestry. |
| Program render | Same WI entry + guarded observed target → complete PCM output and job/readback receipt | Bind intent, unique job UID, queued actual settings, full start/end extent and pre/post fingerprints. Refuse unexpected ranges/codec/routing before rendering. Preserve uncertain job/output; no automatic duplicate render. |
| Proposal | Baseline + current script + current observation + output evidence → deterministic report | Hash all three immutable inputs. Unknown IDs, duplicates, missing/offline media, altered sources, unsupported timing or observed drift refuse visibly. |
| Local decision | Report hash + baseline/script/observation hashes + explicit accept/reject per proposal | Reject unknown/duplicate/missing IDs and unsupported accepts; no implicit narration rewrite. Identical replay returns identical revision; stale decisions fail. |
| Canonical revision | Accepted supported operations → new validator-passing ScriptDocument | Retain token IDs/order except explicit omission. Visual edits bump only event/anchor versions. Omission bumps narration and affected anchored entities. Increment local sequence once; empty local state vector. Hash canonical document excluding its own `liveContentHash` using the actual compiler serializer. |
| Fresh rebuild | New revision + verified local dependency/materialization inputs → new package/job/Studio target | No paid synthesis. Proposed PCM splice route below emits new text/revision-bound audio/timing. Validate/compile/package/build/verify against the new manifest; only then publish a new baseline. |

### Entry commands and owned files

- Implemented compiler entry:
  `node packages/contracts/src/issue-144-compile-cli.ts script-document.json compiler-dependencies.json`.
  It writes one canonical compiler-only envelope to stdout, containing the
  unchanged manifest/report strings and their hashes, raw input byte hashes,
  source/schema hashes, separate lockfile hash and pinned runtime. Installed
  dependencies are bound through the locked `npm ci`, not fully attested by
  this receipt. Persistent input/source/lock drift exits 75, distinct from a
  compiler refusal (exit 1 plus a valid `ok:false` envelope). The host checks
  `node --version` before invoking it. Re-reads do not prove atomicity or catch
  reverted changes. It writes no source or output files. Host stages
  publish those bytes through #35's immutable-output API.
  Host operator input parsing rejects BOMs, duplicate keys and non-finite
  numbers before calling the compiler. Use stdlib `json.loads` hooks:
  `object_pairs_hook` rejects duplicate keys, `parse_constant` rejects literal
  NaN/Infinity and `parse_float` checks `math.isfinite` for overflow (e.g. 1e400).
  `parse_int` refuses outside JavaScript's exact integer range (±(2^53−1)).
  No custom tokenizer. The standalone compiler uses the
  accepted `JSON.parse` semantics for duplicate keys; it is not the strict
  operator gate. Normal reformatted JSON remains hash-bound and accepted.
  Every #144-produced revision/dependency uses the actual TypeScript canonical
  serializer; never impose the local revision hash rule on #148 input.
- Planned host entry:
  `uv run --frozen python -m vera_timeline_agent.roundtrip_proof <action> --proof-root <directory>`.
  Actions: preflight, build, bind-baseline, propose, decide, rebuild, verify,
  promote and status. Operator files are `proof-request.json`,
  `script-document.json`, `compiler-dependencies.json`, `materialization-plan.json`,
  `observation-a.json`, `observation-b.json`, `program-evidence.json` and
  `decisions.json`. Generated files include immutable proposals, decision/revision
  receipts, job/artifact receipts, source/occurrence map and baseline pointer.
- Implemented core-stage building block:
  `uv run --frozen python -m vera_timeline_agent.roundtrip_build --proof-root <directory> --node-executable <pinned-node>`.
  Four literal inputs (request/script/dependencies/materialization plan), five
  real core stages, immutable input-derived run/job identity and exact compiler/
  package verification. Request schema `issue-144-prepared-build/v1` contains
  evidenceLevel and verifiedAt. Narration artifactId equals dependency assetId.
  Build IDs remain pinned in the literal dependencies at this segment; canonical
  revision preparation must create fresh input-derived IDs before rebuilding.
  Native stages explicitly wait, so exit2 is expected. No baseline is published.
- Implemented injected native building block: `NativeStages` in
  `roundtrip_native.py`, supplied explicitly to `PreparedBuild.run(adapter=...)`.
  Tests supply fake factory/local facts and a fresh inspector; native evidence
  is `synthetic_injected`. Exclusive/fsynced intent precedes actual accepted
  assembly invocation; missing result waits without retry. Real guarded WI
  inspector/native authorization and host command remain to be implemented.
- Planned stdlib-only WI entry: `python/vera_timeline_agent/roundtrip_wi.py`,
  staged/launched through the existing approved WI boundary with `request.json`.
  Actions: capture, link, render and inspect-render. Guard current target UID and
  declared disposable proof before any mutation. Host never assumes this imports
  Python3.12 dependencies. Two captures use the same entry/build.
- Evidence levels: `local_prepared` (five core stages), `compiler_only`, `synthetic_injected`,
  `retained_native_observation` and later `real_issue145`. Retained gate evidence
  and injected complete-pipeline evidence remain separate. New native tests,
  private media and real narration approval are #145 work.
- Proposed ownership: the two new issue-owned TypeScript entry/semantic modules,
  Python proof/WI/audio modules, new issue-owned tests/data and this runbook.
  Existing compiler, Studio/job implementations and accepted tests stay unchanged.

### Supported semantic mapping

Visual move: retain the normal-speed linked +25-frame placement envelope from
Studio21.1.0 build14. Its pair is separate `base.mov` video and `repeated.wav`
audio linked by `SetClipsLinked`, not a single embedded-audio occurrence.
The proof setup pairs the compiled ready `audioPolicy: use_source` video and its
source audio. Muted/independently moved visuals refuse. Require unchanged source
ranges, reciprocal pair links and equal +25 deltas. Enumerate canonical
before-first/after-last token intervals within one block; normalized token-index
candidates must be unique, including after frame rounding. Block end is permitted
only as the compiler's derived final-token end. The actual compiler must reproduce
both record endpoints with unchanged source range. Require clearance on both the
video layer and shared source-audio track, and validator-passing vacated coverage.
Change `VisualEvent.range`, not spoken order or narration version.

Source trim: retain the normal-speed linked 25-frame end-trim envelope on that
build. Both items must shorten by 25 with starts/source identity/links unchanged.
A unique earlier token boundary must reproduce record and source ends through
the actual compiler. Keep coverage and non-overlap valid. No arbitrary trim,
retime, changed source start or sample-exact assertion. Track indices, neighboring
items and exact durations differ from historical #141 and must be re-proved in
#145, never inferred from the retained synthetic envelope.

Spoken omission: the retained W1 positive is Charlie absent from the linked-cut
**complete rendered mix** on WI Studio21.1.1.10. Reconstruct the complete
399-frame / 766,080-sample program from hash-bound enabled A1/A2/A3 occurrences
and observed source/record intervals, preserving each channel. Account for gain
per route using retained calibration; require bounded windowed residual and
target-support/partial-residue checks. The independent repository measurement
uses complete stereo PCM, route gains fit from unchanged picture-only audio,
and a fixed 20 ms (960 sample) window. Gains are approximately 1.000/0.708/0.708;
largest retained supported residual is 0.004246 RMS, versus 0.233422 for a
synthetic half-word overlay. Freeze a bounded calibration profile and tests
before using a verdict; these measurements alone are not a speech classifier.
Checkpoint 3 boundary probes show that quiet/tiny synthetic residue can pass the
proposed RMS limits. Do not freeze those limits as an absence classifier or tune
them to pass a test. The closed W1 route/support profile and safe uncertainty
boundary require checkpoint 4 review before a positive gate is implemented.
New cases need an unchanged reference and plausible bounded gains, never a fit
to the edited output that can hide residue. W1 target/neighbor supports are
**fixture-generator declarations** from the hash-bound media manifest; label
them accordingly. Real input requires independently verified supports.
Geometry must fully remove the target's support and preserve neighboring supports;
geometry alone is insufficient. Unknown routes, source bytes, effects, automation,
partial supports or incomplete renders refuse. Attributable A2 or shifted retained
words need not be silent. Picture-only retains Charlie; disabled A1 is a whole
route loss and must not become a phrase proposal. W1's embedded-linked omission
topology differs from VERA's standalone narration; #145 must re-prove the route.
Source transcripts, subtitle strings, mute flags and missing transcripts are not
absence evidence. If transcripts become necessary, stop for accepted #146 and
its canonical prerequisite. No all-refused or smaller-positive substitute.

### Proposed local narration rebuild and exact wording rule

For an explicitly accepted omission, propose a lossless splice of the hash-bound
original normalized local narration: PCM-24 mono, 48 kHz, 25/1, 100% speed,
frame-aligned cut inside independently verified silence around the phrase.
At this rate one frame is exactly 1,920 samples / 40 ms. Refuse audible joins,
partial target/retained support, fractional timing, effects or missing original
assets. Create a new file; preserve the original. Remove the corresponding word
marks, subtract exactly the removed duration from later `timeMs`, update retained
UTF-16 offsets, and drop sentence marks on this word-precision lane. Emit a new
schema-valid NarrationDependency directly, deterministic asset ID/audio hash and
`splice-derived/v1` alignment, plus separate splice provenance. Do not represent
it as a Polly `temp_synthetic` NarrationAudioAsset or keep stale text-bound audio.

Bounded text policy for review: one contiguous **interior** token interval in a
single narration block; nonempty retained neighbors; gaps containing only ASCII
space, tab, LF or CR to
those neighbors. Replace the character span from the previous retained token's
end through the following retained token's start with one ASCII space. Remove
only selected token IDs; shift later offsets by the exact UTF-16 length change.
For example `Alpha Bravo Charlie Delta` becomes `Alpha Bravo Delta` when Charlie
alone is accepted. Refuse first/last-token deletion, punctuation outside selected
tokens in the joining gaps (which also refuses a sentence boundary), and any visual/host-span/
annotation/beat anchor endpoint on a removed token. Ranges enclosing the phrase
retain endpoints and receive new quoted text/version. Validate the complete
revision before publication. No grammar correction, capitalization rewrite or
spoken reordering is inferred. Producer route/wording choice is pending; new
real input and exact before/after approval belong to #148/#145.

For #145, select one exact build and record host External Scripting Local (the
historical WI evidence ran with it None). Re-prove assembly including any still/
placeholder end compensation, linked setup, move, trim and standalone narration
omission; then verify a complete render of the rebuilt target. The retained W1
verdict does not authenticate real input. Preflight separates script/media checks
from narration-dependent checks. #148 can only use already available local
narration; it cannot create paid/cloud audio to satisfy anchor/support checks.
If original narration or qualifying timings are absent, retain a named readiness
blocker with the dependent checks pending. Do not silently treat #148 as accepted
or bypass its dependency on #145. Producer/steward must resolve preparation
ownership or amend that future sequence before real-input preflight can pass.
#144 itself has no cycle: use public W1 and issue-owned synthetic pipeline inputs.
Missing assets or unsuitable boundaries do not authorize synthesis, invented
timings or dropping a named positive.

### Freshness and recovery

Two adjacent equal observations detect observed drift, not ABA or atomicity.
Recheck script, input/code hashes and complete observation before decisions and
each stage. Local lock serializes proof operations. Decision receipt key binds
literal decision bytes, proposal, baseline, script and observation hashes plus
code/build lane. Completed identical replay returns its receipt even after
promotion; a different stale decision refuses. Pin package `verified_at` in the
immutable request. Input-derived build IDs/idempotency keys reuse #35's existing
job identity, rather than modifying its UUID/lease core.

Persist native intent through the assembly `adapter_factory` wrapper before
calling `run_studio_assembly`. Project UID first becomes known at WI capture;
the accepted name lookup searches only the current folder. A lost creation
response requires read-only identification within the current project folder
using the accepted lookup, or explicit operator identification. Cross-folder
automatic search has no verified project-manager API and remains unsupported.
Even a unique name alone does not establish target ancestry. Lost response/name collision waits;
read-only rehydration verifies target UID and manifests from package-relative
media paths, hashes and current track/occurrence facts, not only creation-time
maps. Never retry uncertain creation/render/link automatically. Preserve partial
targets; a deliberate replacement needs a new recorded attempt/build/job identity.
Failed verification retains prior baseline. Promotion takes the lock, compares
the prior pointer hash, atomically replaces the pointer and fsyncs the directory
only after all fresh-target verification passes. Old revisions/timelines remain.

Compose accepted edits against original token identity: apply proven omission,
update surviving anchors, then apply explicit visual candidates and compile once.
Use the actual compiled candidate as the geometry authority. Compare all retained
non-narration occurrences and the explicit narration splice segment map to the
observations; do not equate old split narration UIDs/source IDs to a new single
narration asset. The W1 cut has a one-frame gap [99,100), so it is not automatically
equal to a gapless splice. Lift gaps, spanning items and non-uniform downstream
shifts must either match this explicit compiler-backed mapping or refuse.
Full program evidence binds the semantic narration equivalence. Rebuilt geometry
is checked against the new compile, not copied from observations.

## Test-first checks and automated acceptance

New focused tests cover three positive semantic mappings, wrong project/timeline/
source, duplicate/ambiguous occurrence, stale observation/decision, malformed
decisions, partial-word uncertainty, picture-only cuts, residual speech,
unavailable media, deterministic replay, rejected input immutability and failed/
interrupted rebuild. Retained-native observations and synthetic injected pipeline
tests have separate honest evidence labels. Run accepted compiler byte-identical
goldens, focused #34/#35/package regressions, generated-currentness/frozen/lock
audits, `git diff --check`, then full `npm run validate` on a pinned commit.

Named new seam checks: reconstruction partial head/tail, opposite-channel residue,
unattributed route, out-of-range gain, incomplete extent and wrong fingerprint;
splice fractional-frame cut, audible join, exact `timeMs` shift, dropped sentence
marks and UTF-16 surrogate pairs; wording punctuation gap, edge-token deletion
and removed anchor endpoint; linking extra/non-reciprocal links and unequal ranges;
speech/media stages missing or changed bytes and no synthesis/provider imports.
The compiler boundary additionally covers torture golden bytes, BOM rejection,
observed drift and exact output hashes. No accepted tests are changed.

Runtime/bootstrap: Node24.19.0, npm11.17.0, Python3.12.14, uv0.12.5; locked
`npm ci` and `uv sync --frozen`. Default Node26 is not the pinned runtime.
Retain exact commands, versions, counts, input/output hashes, failures and fixes.

First compiler segment: eight new subprocess tests were red before the entry
existed, then **70 passed** with the 62 accepted compiler/validator regressions.
Existing minimal/torture golden bytes are unchanged. Focused lint, package
typecheck and `git diff --check` pass. These establish only the compiler entry;
integrated proposal/rebuild tests and full validation remain outstanding.

Numbered runbook will give literal files and commands for preflight, baseline,
operator edits, capture, proposal, decisions, canonical revision, rebuilt target,
verification and recovery. Every artifact declares evidence level. Handoff
distinguishes verified support, safe refusal and untested requirements and gives
#148 preparation expectations and #145 three-edit procedure. Automated checks
do not count as the real run. Move to In review with evidence; do not self-close.
No Producer approval is required for deterministic checks; any product judgment
will receive precise numbered Producer steps.

## Forecast

The initial **6–12 remaining active-work hours** forecast is withdrawn after
Claude checkpoint 1 exposed unresolved topology and executable rebuild seams.
Re-estimate after the corrected executable plan and first actual compiler/package
stage test. Approval waits and later #148/#145 work are excluded. Update material
scope/evidence/forecast changes here and in handoff.

After the first actual compiler/package/job stage test: planning estimate
**8–16 remaining active-work hours**, excluding Producer waits and #148/#145.
Semantic mapping/decisions/revision, qualified audio/splice, WI sidecar, native
injection/recovery, baseline promotion, integration and runbook remain. Revise
if the audio/recovery checkpoint changes the executable design.
