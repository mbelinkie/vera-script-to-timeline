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
