# Issue #8 checkpoint — 2026-10-14

Owner: `01a13277-8209-79b1-a9bc-9b42c5cc27c2`, Sol/high,
`codex/8-curated-fusion-studio`. Live board confirmed In progress with this
owner. Baseline `4e31565`; prerequisite integration commits `9bb4f9b` and
`be6831d`; remaining approved integration and the reviewed implementation are
being preserved as one local candidate commit. No push, merge or closure.

Producer approved the prerequisite integration note in
docs/plans/issue-8-studio-live-placement.md. The implementation now includes a
Studio-only verified envelope, unchanged original compiler files, a separately
verified internal transport view and the pinned EV24 placement/verification
adapter. Default Free writers still reject graphics. No badge override loading.

Completed checks:

- Accepted dependency focused inventory: 36 TypeScript and 12 Python passed.
- Generated types current; the four added v1 schema variants match accepted
  #7 exactly. Accepted EV24 assets, dependency tests and #7 data/goldens match
  `7cb942e` exactly. Earlier fixtures/goldens and both locks are unchanged.
- Initial new package/control suite: 20 passed, including six real compiled
  package cases and tamper rejection. Six retained packages are verified under
  out/issue8/packages/{standard,overrides,otis}-{64,120}.
- The first fast gate failed 26 native-CLI cases. The approved old compiler's
  parameter-property syntax and file-backed registration import were the
  cause. Compatibility repair now passes all 54 affected CLI/compiler tests;
  log out/issue8/cli-integration-delta.log. Failed log is retained separately.
- Post-review pure adapter/package checks: 21 passed, 13 slow deselected.
  Tests drive fresh-object simulated reopen and reject changed semantic/use/
  graph/atlas/bin/provenance/range/track facts. Four-file Python lint and mypy
  passed. TypeScript lint/typecheck passed before the final compatibility delta;
  final fast validation remains required.
- git diff --check and staged whitespace check pass.

Independent review: out/issue8/claude-review.txt; fixes and added coverage are
described in out/issue8/review-delta-prompt.md. The completed read-only delta
review returned GO for the automated candidate in
out/issue8/claude-review-delta.txt. No actual runtime/slow/full evidence is
inferred. A second narrow review, out/issue8/claude-review-matrix.txt, returned
GO for the one-field acceptance revision and operator/runtime documents.
Both reviews had Read/Grep/Glob only; no tests, commands or Resolve actions.

Pre-#109-adaptation implementation SHA-256s (plain hex; retained provenance,
not the current injected candidate):

- studio_graphics.py: `0f77b8f376c5390d5402ab3af4ec46e2b7181b4536da73b131ad2910ce4eabbd`
- studio_graphics_cli.py: `68b5a74643a5b8673e57aa07437471081d58bf356df3bd28dc1cc585b093e50e`
- test_studio_graphics.py: `d46c0bd833ec99709c2f91f847bb7da72588f2d00376383d69a26c75013807b4`
- test_studio_graphics_adapter.py: `10b9ce0eb7ff2ff92442c0ed09e132384eb2e8c6e044227aad294b129d665e86`
- studio-graphics-inputs.test.ts: `b8b386f7a79c5e8f1df9c8264752ed18ab643ea9fc2e7b80887a82b958c60c8a`
- ev24-identity.ts: `171df375951fbcabdbeef4e5fc49932bec4d073c45741a37a883add3b90601ad`

Capacity gate: the current private coordinator reservation explicitly belongs
to #214, task 01a13cdf-1a4f-7f13-93ef-4b1a4c8a31dc. Its current owner checkpoint
is phase10-final-completeLOCALvalidation-live, runner99249; actual child99867
`npm run validate` was confirmed live on this continuation. Prior review96620
completed exit0/drained; it is not the current job. Heavy slot held=true,
released=false. No #8 heavy job remains live. Do not
start slow deltas, fast or final full validation before that slot is expressly
released. Never stop another owner's job or alter its reservation. Cloud
substitution is ineligible because the prerequisite integration changes a
package manifest and the candidate touches media packaging.

External gate: Studio is now21.1.1/build10; accepted EV24 remains21.1.0/build14.
Launch timed out and status remained not running. The package preflight
out/issue8/resolve-preflight.json stopped before API import: old21.0.4 installer
receipt and absent expected scripting README. No native graphic/project/render
was created. Preserve the accepted checks. Actual input descriptor, scoped
atlas mapping, graph persistence and 64/120 duration compensation need real
qualification. The accepted #3/#34 PNG end-frame recipes differ; inspect this
first in the native matrix, without guessing a replacement rule.

