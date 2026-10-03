# Issue 144 — bounded file-driven round-trip harness

**Checkpoint status:** Claude reviewed the original plan at `d055f90` before
implementation. Read [the retained review and disposition](../investigations/issue-144/checkpoint-01-disposition.md)
for required corrections and the recorded Producer choice to retain the tested
linked cases through an isolated proof setup step. That disposition governs
unresolved assumptions below. Claude is reviewing the corrections; no
implementation or native action has begun at this checkpoint. #145 must verify
the actual native setup and cases on its selected build.

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

One local proof directory, literal JSON inputs/outputs, injected Resolve/WI
boundary, existing compiler, package writer/verifier, Studio assembly and
durable job store. Implement the missing connection, deterministic proposals,
explicit local decisions, new canonical revision and verified fresh rebuild.
Retain old files and targets. No frontend, general importer, production
reconciliation, services, paid synthesis, private upload, acquisition, sharing,
existing-project mutation, new live Resolve action or transcript generation in
this task. #148 prepares real input; #145 owns the actual disposable run.

No frozen contracts, generated types, fixtures, goldens or accepted tests change.
New implementation, test data and evidence are issue-owned. No package dependency
is added: use the accepted libraries and standard-library file/hash/SQLite APIs.

## Seams and decisions

| Seam | Input and output | Binding / safety |
| --- | --- | --- |
| Local CLI / injected WI entry | ScriptDocument, CompilerDependencies, materialization plan → proof request | Validate with actual v1 validator/compiler; bind bytes, revision, media hashes, declared evidence level and intended new target. |
| Durable build | Request → #35 job/stage receipts → compiler manifest/report → #34 package/Studio result | Stage keys, immutable files, package verification; no fabricated receipt or automatic retry of uncertain native effects. |
| Read-only capture | Verified new target → two complete observations and managed UID map | Exact project/timeline UID, settings, source hashes, source/record ranges, track, speed, links, availability. Initial binding requires one unique pristine candidate per manifest event. Later matching uses retained UIDs; copied signatures never prove ancestry. |
| Proposal | Baseline + current script + current observation + output evidence → deterministic report | Hash all three immutable inputs. Unknown IDs, duplicates, missing/offline media, altered sources, unsupported timing or observed drift refuse visibly. |
| Local decision | Report hash + baseline/script/observation hashes + explicit accept/reject per proposal | Reject unknown/duplicate/missing IDs and unsupported accepts; no implicit narration rewrite. Identical replay returns identical revision; stale decisions fail. |
| Canonical revision | Accepted supported operations → new validator-passing ScriptDocument | Retain token IDs/order except explicitly accepted omission. Bump affected versions and local sequence; empty collaboration vector for this local proof. Preserve originals. |
| Fresh rebuild | New revision + newly verified dependency/materialization inputs → new package/job/Studio target | Compiler binds narration text/version. New narration bytes and timing are mandatory for an omission; never reuse old text-bound dependencies. Verify new target before publishing a new baseline. |

### Supported semantic mapping

Visual move: only the retained normal-speed linked +25-frame placement envelope
on Studio21.1.0 build14. Find an unambiguous existing token anchor whose compiler
output equals the observed placement and unchanged source range. Proposal changes
`VisualEvent.range`, never spoken order. Do not invent non-null timing overrides.

Source trim: only the retained normal-speed linked 25-frame end-trim envelope on
that build. A unique earlier token boundary must reproduce both observed record
and source ends through the actual compiler. Starts/source identity/links remain
unchanged. No arbitrary trim, retime, partial-word or sample-exact assertion.

Spoken omission: consume retained W1 independently measured rendered program
evidence on WI Studio21.1.1.10. The bounded positive is Charlie absent from the
linked-cut output; picture-only retains Charlie; disabled A1 leaves A2 numbers.
The complete 399-frame / 766,080-sample stereo output includes all A1/A2/A3 pilot
routes and the independently measured preserved words. Bind its render job,
timeline/edit state, output hash, source support intervals and check records.
Source transcripts, subtitle strings, source ranges and mute flags are not the
absence gate. Residual target speech or partial/unknown edges refuse deletion.
Only an explicit accepted phrase deletion changes the canonical text. Removed
anchor endpoints require explicit repair or refusal; interior quotes/offsets
must be updated consistently and validated. No source-only or empty transcript
inference. If a transcript-based path becomes necessary, stop for accepted #146
and its canonical prerequisite; no all-refused or smaller positive substitute.

For #145, a new independent complete program-render verification is mandatory:
the retained W1 verdict cannot authenticate a different real timeline. #148 must
supply local media, independently verified relevant word support/timing and
compiler dependencies for the original and revised narration; unknown complete
audio routing/output is a readiness blocker, never guessed by the harness.

### Freshness and recovery

Two adjacent equal observations detect observed drift; they do not exclude ABA
or provide atomicity. Recheck the current script and full observed fingerprint
before decisions/rebuild. Lock the local proof operation to prevent overlapping
workers. Rejected/deferred work never advances a baseline. Publish revision and
decision receipts immutably. An interrupted native stage retains its intent and
partial target; reconcile through the injected boundary or wait for operator
inspection, never create a duplicate automatically. Failed package/build/output
verification keeps the previous baseline authoritative. Retry uses the same job
and immutable completed receipts. Only successful new verification publishes a
new baseline file; old baselines/timelines remain intact.

## Test-first checks and automated acceptance

New focused tests cover three positive semantic mappings, wrong project/timeline/
source, duplicate/ambiguous occurrence, stale observation/decision, malformed
decisions, partial-word uncertainty, picture-only cuts, residual speech,
unavailable media, deterministic replay, rejected input immutability and failed/
interrupted rebuild. Retained-native observations and synthetic injected pipeline
tests have separate honest evidence labels. Run accepted compiler byte-identical
goldens, focused #34/#35/package regressions, generated-currentness/frozen/lock
audits, `git diff --check`, then full `npm run validate` on a pinned commit.

Runtime/bootstrap: Node24.19.0, npm11.17.0, Python3.12.14, uv0.12.5; locked
`npm ci` and `uv sync --frozen`. Default Node26 is not the pinned runtime.
Retain exact commands, versions, counts, input/output hashes, failures and fixes.

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
