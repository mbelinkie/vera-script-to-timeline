# #202 final reviewed candidate

Automated acceptance is pending the complete cloud/local gate. No native,
provider, acoustic, visual or Producer acceptance is claimed by this artifact.
The accepted integration baseline is
`bd6048b02604954df037bf0b2dd01906e986d19d` (#190), merged cleanly into this
task's dedicated branch. #192 retains all native inference, authentication,
fresh package/delivery/reopen and final combined proof obligations.

## Final internal API and sources

Direct internal import:
`packages/contracts/src/issue-192-v2-revision-core.ts`.

- `prepareRevisionInputsV2` validates a ready baseline, consumes explicit A/B
  commands and an already accepted #191 C omission, and returns exact staged
  document/dependencies/regeneration. Explicit fresh preparation bindings must
  cover actual new duration; caller authentication and authorization remain
  required. A/B plus C advances live head twice, preserving staged identity.
- `createRevisionProposalV2` consumes the exact #191 staged handoff, uses
  actual compiled fresh audio duration, freezes final timeline into returned
  dependencies, recompiles deterministically and checks manifest/report/
  dependency timeline and report dependency-hash closure before proposal hash.
- `decideRevisionV2` reconstructs current proposal, verifies baseline document,
  dependency/live head/proposal/history identity and explicit accept/reject.
  Reject returns original objects. Caller persists returned history atomically
  with its document revision. No external effect is emitted by the core.

Raw SHA256:

| File | SHA256 |
| --- | --- |
| New core | `368d0f5ed125db82a87e7a3056b190664d07814ec348da8e29068ec400778631` |
| New tests | `daf15a3a656578a418f7f27d5af813c25dcae3b50cc996ba2439a6da76c1851d` |

Signatures and accepted #191 staged prior-dependency binding are unchanged.
Comparison content changes proposal hashes relative to earlier candidates:
e66b744, 77b82b3 and their retained proposals are superseded, not normalized
after acceptance. Structured comparison preserves complete event/source
impacts; readable cells show block/slot, record/source/audio sample ranges,
track/picture/mapping/preparation and per-source summaries.

## Retained review and focused/fast evidence

Initial and delta reviews both returned GO with no blockers. Actual reviewer
was `claude-opus-5-5`, tools disabled, not a fabricated independent execution.
Exact reviews, sessions, limitations and dispositions are beside this file.
Timeline closure was first reproduced red against the earlier source (four
positive assertions), then corrected solely in the new core. Required
preservation/refusal coverage was expanded before the final complete gate.

Final executable source/test state was checked as
`5ec08503d4c04f9d660592db7251fe8b94c1b7d8`, tree
`1ef1414a66cda229f570b0855f1813723d4369d0`:

- Whole new test file: ten passed, no filtering/skips, exit 0. Log SHA256
  `74bdc1beb697d38b666cbf1b3c1e2d598d71dda86bbfd56b8e87779fa2661161`.
- `VITEST_MAX_WORKERS=1 PYTEST_ADDOPTS=--durations=25 npm run validate:fast`:
  exit 0; 440 Vitest cases across workspaces, 61 Node cases, 474 non-slow Python
  cases; generated-currentness, all lint/types and frozen compiler golden
  checks included. Log SHA256
  `68e84ca0e009dcdd15a151cc040ac394bc8f9a5798729a9b742c5e11ea609db0`.
- Pinned local Node 24.19.0/npm 11.17.0/uv 0.12.5/Python 3.12.14, Darwin/x64,
  own frozen Python environment. Dependencies use the previously recorded
  lock-equivalent third-party overlay and this task's own workspace links.

Subsequent differences are review/disposition/final-candidate Markdown only.
No executable source, tests, controls, configuration, manifests, lockfiles,
generated files, fixtures or goldens change. TypeScript checks consume src/
test and schemas; Python lint/type/tests consume Python files; generated checks
walk contracts; roadmap reads its configured JSON; progress uses board data.
These new review Markdown files are not read by those checks. Exact complete
cloud evidence nevertheless tests the entire delivered tree including them.
Failed startup/type/lint/test runs remain retained failures, never green.

## Complete acceptance and closeout

Only an actual complete full gate supplies acceptance. For qualified pure
logic cloud substitution, use an immutable clean accepted-main checkout's
validator, profile digest
`1d6b3c41d0bfbba1c9e012796a1067ebba7944e6a8615ecf96e77444071257c7`,
`excluding-media-sensitive` scope and the real Ubuntu run artifact. Require
exact delivered/integration tree, complete inventory, zero unqualified skips,
unchanged controls/tools/input identities and every attempt's disposition.
No candidate validator, local manifest or CI color substitutes for this.

The implementation owner retains final run/validator evidence on the issue/PR
and in ignored local receipts; no post-gate repository edit changes the tested
tree. Then create/attach the PR, verify its exact head and complete passing CI,
merge as authorized, retain post-merge integration evidence, record roadmap
review and Automated completion, and independently confirm Closed/Done. The
claim's final cached-inclusive local token metric is stewardship after the
task finishes, never an estimate or account-wide total.