Continuation progress: added a seventh actual compiler case, revised-120, with
fresh build UUID000000000007, the same stable graphic-use/range, incremented
visual-event version and only Top Line changed to The Code — revised. The
single TS matrix test passed. 21 nonslow Python checks passed,14slow deselected
in13.28s. Scoped TS types passed. Initial scoped lint exposed untyped JSON in
the new assertion; it now uses the generated TimelineManifestV1 type and exact
graphic narrowing. Scoped lint rerun completed exit0 (session92749), as did
scoped TS types (session99000).
Production source hashes remain identical to the first GO. Four accepted #7
schemas and its tests/data remain exact; earlier frozen data and both locks
unchanged; working and staged whitespace checks passed.

Final scoped TS matrix test passed in4.20s with one worker and retained all
seven actually compiled cases in out/issue8/revision-inputs. All original six
manifests/reports and registered-template files compare byte-identical to
out/issue8/inputs. No retained seventh package yet. After capacity release
prepare revised-120 from that fresh input directory. Run14affected
slow checks serially, final fast checks and complete qualifying local gate.

External next-action decision is documented in runtime-assessment.md: accepted
#109 source8ef9f864 supports current injected21.1.1/10 delivery but cannot simply
load this candidate's Python3.12 verifier dependencies or accept its separate
template bin. Its native acceptance is not EV24 qualification. No109source was
imported, guard weakened or global installation performed. Need bounded
#109-based integration direction plus operator-owned install/launch and actual
EV24qualification, or an already-qualified supported EV24 installation.
Operator checklist now names exact seven builds and required outputs, clearly
NOT RUNNABLE yet; it never treats Transport as successful graphic placement.
No native/visual acceptance, review status promotion, closure or merge claimed.

Forecast retained in the plan: 1–3 active hours plus final validation runtime;
capacity and Resolve qualification/Producer visual waits are separate and
currently unbounded. No successor is authorized.

## Approved injected adaptation continuation

The Producer explicitly approved adapting #8 to accepted #109 for installed
Studio21.1.1. The live board was re-inspected: same active task/branch,
In progress, External, dependencies resolved. No new claim, dispatch or scope
outside the approved plan. Goal resumed; actual acceptance is still missing.

Accepted109source8ef9f864 modules, menu script and regression tests are now
integrated. Default non-graphics delivery behavior is retained. The two
accepted regression files are byte-identical: Git blobs23c185b97721fc010ea7f7955a9c9f86ccba7ea4
and3c667d28ff7aa61ef1980786809af433f132a300 respectively. Only trusted internal
factory/guard/loader/runner hooks and extraction of the existing inventory
method adapt accepted delivery/launcher code. studio_spike's lazy OTIO import
is exactly the accepted109change. Contracts/assets/data/locks unchanged from
84fbf3b. No operator global installation or preference change occurred.

New standard-library studio_graphics_runtime holds the existing semantics and
native placement. External studio_graphics keeps verification and reexports
its existing API. InjectedGraphicAdapter inherits #109 UID/save/reopen guards
and calibrated still compensation0, with exact regular+template-bin inventory.
The locked external CLI attests the full Studio envelope plus transport, builds
a source-hashed Graphics release and emits explicitly authorized requests.
The old external API path keeps its receipt/version refusals unchanged.

Test-first: initial2newtests failed because the new modules did not exist.
The split then exposed12testfixture monkeypatch-target errors, repaired by
moving that target only; assertions unchanged. New runner fake lacked source
files; corrected the synthetic test fixture, not production checks. Synthetic
unit attestations are never external/native qualification evidence.

Current focused results:46passed,15slowdeselected in16.44s across three #8
test files;3unchanged109release/readback tests passed in1.26s. Scoped12file
mypy passed; Ruff passed after instance-local fake observations. New real
verifier/attestation slow test is authored but pending. CPython3.14.7 -S imports
the injected boundary without site-packages, exit0. This is import evidence,
not execution inside Resolve. Locked external runtime remainsNode24.19.0,
uv0.12.5,CPython3.12.14. Finalfast/full and affectedslow remain pending.

Candidate source release (not for installation):
out/issue8/injected-release-review-candidate/vera-graphics-v1/release.json,
rawSHA2561b61a80c8c3eeafdc1c76cc13f67d92bc58195082fc45e784b9c00520dc553a2.
Any reviewed source change invalidates it; create a new final release after
fixes. No graphics handoff or native request prepared with operator flags.

Independent read-only Claude review is live in execution session4177, output
out/issue8/claude-review-injected.txt, prompt injected-review-prompt.md. Do not
restart it; inspect actual completion. Read/Grep/Glob only, no tests/edits/native
or GitHub. Original candidate and accepted109source snapshots are beside the
prompt for comparison. Code/test bytes stable during that review.

