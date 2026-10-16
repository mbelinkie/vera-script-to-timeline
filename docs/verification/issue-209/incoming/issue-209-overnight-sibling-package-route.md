# #209 overnight sibling package route

Coordinator readiness plan, 2026-10-16, for the bounded #209 → #178 → #215
sequence. The direct Producer overnight grant authorizes this
design/compatibility/acceptance delta; this does not claim earlier exact-hash
approval of a CN-211 note. This plan changes no source, tests, contracts,
fixtures, roadmap, media, or Studio state.

## Decision

Let #209 implement its consumer without first making frozen R16 pass the
ordinary v2 packager. Add only a #209-owned
`qualification_output_package_v2.py` sibling and use the existing #209
controller, launcher, CLI, native and decoder seams. It independently binds
original and approved execution inputs. R16 is a qualification-negative case,
never a successful ordinary package or input to native setup/reservation/render.
No shared schema or generated-type edit is presumed necessary.

First establish the runnable smoke through the existing ordinary public-package
path with the same-rate synthetic case: 24000/1001, native token `23.976`,
1920×1080, 1–1498 frames, 2002 audio samples per frame, within #190's
3,000,000-sample limit. Preserve existing range, source, output, and authority
guards. This finite smoke does not replace #178's physical matrix.

## Pinned source and R16 evidence

Use accepted main `22f65c4f2b4ff61e7b08f530cdda3d92fea11d08` and exact #214
head `e2f2d7fd508b7e21a0056779eb5b8640e78859f8` (PR #216; main is an ancestor).
Pin #214 INTERFACE SHA256
`de87b21cd8ab7fa9c74bff1198b775dbb96aaee4967aa5b5c315b9d507c2800f`,
records module `ec54847a872b7fcdb6c4e434dd3e9dc2bc1d100d10a9d90d24367b96c8269e2a`,
and output module `d1d137c91eb99d76dd8eecfa3297ef677d41f59a668644ee5d7a2bea364a9684`.

Host preparation produced four actual #174 receipts and signed-24 PCM
sidecars; exact 2002-grid checks passed. Measured q values are 1549548,
11629618, 5333328, and 792792. Execution-dependency SHA256:
`ca837b3d46b07d3c431bf923c3c99629f21777872ff1bbabd0bbca6834f48780`.
The pinned compiler ran twice, exit 0 with byte-identical output. Retain these
as fixed inputs; never assume q=0 or rewrite original files.

The ordinary packager refusal is an exact negative vector: frozen dependencies
have `authoringDefaults.presenterStill=null`; the manifest resolves an
effective presenter still; the report has three
`TEMPORARY_PRESENTER_STILL` warnings and
`REPLACE_TEMPORARY_PRESENTER`. Pin the allowlist to those report-bound
occurrences/counts only; any extra diagnostic refuses. An allowlisted R16
match stays qualification-negative and grants no package/effect authority.

The sibling must authenticate original document and original dependencies as
separate raw snapshots, and execution document/dependencies as separate
snapshots. For this R16 vector, execution document bytes equal the original.
The dependency delta is exactly four approved binding replacements plus six
prepared-audio fields in each of four rows; reverse it to the pinned original.
Any other change refuses. Never rewrite either input to hide the defaults
mismatch.

## Ownership and finite checks

The only new production module is
`python/vera_timeline_agent/qualification_output_package_v2.py`. It owns the
qualification-only package/profile, independent input pins, the exact R16
diagnostic allowlist, and negative disposition. Existing #209 seams perform
static trust wiring and public dispatch; the installed native boundary admits
only an ordinarily verified synthetic public package. Do not change
`v2_package.py`, compiler behavior, #177 delivery guards, #190 strict readers,
or #214 modules and byte contracts.

Focused checks must prove distinct original/execution hashes, exact R16 delta
reversal, receipt/binding/q/r/sample-grid verification, exact allowlist
matching, and refusal of negative R16 before adapter construction or effects.
Prove the synthetic package passes the existing verifier and is the only
disposition that can enter the native route. Prove existing #177/#190
refusals remain unchanged. No accepted test, fixture, or golden changes.

Preserve #214's bounded output-consistency claim and labels:
`internalControls=unverified`, `geometryStability=not_claimed`,
`controlStability=not_claimed`, `futureAuthority=false`. No claim follows
about hidden processing, complete controls, listening, edit inference, accepted
revision, or rebuilt proof. Follow #211's complete-control refusal: an
unsupported or stale required field remains unavailable and blocks dependent
operations. R16 warnings do not fill that gap.

## Ready ownership and clean recipient

Coordinator preflight found #209 Inbox/unclaimed and canonical dependencies
Closed/Done on 2026-10-16. Proposed Ready routing is exactly `model:sol` and
`effort:high`, one owner/task, dedicated branch
`codex/issue-209-qualification-output`. Claim only after Ready. This plan
does not promote, claim, or dispatch.

Create a fresh clean implementation worktree at exact #214 head above; copy no
untracked handoffs or preparation files from this planning checkout. Verify
the main ancestor, source pins, and clean recipient before edits. Do not
cherry-pick part of #214 or adopt changed composition. PR #216's pending remote
CI is not a passing result or merge authority. If the head is unavailable or
the recipient diverges, stop source adoption and retain the comparison.

## Validation and operator handoff

After claim, run focused checks and the fast gate, obtain independent
implementation review, resolve findings, then complete required local
validation on delivered source. Retain commands, revision, versions, exits,
skips, artifact hashes, and `--durations=25`. This plan and synthetic tests
are not External evidence.

The Studio smoke remains External. Once exact artifact, target, authority,
inventory, and preflight are reviewable, the operator reviews and grants that
exact action through the audited product flow. Complete
`docs/verification/issue-213/parallel-preparation/issue209-operator-handoff-outline.md`
with exact paths and expected observations. No agent-issued confirmation or
reused authority. If controls are unavailable or an effect is uncertain, stop
and preserve the partial state for operator recovery.

After #209 closeout, continue the requested #178 physical matrix, then #215's
separate observation/inference consumer. Neither inherits R16 package success,
hidden-control assurance, or #145 acceptance.
