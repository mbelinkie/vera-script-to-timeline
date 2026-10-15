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

Current implementation SHA-256s (plain hex):

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