The actual shared-slot owner is #214 phase12, runner11245; child13632pytest
was independently confirmed live on this continuation. Reservationheld=true,
released=false. No #8 heavy job started. After explicit release: prepare seventh
package, run all affectedslow and accepted109regressions serially, finalfast,
fix/deltareview as needed, and complete reviewed-source localfullgate.
Then finalsource release/handoffs and operator install/preflight/native64/120
qualification, sevenbuild visual isolation checklist. See injected-delivery.md.

Adaptation source is now local commitb5bfc6c; clean source bytes were confirmed
while review4177remained live. A subsequent complete nonslow109release run
(`uv run --frozen pytest tests/test_workflow_release.py -m 'not slow' -q`)
passed16tests,9slowdeselected in10.86s. This supersedes the earlier3testsubset
for its lightweight scope; it does not cover9slow tests. All11bundled source
files were independently rehashed and byte-compared to current repository
source, including the menu script; candidate release hash unchanged. The exact
bundled launcher also imports underCPython3.14.7 -B -S, no site-packages.
No full/local/native/visual acceptance is inferred from these checks.

## Injected review disposition and fix delta

Review4177completed exit0: automated-candidate GO, with two should-fix items
and one report-shape improvement in out/issue8/claude-review-injected.txt.
The class chain, default109behavior, faithful adapter move, stdlib closure and
fail-closed graphics were confirmed. Native/slow/full/operator gates remain.

Addressed all3items: real InjectedGraphicAdapter import now has a fake-native
wiring test asserting both regular/template expected paths and guard invocation
with the external verifier module unavailable. The attestation is read once,
hash-checked and JSON-parsed from those same bytes, explicitly refusing non-dict
JSON. Early refusal retains result schema, pins, action and discrepancy list.
Red tests reproduced the old double-read and missing-schema behavior; wiring
passed on existing code.49focused8tests passed,15slowdeselected in17.52s;
subsequent typed-import aliases plus nonobject parsing test passed4targeted,
25deselected in3.06s. Mypy2files and Ruff pass. No other production delta.

Candidate release1b61a80... is now INVALIDATED by the reviewed source fix;
retain but never install it. Build a new final-source release after final review/
checks. Narrow read-only fix review is running in execution session89143,
output out/issue8/claude-review-injected-delta.txt, prompt
out/issue8/injected-delta-review-prompt.md. Do not restart. #214's actual child
13632pytest remains live; shared-slot reservation not released.

Delta review89143completed exit0: GO, no blocking findings. Both review handles
4177/89143are terminal; do not restart/poll them. Review log rawSHA256s:
56da754cca88f1766d10ed583244e7f15ba1439744c808a6bd90c60e9f9bbfc1
(initial injected GO) and
d1daf0563462f5e334e666414802c7783beb8f8caf2cff91f0c86769769388f9
(fix delta GO). Repaired source committed5d316be; workflow rawSHA256
f98f428e323b1ee6ce252127ef9e865e47c728949c639703de8d15459102edbf,
test rawSHA256b3e5195cebd03e8dfb8a4b39a7d2d4326cb2e6d2d6176713564bb68b866acfd4.
No later production/test edits. Actual current completion is still unproved.

New reviewed-source release prepared (not installed; automated gates pending):
out/issue8/graphics-release-5d316be/vera-graphics-v1/release.json,
rawSHA256f955e0f46993028a951d3331f9ce6aaba0bd510134590b73e2e9c481c3956614.
Its bundled launcher imports underCPython3.14.7 -B -S, exit0. Old1b61a80release
remains invalid. No operator flags, installation or native project effect.

Next after explicit214slot release: prepare revised-120 package from retained
revision-inputs; run all affected slow tests serially (109delivery,109release,
8package/attestation), validate:fast, then complete VITEST_MAX_WORKERS=1 npm run
validate. No qualifying full gate exists yet. #214's actualpytest13632was still
live at23:20elapsed on the latest check; slotnotreleased. Native qualification
and operator visual/render acceptance remain subsequent independent gates.

## Scheduled validation observation — 2026-10-15

The shared slot was explicitly released by #214; coordinator owner was null
and no validation/pytest process competed before the run. Serial affected
injected/graphics checks passed 129 tests in 48.06s. Fast validation passed,
including 395 non-slow Python tests and 439 contracts cases. Logs and runtime
identities are retained in `out/issue8/full-run-state.json`.

