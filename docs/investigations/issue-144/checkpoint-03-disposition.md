# Checkpoint 3 disposition and completed local build segment

Direct Claude CLI review completed successfully: version 2.1.235, configured
default `claude-sonnet-5`, high effort, 42 turns, session
`aff5f779-4771-4c18-b547-67b6e85a25bb`, no permission denials. Available tools were
Read/Grep/Glob only, plan permissions, no Chrome/MCP/plugin/custom hooks. It read
the repository but ran no tests or native action. Full response is retained in
`claude-checkpoint-03-verbatim.md`. This is review, not acceptance.

- Compiler corrections: reviewer found them sufficient; no new JS parser.
- Finite JSON: stdlib `parse_float` plus `math.isfinite` now refuses numeric
  overflow such as 1e400, alongside duplicate-key/BOM/NaN/Infinity checks. No
  custom tokenizer or dependency. Tests cover each; the plan names the mechanism.
- Host stage API mapping: no plan blocker; implemented the five actual core
  stages below. Native injection/recovery remains a separate next segment. Core receipts have server-assigned local_prepared evidence; requested lane is separate proofLane, so an input cannot label local checks as native evidence.
- Composition: reviewer accepted the qualified compiler/segment-map seam. No
  implementation or positive composition claim yet.
- Future readiness: reviewer found no invented #148/#145 authorization. Missing
  real narration/timing remains a named future blocker, not silent acceptance.
- Calibration: reviewer correctly asked for near-boundary tests. Its summary
  mistakenly calls our adversarial half-word overlay full-word; the measurement
  script/report bind the exact half/quarter support indices. Added head/tail,
  frame-boundary and quiet overlay probes. These reveal that tiny/quiet residue
  can pass a numerical tolerance. Therefore do not freeze this as a general
  speech-absence classifier. The completed measurements and bounded gate
  qualification require further review before a positive omission gate.
- Recovery API qualification: Claude mentions GetSubFolderList/GetClipList
  from the media-pool preflight. Those are not sufficient evidence for a project
  manager folder walk. Verify the actual project-manager APIs before implementing
  tree recovery; unresolved response remains waiting, never automatic retry.

## Finished segment: prepared local build

`python/vera_timeline_agent/roundtrip_build.py` uses four literal operator files:
proof-request, script-document, compiler-dependencies and materialization-plan.
The issue-owned request pins evidence level and package verifiedAt. Narration
materialization artifactId must equal its dependency assetId. Origin media is
local, independent and hash-bound. Speech checks original block text/revision,
audio hash, actual PCM24 mono 48k extent and complete dependencies. It never
imports a synthesis provider; media only verifies local inputs.

Pinned Node/Python check and strict parsing precede job/snapshot publication.
Inputs are copied unchanged into immutable, hash-derived run directories. All
five core stages run through unchanged #35 jobs: speech/media verification,
actual #144 compiler entry (unchanged core), actual #34 package writer and actual
package verifier. Compiler manifest/report bytes remain exact. Intermediate
input/output changes, original input/media changes and package discrepancies
refuse. Completed replay reuses the same job and package. Render/upload stages
are explicitly skipped. The Studio stages wait with an explicit #145 message;
there is no default native factory and no native intent/effect.

Build/manifest/report IDs currently come from the literal pinned dependency input.
The later canonical revision preparation must generate fresh input-derived IDs
before rebuild; do not reuse the original target's names on a new revision.

Test-first: initial collection failed before the module existed. First green
attempt exposed a wrong new-test assumption: #35 retains render/upload rows as
skipped, rather than omitting them. Corrected the new test without touching core
or accepted tests. Initial combined run: 35 passed (12 new + 23 accepted package/
Studio/job regressions). Two intermediate-tamper tests plus four stale/ambiguous prepared binding cases then added: 18 new pass.
Focused Ruff format/check and strict mypy pass; protected diff versus 9c8973d is
empty and `git diff --check` passes. Full validation remains outstanding.

CLI for this segment:
`uv run --frozen python -m vera_timeline_agent.roundtrip_build --proof-root <dir> --node-executable <pinned-node>`.
It returns exit2/status waiting after verified core work, deliberately before
native assembly. This is a building block, not the finished #144 runbook.

## Re-estimate

The first actual compiler/package stage test is now retained. Planning range:
**8–16 remaining active-work hours**, excluding Producer waits and later #148/#145
work. Outstanding: bounded semantic mappings/explicit decisions and canonical
revision, qualified program gate/splice, WI observation/link/render, guarded
injected assembly/recovery, baseline promotion, integrated tests and complete
runbook/validation. This is an estimate, not an acceptance forecast; revise if
the audio/recovery review reveals a required design change. Scope is unchanged.
