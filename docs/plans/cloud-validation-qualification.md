# Qualify cloud regression validation for VERA

> **Superseded on 2026-10-16 by [D-0016](../../DECISIONS.md).** A green
> GitHub Actions `Validate` run is now the full regression gate for every
> issue, with no qualification profile, validator run or scope restriction.
> See the [verification policy](../VERIFICATION_POLICY.md). This plan is kept
> as history.

Status: proposed implementation plan, revised after Claude review, 2026-10-12.
Requested by the Producer;
implementation, cloud execution and acceptance substitution are not authorized
by drafting or Claude review. Current [verification policy](../VERIFICATION_POLICY.md)
still requires local full acceptance. This plan changes neither an in-flight
test run nor the #174 → #193 → #191 queue.

## Outcome and bounds

For cloud-qualified tickets, a complete passing GitHub Actions run on the exact
reviewed source can supply full regression evidence without repeating the
whole suite on the Intel Mac. Local focused checks and all required independent
reviews remain. Resolve, private media, platform-specific qualification and
human design/listening judgment remain separate local/External/Producer gates.

Start with the existing standard Ubuntu GitHub Actions job. No AWS account,
paid runners, self-hosted runner, remote desktop, GPU or new evidence platform.
GitHub documents standard hosted runners as free for public repositories; the
existing workflow uses ubuntu-24.04. [Runner documentation](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

Keep this one bounded qualification-and-policy rollout, with a go/no-go after
measurements. Any test optimization, frozen-test change or paid alternative is
a separately scoped proposal, not a prerequisite research program.

## Starting evidence and prerequisites

- Inspected baseline: `origin/main` at `5d59b2ad560aa18f96554b71fe34ee5b7f30dfed`,
  not the older primary checkout. Existing workflow runs the full root gate
  with pinned Node/npm/uv/Python and system FFmpeg, then checks lockfiles.
  [Workflow](https://github.com/mbelinkie/vera-script-to-timeline/blob/5d59b2ad560aa18f96554b71fe34ee5b7f30dfed/.github/workflows/validate.yml).
- [Earlier cloud success](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/38136893433)
  at `894418adc903f46267f561054df758bf3191f3c9` ran from 11:48:10 to 12:23:42
  UTC on Oct 11 (~35:32 elapsed). Newer sampled runs failed within seconds;
  no claim of current full coverage or speedup follows from the older pass.
- #193's workspace-install repair must be accepted and integrated into the
  qualification baseline. Do not bypass it with unlocked installs or changed
  workspace discovery. Confirm clean pinned npm/uv installation from that
  exact baseline as the install stages of the first qualification run; no
  separate duplicate install job is required. The sampled latest failed PR
  run stopped at npm installation, but inspect its exact error before assuming
  #193 resolves every recent failure.
- Select one clean, reviewed calibration commit with its actual test inventory.
  Prefer valid retained local full evidence for equivalent inputs/profile;
  otherwise schedule exactly one local reference run through the existing
  coordinator. Compare collected IDs using cheap collection/list commands;
  they need not trigger another full local run when retained outcomes suffice.
  The cloud work does not need unrelated #174/#191 completion
  unless their changes are included in that selected baseline.
- #184's 50:31 local / ~100-second fast figures establish the motivation, not
  required counts or a same-revision benchmark. [Measured evidence](https://github.com/mbelinkie/vera-script-to-timeline/blob/70e8435de69bee09f2266ca9470dee790be73aae/docs/plans/issue-184-fast-validation.md).

## 1. Define eligibility and coverage

Inventory every gate and consumed input on the calibration commit. Separate:

| Work | Cloud acceptance proposal | Additional evidence retained |
| --- | --- | --- |
| Pure logic, tooling, mechanical metadata/lock changes | Full qualified CI pass can replace local full rerun | Local focused/fast checks; clean install for dependency changes; required review/frozen audit |
| Synthetic media, compiler/goldens, subprocess/recovery | Include in full cloud regression; substitute only where equivalence is demonstrated | Targeted local coverage for affected platform/media behavior |
| Real Resolve APIs, installed-tool qualification, private samples | Cloud suite is regression evidence only | Actual authorized local/runtime evidence and byte/tool identity |
| Design, listening, visible quality | No cloud substitution for human judgment | Explicit Producer acceptance of exact artifact |

Create an explicit check-to-platform exception list, including each local
command and why it is required. No catch-all exemption by issue size/model.
Compare exact collected test identities, parameterization and required
assertions, not counts alone. Missing tools must fail qualification rather
than silently skip; fixture checks already have an FFprobe-missing skip path.
Do not edit accepted tests/assertions/timeouts/fixtures/goldens to achieve parity.

## 2. Minimal workflow/evidence changes

Extend `.github/workflows/validate.yml`, keeping the full command and test
selection intact: `VITEST_MAX_WORKERS=1 npm run validate`. Preserve serial full
Python execution initially; do not introduce test sharding or affected-only
selection in this slice. Add reporting-only durations/JUnit where compatible.

Record actual checked-out commit/tree, PR head and base (if applicable),
workflow version, run/job ID and attempt, command, tool/runner image versions,
FFmpeg/FFprobe build/capabilities, fixture/input and lockfile identities,
completed exit status, test identities/counts/skips, phase durations and logs.
`pull_request` normally tests a merge commit, not merely the PR head. Key
source correspondence to the checked-out tree (`git rev-parse HEAD^{tree}`),
not equality of commit names: a squash/rebase may change SHA while preserving
the exact tree. Compare with the delivered source on the issue's required
integration baseline, which can be a named accepted branch rather than main.
Any tree difference requires the existing evidence-reuse analysis; unexplained
source/base differences need a fresh run. A green badge labelled with a head
SHA is insufficient. [GitHub event/trust behavior](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target).

Record a qualified digest set for the workflow, validation command definitions,
runner/test/reporter configuration and any evidence helper. Changes to those
control surfaces cannot self-certify substitution with a green run produced by
their own changed gate: use the local path and separately approve/requalify
the affected profile. Dependency changes still require their clean install
and full run; do not accidentally exempt changed validation scripts in a
package manifest. Independent code/test review and frozen audits remain.

Read authoritative run/job conclusion, attempt, event and source identifiers
from the GitHub API, verifying job steps and actual checkout correspondence.
The uploaded manifest supplies tool/input/inventory details, not authority to
declare its own run successful. Reporter options must produce the same
collected IDs with and without reporting. A preflight requires FFmpeg/FFprobe;
the report validator rejects every unqualified skip outside frozen tests.

Keep read-only repository permissions, pinned action revisions, ordinary
push/pull_request trust boundaries and no new provider secrets. Publish only
allowlisted test reports and sanitized logs with normal workflow artifacts;
never upload worktree roots, private preparation folders, audio/transcripts,
environment dumps or caches containing private samples. Do not re-upload raw
job logs; retain their GitHub links/digests and only the manifest and relevant
test reports after checking for accidental sensitive content. Public-repository
artifacts/logs must be treated as public. [Artifact access](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts).

Retain reports even on failure without allowing upload success to overwrite the
test exit result. Dependency caches accelerate installs, not proof reuse.
Archive the small profile/acceptance manifest, tested tree, run URL/attempt,
report/log digests and safe coverage/skip summary durably with the issue or
its existing verification folder before cloud artifacts expire. A digest alone
cannot reconstruct the reviewed inventory/profile. Use repository
retention limits, never delete existing evidence. [Artifact retention](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/remove-workflow-artifacts).

Don't generate duplicate full jobs just because both branch push and PR events
fire. Prefer the PR integration tree for ticket acceptance; a branch without
a PR can use its push run. Either suppress the redundant feature-branch push
job using read-only PR lookup or record which run is authoritative without
adding unsafe event privileges. Preserve required post-merge integration
checks; they aren't another owner-local full run. Superseded runs may be cancelled only
for the same branch/PR after identifying that their revision is obsolete;
they remain cancelled/non-passing evidence. Independent tickets need not share
the Intel-Mac lock. Do not weaken branch protections to avoid duplicate work.

## 3. Qualify correctness, reliability and runtime

Run the full workflow once on the fixed reviewed calibration source, then one
repeat on the same source/profile to check execution reliability. Reuse valid
existing runs if their complete provenance meets these requirements. Keep the
current 90-minute job limit initially. Measure setup, queue and test time
separately, including largest Python cases. These two calibration runs are
one-time qualification, not two full runs per future ticket.

Accept qualification only when:

- Both complete full runs pass with the required inventory and no unexplained
  skip, missing report, cancellation or timeout. Failures remain failures.
- A later green attempt on the same tree does not erase an earlier unexplained
  failure. Retain every attempt and its disposition; diagnose test versus
  infrastructure failures under the existing failure/flake policy. Neither
  "latest is green" nor silent retries resolve an unexplained failure.
- Local/cloud comparison confirms unchanged test/fixture/golden content and
  generated currentness. Deterministic contract/golden bytes must match.
  Existing passing byte-golden assertions on unchanged goldens can establish
  this without a second output-generation/diff pipeline.
  Platform-specific media bytes need their recorded semantic measurements and
  tool qualification, not a false assertion of identical encoder outputs.
- Differences in tools/codecs/native libraries, CPU architecture, paths,
  filesystem behavior and timing are classified; each unresolved difference
  has an explicit local check or blocks the relevant substitution category.
  Cloud green cannot certify the Mac's #174 tool fingerprint or Resolve runtime.
- Every report can be tied to the actual tested source/config/inputs and
  delivered revision. Use the existing evidence-reuse comparison rules;
  a subsequent merge/base change cannot reuse an unrelated candidate pass.
- Report end-to-end latency and projected local minutes avoided. No arbitrary
  speedup gate: freeing the Mac is useful even if cloud duration is similar.
  If 90 minutes is exceeded, retain the failure and propose a bounded outer-job
  budget/performance adjustment; do not relax frozen child/test deadlines.

The qualified profile includes actual FFmpeg/FFprobe binary/build-capability
fingerprints and runner OS/image/architecture provenance. An unqualified
media-tool change suspends substitution for media-sensitive checks, not unrelated
pure logic whose required runtime remains covered. Runner label/architecture,
language runtime or control-file changes suspend the affected profile until
accepted requalification. Hosted image maintenance is not permission to reuse
a stale fingerprint; record changes and apply explicit profile exceptions.

Add cheap tests for any new evidence-validation helper: reject a stale tree,
wrong attempt/job, incomplete coverage, skipped required tests, nonzero exit,
changed controls/profile/inputs, unresolved previous failures and malformed
evidence. Read-only GitHub responses are data, not commands to execute. Do not
build a generalized evidence SDK.

## 4. Conditional rollout after acceptance

Deliver a short go/no-go report and exact eligible/local-exception list. Obtain
Producer approval to activate that scope of cloud substitution. Then amend
`docs/VERIFICATION_POLICY.md`, repository AGENTS/CLAUDE coordination pointers,
dispatch prompts and reusable operating playbook together. Until activation,
the current local-full policy applies; qualification is not implicit acceptance.

Future eligible owner flow: focused/fast local checks → required review/fixes →
push an authorized reviewed candidate → full qualified CI evidence → verify
source correspondence and all additional gates → close using its existing
Automated/External/Producer authority. A local full duplicate is not required
for covered checks. Real local integration and subjective gates remain intact.

Use the complete relevant run, not an old unrelated success or a still-running
job. New source/test/config/dependency/input changes need a new CI pass;
proven non-consumed evidence-only changes can reuse it. Any qualification drift
or missing proof fails closed to the existing local path without manufacturing
a pass. Do not interrupt #174's current gate for this proposed rollout.

## Implementation ownership, acceptance and exclusions

Expected touched surfaces: workflow and minimal evidence collection/checking,
qualification report, verification/coordination/launch documentation. No
product code, schemas, generated types, accepted tests or fixtures/goldens.
Any necessary frozen change is separately approved and scoped.

Objective completion: clean pinned installs, two valid qualification passes,
exact coverage comparison, evidence-helper regression tests (if one is added),
generated/frozen/diff checks, required review and a concrete eligibility result.
Producer decision is only the policy activation/exception scope—not manually
repeating test runs or reviewing a huge log. No claimed savings without data.

Unresolved decisions: media-tool pinning/qualification profile on Ubuntu,
which specific platform-sensitive checks remain local, and artifact retention
within account limits (with the small durable archive required regardless).
Candidate/merge correspondence is governed by the tested-tree rule above. Resolve these
inside the bounded qualification; stop affected rollout rather than expanding
into AWS, licensing, cloud Resolve setup or a testing-platform rewrite.

## Producer activation checklist

1. Read the one-page go/no-go summary: eligible ticket types, mandatory local
   exceptions, measured runtime, both exact run links, tested tree, qualified
   control/tool profile and skip allowlist. Expected: each
   required gate has a named home and complete evidence.
2. Confirm no private media/provider access or paid infrastructure is included.
3. Respond: “Approve cloud full-suite substitution for the qualified scope
   at COMMIT, with the listed local exceptions,” or name the disputed exception.

This document alone does not create a ticket, launch implementation, push code,
run a cloud job, upload an artifact or change repository settings.

## Claude review and incorporated changes

Consulted Claude Code via existing account, requested `opus` / high; reported
`claude-opus-5-5`, session `ed7a84f4-650b-4447-aca2-5b011264aa03`, 2026-10-12.
Tool access disabled; the draft and public-source references were supplied as
data. Claude did not inspect code, browse, run tests or implement the plan.
Verdict on the original draft: approve the direction, revise before implementation.

| Finding | Revision |
| --- | --- |
| Candidate/merge ambiguity | Tested tree plus runtime/input equivalence; bind to actual required delivery baseline, not automatically main |
| Changed gate could self-certify | Qualified control digests, authoritative GitHub job facts, local fallback and accepted requalification |
| A green retry could hide failure | Keep attempt history; resolve earlier unexplained failures before substitution |
| Unqualified media-tool drift | Explicit fingerprints and category-scoped suspension |
| Frozen skip paths could omit coverage | Tool preflight and report-level skip validation, without editing accepted assertions |

Adopted simplifications: install readiness inside the first calibration run,
cheap inventory comparison and retained local outcomes, existing byte-golden
assertions rather than duplicate generation, normal GitHub logs rather than
re-uploaded raw logs, and a small durable evidence archive. Retained privacy
review and profile data: no private samples does not prove no accidental leak,
and hashes alone cannot reconstruct expired evidence. Preserved explicit
integration gates instead of declaring post-merge checks unnecessary.

The revisions above are the steward's incorporation of the review, not a claim
that Claude issued a new PASS on the revised text or that qualification passed.