Full run session75836 is terminal **exit1**, not green: 47 failed, 593 passed,
640 collected, 1630.98s. Tested clean commit `0b7ab1e3f7c4996a074f00a0f6c496ee5ceb0035`,
tree `fbfaba98669769471e8389fcd8ba7068348186a5`. Full failure log
`out/issue8/validate-full-0b7ab1e.log`, raw SHA256
`b663dbfaa322fa9b3bd02af45b1247191e217aeca3975ff8a2c16b25b9f94eb9`.
All 47 failures share `semantic entry receipt binding differs`: 46 direct
exceptions and one CLI result carrying that exact refusal. The scheduled
check-in was disabled after terminal observation; never resume/restart75836.

The actual TypeScript CLI advertises `./ev24-identity.ts`; Python's semantic
receipt expectation and prepared-build source inventory omitted it. New
issue-owned `test_studio_graphics_receipt_closure.py` reproduced three failures
in 2.12s: valid receipt rejected, missing identity incorrectly accepted, and
prepared inventory missing the file. Adding only the two inventory entries
made all four tests pass in 2.13s, including altered-hash rejection and actual
prepared source-currentness invalidation. Ruff lint/format checks pass.
Accepted tests/fixtures/contracts are untouched by this repair.

Current execution session28021 runs one originally failing end-to-end
composition case plus four new receipt cases, then (only on success)
`VITEST_MAX_WORKERS=1 npm run validate:fast`, with pinned Node24.19.0 and
locked Python3.12.14. Logs: `out/issue8/receipt-affected.log` and
`out/issue8/validate-fast-receipt.log`. No result is inferred yet. After success,
read-only Claude delta review must cover this two-line source repair and new
tests before a fresh full gate. If the run is still live, leave it alone and
use the timer; no active polling, competing heavy work or unchanged full rerun.
Native/operator qualification and all visual acceptance remain pending.

### Receipt-repair check-in — 12:28 UTC

Session28021 completed exit1. Its affected stage passed all five cases in
176.07s, including the formerly failing actual end-to-end composition case;
log `receipt-affected.log`, SHA256
`3569962bcaefb0a56e95fbf42c2cd77b7870511b45dce1b2fdf3f5c6b64d6a03`.
Fast validation passed generated/currentness, TypeScript and Ruff checks but
stopped at mypy: the new regression referenced `proof.subprocess`, an import
not explicitly exported by that module. Failed fast log `validate-fast-receipt.log`,
SHA256 `177ca348548500abe7979b078c9fd405172f962ff70df769db7efd41c68b032a`.
This remains failed evidence, not a fast pass.

The test now monkeypatches its own directly imported `subprocess` module
(the same module object), preserving behavior without the implicit re-export.
Production source is unchanged from the two-line receipt repair. New execution
session73746 runs the four receipt tests then fresh fast validation serially;
logs `receipt-regression-final.log` and `validate-fast-receipt-final.log`.
The existing timer will check once, without active monitoring. Delta review
and the fresh full gate remain pending.

Frozen audits pass: four v1 contracts, #7 goldens/dependency acceptance tests
match accepted7cb942e; original locks and slice1.1/1.3 data match4e31565;
accepted109delivery/release tests, package/CLI, menu bootstrap and lazy-import
studio_spike match8ef9f864. No native operations or operator flags supplied.

### Corrected fast gate and review — 12:34 UTC

Session73746 completed **exit0**. Four receipt regression cases passed in
2.28s; `receipt-regression-final.log` SHA256
`b6bb80c688cddbf7d67212041acfdc836ab8d6b3e335c81b44f5971ac9058cd0`.
The fresh fast gate passed generated-currentness, all lint/types (131 Python
files; 424 formatted), 439 contracts cases in23files, one tooling smoke case,
6progress/23roadmap/32cloud Node cases, and399non-slow Python cases in89.57s.
`validate-fast-receipt-final.log` SHA256
`1de067ba9993f6c517a540e224371a10c3bb2b63a6b953dc1570e882937354c8`.
Earlier failed evidence remains retained and is not relabeled.

Required narrow read-only Claude receipt delta review is now execution
session40286, output `out/issue8/claude-review-receipt-delta.txt`, prompt
`out/issue8/receipt-delta-review-prompt.md`. Only Read/Grep/Glob are available;
no shell, edits, tests, MCP servers, native operations or agent delegation.
Review is restricted to the two source inventory entries, new receipt test and
their real callers/hash validation. Prior injected/native candidate reviews
are retained, not restarted. Do not infer GO before actual review completion.
After GO/fixes: record final source, recheck slot/process exclusion, then a
fresh complete full gate; use a timer for long runs. Native acceptance remains
pending and no operator flags have been supplied.

### Receipt delta review GO — 12:41 UTC

