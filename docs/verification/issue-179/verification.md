# Issue #179 design verification

Profile: `gpt-6.1-sol/high`; one visible chat
`01a121d8-d419-73b0-bbb9-76aab14917cc`, dedicated branch
`codex/issue-179-cut-point-design`; no subagents or chained implementation.
Acceptance authority: Producer. **Proposed design only.**

## Authority and source pins

Claim followed live inspection: #179 Ready, acceptance criteria complete,
exact single `model:sol` and `effort:high`, no conflicting claim; #173 Closed
AND Done. The first mutating action was the successful exact-profile claim.
The initial inspect was refused by another active roadmap command's lock;
retry occurred after its release, without bypassing the lock or shared budget.

Clean new worktree initially had detached main
`96978919616df0148d9c4b06781aeb80acfa85e4`; created only this dedicated branch
and fast-forwarded it with `git merge --ff-only` to
`d2e241316cb032cdddc4bac5d7acd953b1af8519`. No reset or other-worktree change.
#173's tested runtime is `96fd70f573c3eaa1fc2b342de87ee9df00c64eaa`; the
publication commit retains its passing full-gate evidence. Accepted #156 plan
is `e32727f0c0e65dc5a8561e0f470ed28e59bd1809` (identical plan blob).
[source-pins.json](source-pins.json) retains SHA256 and Git blobs for the exact
specification, accepted plan/compiler/schema/adapter/fixture/generated/lock
inputs used here. Runtime source blobs match #173's tested source.

## Commands and results

All shell launches used `ctx-wire run rtk`. Test/currentness/audit commands
used Node 24.19.0 and npm 11.17.0 from the pinned bundled runtime; Vitest
4.1.11 came from the repository lockfile installed by `npm ci`. No manifest,
lock or dependency change was made. The system default Node 26.5.0 was not
used for acceptance checks. An initial `npm exec` with no node_modules tried
to fetch Vitest 5.0.3; it was stopped before any check. No result from it counts.

With `VITEST_MAX_WORKERS=1`:

```sh
npm exec -- vitest run docs/verification/issue-179/reproduction.test.ts \
  packages/contracts/test/compiler-v2.test.ts \
  packages/contracts/test/compiler-v2-schema.test.ts \
  packages/contracts/test/compiler-v2-bindings.test.ts \
  packages/contracts/test/authoring-v2.test.ts \
  packages/contracts/test/authoring-v2-schema.test.ts
```

**77 tests / 6 files passed**, including the issue-owned investigation and
all selected unmodified accepted compiler/authoring/schema tests.
[focused-tests.txt](focused-tests.txt) retains output (8.10 s). An earlier
focused launch's process receipt was unavailable after resume, so that launch
does not count; the retained run has confirmed exit 0. No golden updates.

```sh
npm run check:contracts-generated
node docs/verification/issue-179/audit.mjs
git diff --check
```

All passed. [generated-currentness.txt](generated-currentness.txt) retains
the generator result. [design-audit.json](design-audit.json) records unchanged
accepted files, local design references, runtime-source pin equality and
exact example arithmetic/reproduction consistency. The audit restricts all
new tracked/untracked artifacts to this proposal and its issue-owned docs
directory and confirms all 6275 baseline files remain present, with no
baseline changes. Source/code/contracts/fixtures/goldens/accepted tests are
frozen. The staged diff is also checked before commit/publication.

Full `npm run validate` was not rerun for this docs-only proposal. No source or
generated file changed. The exact #173 source retains its accepted full gate
(3094.986 seconds, exit 0) in baseline
`docs/verification/issue-173/automated.md`; that evidence tests accepted runtime,
not CN-179's proposed behavior. The implementation successor requires its own
full gate and issue-owned byte-repeat goldens without weakened checks.

## Evidence limits and judgment

[complete.input.json](complete.input.json), [sparse.input.json](sparse.input.json)
and [reproduction-result.json](reproduction-result.json) reproduce the current
full-token rejection. They are sanitized synthetic issue-owned derivatives,
not edits to frozen fixtures, real private inputs or acoustic qualification.
The sparse view retains exact identities for beta/gamma; only unrelated alpha
is absent. Ready complete picture becomes blocked sparse picture; narration
duration stays 96 frames at 24 fps; sparse media-needs refuses.

Expected new-input behavior and 24/25/24000/1001-fps pause/tail arithmetic are
clearly labeled proposal-only. No fake new compiler was written to make those
expectations pass. The selected separate evidence input avoids positional
full-map callers and preserves their accepted behavior. Explicit after edges
change who owns a pause without cutting or rewriting narration. Missing
required edges remain blockers; sparse entries never prove complete speech,
omission, captions, take alignment or unobserved silence.

GitHub GraphQL reads of #89/#168 timed out during duplicate review; REST reads
succeeded and confirmed separate ownership. Open/closed title/semantic search
found no existing pure sparse-boundary implementation owner. The single
successor body is retained in [successor-issue.md](successor-issue.md), with
`Blocked by #179` and tentative Sol/high, Size M, Automated acceptance. It is
an unstarted Inbox placeholder, created as
[#180](https://github.com/mbelinkie/vera-script-to-timeline/issues/180); no promotion
or dispatch.

## Forecast and Producer handoff

First substantive checkpoint forecast: 45–75 minutes remaining active work,
medium confidence, principally consumer compatibility and pause semantics.
The draft resolved those proposed choices; final checkpoint is retention and
publication, followed by a separate Producer approval wait. Resume preserved
the original claim/scope. Network waits and Producer review are separate from
active investigation. No prerequisite or implementation scope was expanded.

Open the exact published review revision of
[the design and CN-179](../../plans/issue-179-cut-point-timing.md), then execute
its §8 four-step checklist. Expected choices: unrelated missing marks allowed,
required missing edges block, before-next-word keeps the pause under the child,
audible-end reveals the parent during it, row tail/narration remain intact.
Acceptance must explicitly name the review commit and **both design and
CN-179**. Leave #179 In review until Producer acceptance; design approval
delivers no runtime behavior. #148 and #145 remain separate owners; #145
remains its accepted v1/25-fps proof, not v2/23.976.