Review40286 completed exit0, **GO**, with no blocking findings. Log
`out/issue8/claude-review-receipt-delta.txt`, SHA256
`936ec18d2b56e049d9fd3a855466689c142dc7754377254cd33447c50721ca17`.
It confirmed exact Python/TypeScript source inventory closure, unchanged exact
receipt equality/currentness checks, actual pinned-Node positive and missing/
altered-hash rejection, and prepared-source invalidation. Nonblocking notes:
Node is selected through PATH but exact24.19.0 fails closed; roughly2s tests
appropriately remain in the fast gate. No source/test changes after review.
The reviewer could not see some truncated intermediate fast output; the main
owner retained actual exit0 and complete log and confirmed439contracts,
1tooling,6progress,23roadmap,32cloud,399Python plus lint/types/currentness.
Full/native/visual evidence is not inferred from that review.

Pre-full check: coordinator currentHeavyOwner=null, #214 Closed/Done and heavy
slot expressly released; no competing validate/pytest/ffmpeg/ffprobe process.
Commit this exact source/test repair and retained plan/checkpoint, then run a
new `VITEST_MAX_WORKERS=1 PYTEST_ADDOPTS=--durations=25 npm run validate` with
pinned Node24.19.0/npm11.17.0 and locked Python3.12.14. New log:
`out/issue8/validate-full-receipt-reviewed.log` (never overwrite the failed
original). Exact commit/tree/session are retained in `full-run-state.json`.
Use a15minute timer for one observation per wake; leave a live run alone.
No source changes, competing heavy checks, automatic retries, native effects
or claims of full acceptance while this run is in progress.

### Full suite finished; durable exit record gap — 09:58 EDT

All644Python tests passed in4318.87s (1:11:58); all preceding stages passed:
439contracts in23files,1tooling,6progress,23roadmap,32cloud cases, generated
currentness, lint,424formatted Python files and mypy131files. Log
`out/issue8/validate-full-receipt-reviewed.log` SHA256
`f2d26dffd627cd03b45da6615a5a5c5425ebd4bf1991ef3a53ffdde151ac930b`.
Original parents38530/38531/38532 and pytest40998/40999 have exited; no active
run remains. Execution69953 expired before the desktop exposed terminal exit.
The passing summary is real, but **no direct terminal exit-zero record exists**.
Do not fabricate one or call this the policy's completed exit-zero gate.
Source was clean and byte-identical to testedcbb20b5/tree181243e4 at completion.

This is an evidence-retention gap, not a test failure and not an unchanged
failure retry. Retain the complete passing-suite coverage. A fresh full run
with an on-disk actual exit receipt is necessary to supply the policy's missing
required record. `out/issue8/run-full-durable.sh` captures command status even
if the desktop handle expires; it uses new no-clobber log/exit paths. Never
run it over existing evidence. Defer while #219 has its explicitly authorized
exclusive Resolve/render window. The scheduled check may inspect that task
once for explicit release, then check the shared coordinator and actual heavy
processes before starting. It must not interrupt, message, install into or
use Resolve. No new review is needed for unchanged production/test bytes.

Seven full-envelope/Transport attestations and preflight-only requests were
prepared, session99867exit0. New release `graphics-release-cbb20b5` matches
all11reviewed runtime files and the exact prior release-manifest hash
`f955e0f46993028a951d3331f9ce6aaba0bd510134590b73e2e9c481c3956614`;
full inventory/byte comparison exit0, CPython3.14.7 -B -S import exit0.
Complete targets/hashes: `out/issue8/operator-preparation-cbb20b5.log` and
[prepared handoff](prepared-handoff.md). All requests explicitly remain
preflight, unauthorized, settings-null. No #8 native effect has occurred.

Only handoff/checkpoint documentation changes follow the passing suite.
Repeated searches including --no-ignore-vcs found no references consuming
these issue8documents in scripts/tests/generator/packager. Source, tests,
locks, assets, contracts and frozen boundaries remain unchanged; do not
restart review or alter runtime code to solve an execution-handle problem.

### Final durable validation PASS — 11:21 EDT

The actual on-disk receipt is `{"exitCode":0}`. Full validation on clean
`f20681fd6e0dda4f2d4f6666169e9208adb49537`, tree
`0d96f3c23f4fadee91b7e19c12656cba85000aa3`, passed all644Python cases in
3442.71s (57:22), including slow tests, no skips/deselections;439contracts,
1tooling,6progress,23roadmap,32cloud cases; generated-currentness, lint,
425formatted Python files and mypy131files. Exact command/profile and retained
log/exit hashes are in [prepared handoff](prepared-handoff.md). This supersedes
the earlier exit-record gap, not the truthful disposition of earlier runs.
No further unchanged automated rerun is needed.

Original durable parent94561/94562 has exited; process search confirms no #8
runner/validate/pytest remains. **#8 releases shared heavy host capacity.**
The existing check-in is PAUSED. #219 explicitly released both native and
heavy capacity before this run, and no competing checks were started by #8.
Resolve was untouched. External Scripting was last reported Local by #219;
None remains unconfirmed. No installation, settings change, build authorization,
native placement or visual acceptance is claimed.

Source/tests/config/locks/contracts/fixtures/integrations matched reviewed
cbb20b5 and testedf20681f at completion. Repeated frozen audits passed against
accepted7cb942e/#7,4e31565originallocks/fixtures,8ef9f864/#109 unchanged tests
and stable package/bootstrap sources. Post-full artifact recheck exit0:
`out/issue8/post-full-artifact-audit.log`, SHA256
`f24124a3a1481bff12d6d8b298cedfad5a876da1e9e3086e7df17313f6dca609`.
All11release source bytes, full inventory/hash, all7handoffs and all7requests
remain current. Every request is still preflight-only, unauthorized and
settings-null. Artifact preparation consumed synthetic issue-owned media only.

Post-test changes are limited to this checkpoint and operator handoff docs,
not consumed by generation, lint/types/tests, dashboard/roadmap or packaging
(search repeated with --no-ignore-vcs). Whitespace/local-link checks cover
those changes. Automated implementation is ready for External review, not
closure. Next: operator manually installs the exact graphics release, confirms
None, saves a separate disposable current project/timeline, launches the
standard-64 preflight once and returns its result/first refusal. Only later
explicit named-target build authorization permits native placement. The seven
native/reopen/visual/timing/isolation checks remain mandatory.

### Producer-authorized file installation

The Producer asked whether the agent could perform the next file-placement
steps. This supersedes the prior agent-installation exclusion only for the
two exact Graphics entries and the existing preflight-only request. Resolve
was not running, destination was writable and neither Graphics target existed.
No overwrite, archive, admin elevation, other-plugin change or preference
mutation was needed. Copied the reviewed release into the exact Workflow
Integration Plugins directory and standard-64 preflight as its request.json.
Post-copy all11declared files and release manifest are byte-identical to the
reviewed source; request hash6473916bf6102d3cf1448c2f2cb41a0425482cb603b3d16fc8f8656b2623addf,
mode0400, actionpreflight, authorizationfalse, settingsnull. Receipt:
`out/issue8/installation-receipt.json`. No app launch/native action occurred.

Reviewed production/test/package bytes are unchanged; no automated rerun is
needed for file copying or these non-consumed handoff documentation changes.
Remaining first step: Producer opens Resolve, confirms None and retains safe
scripted actions, saves a separate disposable current project/timeline on Edit,
launches VERA Graphics v1 once and returns preflight result/first refusal.
No new-target build authorization or visual acceptance has been supplied.

### First authorized native run — failure retained

Producer confirmed the preflight sequence done. Actual result
`result-f1ecda3ae4ec4967963fff6684eee3ba.json`: preflight_passed on Studio21.1.1/10,
Python3.14.7, no discrepancies; hash
`a820f51d9b13b1670c724b05627cf68b1a864dc430a65f93f86fd41226523d52`.
Producer then explicitly said `Authorize this disposable build` for the exact
standard-64 target6066118d9c7d. The build request hash
`6c00fb4a4f1e9c0377ea4b068fbf55dc6dc41ebc96332c4b5d8d17edffe22cfb`
binds actionbuild, authorizationtrue and the Producer's None statement.
After Producer closed Resolve and no process remained, the old preflight
request was moved intact outside the plugin root into the private request
archive and the build request copied/verified. Runtime bytes stayed unchanged.

Producer relaunched once and reported done. Native result
`out/issue8/native-evidence/standard-64/result-f376f182a6c84ef8a973e89e15d28a4c.json`,
SHA256 `5bf4c3c6f8e9a8e7e02593525872c1851c16d5f91b9e5fb6ac47a1161d5418ad`,
reports **verification_failed**, `verified:false`, partialTargetRetained:true:
`EV24 verification failed: reopened Fusion graph fingerprint differs`.
The target was created/saved/reopened and media verification is recorded;
graphic observations remain empty. The code's semantic-value and stable-use
checks precede the failing combined graph-hash/persistent-hash comparison.
That does not qualify graph persistence, atlas mapping, rendering or acceptance.
Keep the exact partial target unchanged; do not rerun the installed build.

The result does not retain pre-save/raw reopened settings or separate which
fingerprint branch failed. No root cause or compatibility normalization is
asserted. No production/accepted-test/fixture/contract change has been made.
Following diagnosing-bugs, the next evidence is a guarded read-only native
capture, not a speculative fix. Private script
`out/issue8/diagnose-standard-64.py` SHA256
`86b5d7a25262ca67e8da01487cd93d5500b80a71e2adeef2d8718931f0ac7c7b`
requires exact current failed project/timeline and21.1.1/10, refuses rendering,
verifies the installed source release, reads repeated SaveSettings() tables,
persistent hashes/identity and controls, and writes only a new private report.
It never saves/switches projects, sets controls/data, places media or renders.
Local static/syntax/missing-API checks pass; fake-API detection and wrong-target
refusal pass after completing the synthetic fixture's missing graphic identity.
These are diagnostic safety checks, not live reproduction or native acceptance.
Producer must invoke it in Python3 Console with the existing injected resolve;
no external-scripting connection or preference change is requested.

### Read-only graph capture received

Producer ran the prepared diagnostic in Python3 after correcting the Console
language/paste. Capture `readonly-graph-91d060f2191043a39101966a9df1f60d.json`,
SHA256 `2125127f6e032c759d6205268b8bb8f2110b866d578b7822fb7f1e89b0e7d87a`,
retains actual project/timeline/item UIDs and two complete private settings
tables. Both production hashes are3671d53c..., persisted pre-save hash281b541c...
is present and differs. Country16/Year2024 and blank text overrides persist.
Immediate repeated reads are stable; this is not a missing stored hash or an
unstable pair of reads. Replay through the actual production fingerprint helper
reproduces the mismatch in seconds; `out/issue8/graph-replay-red.log` retains
the expected failed equality assertion.

Ranked hypotheses remain native range/display serialization, capture timing,
or a meaningful graph change. Bounded offline copies reversing GlobalOut63 to
authored119 and removing display fields, alone/in combinations, did not recreate
the pre-save hash. No native target or production code was modified and no
field was excluded from verification. Because the old raw pre-save settings
were never retained, this capture cannot reveal the exact before/after diff.
The next necessary native evidence is one fresh explicitly authorized named
disposable diagnostic build with before/after settings witnesses, keeping the
original failed target unchanged and all verification checks intact. Such
diagnostic execution is not acceptance or permission to weaken graph identity.

### Second-target diagnostic prepared; review and host exclusion pending

Producer approved `yes prepare build` for exact overrides-64 target
`VERA Delivery 88000000-0000-4000-8000-000000000002 d859f645132f`.
Private diagnostic build request hash075b7569fc2b2309c2fc51a1c88b333ad59122942f60c2bf552706287ddabc2f
is prepared, with existing full-envelope attestation and source-equivalent
installed release. No installed request/release or production code was changed.
Private script `out/issue8/diagnostic-overrides-64.py` temporarily observes only
the two existing production fingerprint calls, one raw SaveSettings read per
call, hashes those same tables with the original helper and returns unchanged
hashes. Witnesses record before-save/after-reopen settings; the separate index
is diagnosticOnly/acceptancefalse. The old failed target cannot be used as the
current origin; fresh interpreter, exact authorization/runtime/source guards,
no-active-render and one-shot private evidence guards apply. Native work runs
only through the unchanged audited injected request runner.

Fake-boundary safety harness exit0 (no live API/native evidence writes), Ruff
pass and CPython3.14 -B -S stdlib-only load/no-auto-run pass. Original captured
graph mismatch stays a mismatch through the observer. Safety review33462 is
running read-only (Read/Grep/Glob only, no commands/edits/native/other agents),
log `out/issue8/claude-diagnostic-capture-review.txt`. Do not edit its candidate
or infer a GO. Exact script/request/check hashes and pending safety follow-up
are in `out/issue8/diagnostic-overrides-64-preparation.json`.

An actual full validation process61160 belongs to #219's fa5b worktree. No
competing #8 heavy check or native action was started. The coordinator record
was stale8ownership; it is not permission to compete. Operator execution is
not yet ready: retain review outcome/fix/delta evidence and wait for actual
host release. This is preparation only, not graph qualification or acceptance.

### Diagnostic safety review and inventory fix

Review33462 completed exit0 **GO** for one diagnostic run, not acceptance.
Log `out/issue8/claude-diagnostic-capture-review.txt` SHA256
`5a4d0ec6775a647d3fca13b40d40f3a6464d0d6fe91bcc2472698bcb2e2e39d7`.
It confirmed one native settings read per original call, unmodified hash return,
all full-envelope/target/stage guards and fail-closed diagnostic writes. Minor
limits remain: some refusal branches are static-only, index-storage failure
could mask an error but cannot turn it into success, and any one-shot refusal
requires fresh authorization before retry.

Parent identified a missing installed-inventory check beyond that review's
actual-current-folder observation: declared hashes alone cannot reject an
extra importable __init__.py. A synthetic temporary-release test went red
(`diagnostic-inventory-red-exact.log`: undeclared importable file accepted).
Copied the normal accepted menu bootstrap's exact file/directory closure into
the private diagnostic only. The harness now passes baseline, extra-file,
extra-directory and declared-source-tamper cases plus all original observer/
refusal/replay checks. `diagnostic-inventory-green.log` exit0 SHA256
`4a750b87803c4d12d11375cc4615b5076bfbb70b9b3cd345329f996bcc8873a5`.
Rufflint/format and CPython3.14 -B -S/no-auto-run pass. Script now SHA256
`28ccec69d81f6cab037732f21023bd2abfeec08b09129b533070a7fa2678c4b4`.
No production/installed-source/request/contract/test/fixture change occurred.

Narrow inventory-fix review66277 is running read-only in
`out/issue8/claude-diagnostic-capture-delta-review.txt`; do not restart or infer
GO, and do not change its candidate while live. Native diagnostic is not run.
The earlier blanket host hold was corrected after the Producer asked: manual
read-only checks and this light no-render API diagnostic do not automatically
conflict with #219's full tests. No competing heavy test/media render will be
started; #219 previously released the native window. Once safety review GO is
retained, operator can restart Resolve, open the original separate saved
disposable on Edit (not either build target), keep None and invoke the new
one-off Python3 script once. Do not use the old installed Graphics build menu.

### Second-target diagnostic ready — 13:13 EDT

Narrow review66277 completed exit0 **GO**, no blockers. Log
`out/issue8/claude-diagnostic-capture-delta-review.txt` SHA256
`ffd76372cb01f4da0043673d386047d664459c241965d242475dce62fd06e704`.
It confirms inventory closure matches the accepted bootstrap and runs before
any installed runtime import. The red harness line numbers predate a
format-only rewrite; red/green order and refusal remain retained. Static-only
coverage limits and one-shot/index-write caveats are explicitly retained, not
claimed tested. No native acceptance or production fix is inferred.

Final readiness audit: script28ccec69..., request075b7569..., installed release
f955e0f4... match; all11installed declared files/exact inventory and complete
graphic handoff pass; diagnostic evidence directory remains absent. No native
API was invoked. Check-in timer PAUSED. User-authorized exact second target
is ready for one operator-run diagnostic. No installed request/source changes
or heavy tests were made, and the earlier failed target remains unchanged.

Operator: quit/restart Resolve for a fresh interpreter; open the ORIGINAL
separate saved disposable current project/timeline on Edit, not either build
target; keep External Scripting None. In Python3 Console run
`exec(open("/Users/matthewbelinkie/.codex/worktrees/46d4/VERA Script to Timeline/out/issue8/diagnostic-overrides-64.py").read()); run(resolve)`
once, without the prompt prefix. Do not launch the installed Graphics menu,
whose request still targets the failed first build. Retain result/index paths
or first error and do not rerun. This diagnostic does no rendering and need
not wait merely for #219's tests; no competing heavy test/render is authorized.

### Second-target diagnostic completed; exact mismatch isolated

Producer executed the reviewed one-shot script. Resultd5fd4ddc... reports
verification_failed after save/reopen, same graph fingerprint discrepancy;
partial target0002d859f645132f retained. Its source/request/release identities
match approval and the index confirms the original fingerprint binding was
restored, no diagnostic exception, diagnosticOnlytrue/acceptancefalse. Native
result and witness hashes are in [proposed change note](graph-persistence-change-note.md).

Exactly4serialized differences explain the hash:3specific added UserControls
__flags values and the removed exact nested RibbonUnit BadgeImage0 Input.
All other settings, expressions, connections, exposed semantic values and
actual BadgeOverride/Clip Loader binding are unchanged. Original authored
nested BadgeImage declaration refers to ClipName; this is not the actual
exposed control used by #8. No broad equivalence or visual correctness claim.
Offline replay reversing only those4changes restores complete table equality
and the original production hash; exit0, graph-exact-diff-replay.log retained.

The underlying mismatch is raw native serialization identity across persistence,
not lost semantic values or unstable immediate reads. A narrowly scoped
normalization proposal is documented for Producer approval because it changes
what the graph-identity verifier accepts. No production fix or guard relaxation
has been applied. Both failed targets remain untouched; no more Console work
or native rerun is required just to understand this captured difference.
