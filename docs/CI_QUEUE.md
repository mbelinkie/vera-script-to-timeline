# GitHub CI queue

## Status

The queue is **active**. Its control issue is [#361](https://github.com/mbelinkie/vera-script-to-timeline/issues/361),
its durable state is `queue.json` on `vera-ci-queue-state`, and
`VERA_CI_QUEUE_ENABLED` is `true`. Strict main protection requires the queue
status, including for admins.

The bounded live proof passed on 2026-10-29: docs-only and full validation,
protected automatic merges, serial smoke handoffs, persistent failure pause,
rejected repeated attempt, retained waiting work, and explicit repaired-head
recovery. All four synthetic PRs were delivered and the queue became empty
and unpaused. See [the actual service results](ci-queue-service-proof.md).

After local checks, required review and acceptance prerequisites are complete,
post `/queue ready <PR> <40-character-head-SHA>` as one comment on the control
issue. A draft can use `/queue validate` without authorizing merge. Delivery
finishes only after main smoke succeeds; issue closure remains with its owner.

## Why the project uses an Actions controller

GitHub's native merge queue is available for public repositories owned by an
organization and private repositories owned by organizations on Enterprise
Cloud. This public personal-account repository does not meet that eligibility
rule. GitHub's queue also removes a PR whose group fails, rebuilds the following
group without it, and continues when that group passes; it does not stop the
whole queue on a failure. [GitHub merge queue eligibility and behavior](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)

Mergify has useful batching and manual pause controls, but its normal failure
behavior also continues the queue: a single failed PR leaves the queue, while
a failed batch is split to isolate the failing PR and process the others. Setting
`batch_max_failure_resolution_attempts: 0` removes the failed batch; it does not
pause all later entries. Pausing Mergify is an explicit operator action.
[Mergify batch failures](https://docs.mergify.com/merge-queue/batches/) ·
[Mergify queue pause](https://docs.mergify.com/merge-queue/pause/)

The chosen controller uses this repository's GitHub Actions and a scoped
`GITHUB_TOKEN`. It needs no third-party queue service, account, personal access
token, app key, or other credential. The controller workflow runs trusted code
from the default branch; the separately dispatched `Validate` workflow checks
the exact candidate with `contents: read` and checkout credentials disabled.
Its final completion job runs on a separate runner, checks out only trusted
default-branch code, and receives the controller's write permissions. Candidate
jobs never receive those permissions. Both controller entry points share one
concurrency group for durable state updates, with `queue: max` so ordinary
pending events do not replace the completion job. GitHub permits up to 100
pending jobs or runs in this group; overflow or a canceled completion requires
explicit inspection and reconciliation. [GitHub concurrency behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)

## Required status and workflow behavior

The required queue context is **`VERA queue validation`**. The controller posts
this as a commit status on the exact candidate SHA after it finds one successful
validation run. The `Validate` workflow's own `workflow_dispatch` job check does
not appear as a PR check or satisfy a required PR status, even when it tests the
same SHA. [GitHub required-check behavior](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks) ·
[GitHub commit-status API](https://docs.github.com/en/rest/commits/statuses)

The controller verifies strict protection using effective active rules from
the metadata-readable [rules for a branch API](https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch).
The classic protection endpoint requires administration access unavailable to
`GITHUB_TOKEN`.

When activating the queue, create an active repository ruleset that targets
only `main`, requires strict status checks for `VERA queue validation`, and has
no bypass actors. Its `required_status_checks` rule sets
`strict_required_status_checks_policy: true`. If classic branch protection is
retained, it must require the same context and include administrators. Allow
merge commits. Do not require
both `VERA queue validation` and `TypeScript and Python`: dispatch-created job
checks cannot satisfy the latter on a PR. Keep the `TypeScript and Python` job
in `Validate` for the inactive PR path and manual fallback. When the queue is
disabled, switch the required context in the ruleset and any retained classic
protection back to `TypeScript and Python` before resuming manual delivery.

GitHub normally suppresses follow-on workflow runs for events caused by
`GITHUB_TOKEN`; `workflow_dispatch` and `repository_dispatch` are exceptions.
The queue explicitly dispatches validation and post-merge smoke runs. The live
rollout also observed no completion event from bot-dispatched validation, so
delivery uses a trusted final job instead of depending on that event. The job
reads the exact run and completed gate jobs through GitHub's API, verifies their
identity and outcome, then reconciles once. It uses no timer or polling loop.
The enclosing validation run keeps the global slot until the final job exits;
a newly dispatched smoke or candidate waits for that slot. A human-driven
merge still uses the existing `push` smoke. [GitHub workflow
trigger rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)

`Validate` has three dispatch modes:

- `manual` always runs the full gate on the selected ref.
- `pr` checks the exact candidate and base SHAs. Trusted classification selects
  either `Docs only` or the full `TypeScript and Python` gate.
- `smoke` runs the focused post-merge smoke on the exact main SHA.

Queue run names include the transaction, mode, candidate SHA, and base SHA.
The controller accepts results only when the workflow identity, run title,
candidate, base, and completed gate jobs match its saved transaction. One global
`vera-validation-slot` serializes manual, push, and dispatched validation while
the queue is enabled. While disabled, the workflow keeps its original per-PR
and per-event/SHA concurrency keys. Enabled-queue PR publications have no jobs
and use their own concurrency key, so branch backups cannot replace a pending
queue validation or smoke. The enabled validation slot also uses `queue: max`,
so a manual run cannot replace the pending queue smoke or candidate while its
predecessor's completion job exits. The disabled legacy path keeps its original
single-pending behavior and PR cancellation. Missing or ambiguous expected runs
pause the queue instead of being inferred; the same 100-pending limit applies.
Run-history reconciliation is capped at 100 pages; exhausting that bound also
pauses for explicit maintenance rather than treating unread history as passing.

## Control issue and commands

Create one public, dedicated, open issue for queue commands. Use a neutral title
and body with no GitHub auto-close phrase. Queue comments and run URLs are public.
Post each command as the entire body of one comment on that issue. The controller
accepts commands only from collaborators with `write`, `maintain`, or `admin`
permission.

| Command | Effect |
| --- | --- |
| `/queue ready <PR> <40-character-head-SHA>` | Attests that the exact open, non-draft PR is ready for automated merge after queue validation. |
| `/queue validate <PR> <40-character-head-SHA>` | Runs validation for an open PR, including a draft, and grants no merge readiness. |
| `/queue remove <PR>` | Removes a waiting entry. An active entry cannot be removed. |
| `/queue pause` | Pauses queue advancement and retains entries. An already dispatched validation continues to its result. |
| `/queue resume` | Explicitly resumes after the cause is understood and the controller confirms there is no active validation run and protection is correct. |
| `/queue recover <40-character-main-SHA>` | After a delivered merge and fix-forward repair, explicitly runs smoke on the named current main before releasing waiting entries. |
| `/queue inspect` | Reports pause state, active PR/phase, waiting entries, and the durable state file. |

PRs must target `main` from a branch in this repository. Fork PRs are not
accepted. `ready` requires the submitted SHA to equal the current head and
rejects draft PRs. Before posting `ready`, complete and record the local focused
checks and `npm run validate:fast`, the required Claude CLI review, and every
pre-merge application or acceptance check for the issue. The command is an
explicit readiness attestation; it does not replace that evidence. `/queue
validate` accepts draft PRs and never grants readiness.
Its result uses the non-required `VERA preview validation` status. Only a ready
entry that passes the final protection, closure, and identity checks receives
the merge-required success status. Dispatched validation does not restore or
save npm/uv caches in main's cache scope.

For `ready` entries, the controller checks the PR title, body, commit messages,
and sidebar closing links to keep issue closure with its owner. If the PR branch is behind
`main`, it integrates the captured base into the PR branch, verifies the
resulting commit identity, and records that candidate before validation. Any
author push, draft-state change, or base movement invalidates the recorded
readiness and pauses delivery until the owner attests to the current SHA again.

The controller never creates or closes roadmap issues and never starts a Codex
task. Queue delivery merges the PR only after the status passes and the saved
base and head still match. It then dispatches smoke on the merge SHA. A PR is
delivered only after that smoke succeeds; issue acceptance and closure remain
with the issue owner and its acceptance field.

## Fail-stop and recovery

The controller handles `issue_comment`, PR head/state changes, completed
human-started `Validate` workflows, and the trusted completion job in dispatched
queue validation and smoke. It has no schedule, background polling loop, or Codex
chat wakeup. GitHub issue comments and Actions notifications are the notification
path. Use `/queue inspect` or a manual reconcile when an event needs
reconciliation:

```sh
gh workflow run ci-queue.yml -f action=reconcile
```

Any non-success, timeout, unexpected failed `Validate` run, stale head/base,
missing result, or ambiguous run identity pauses advancement
and preserves waiting entries. A validation failure does not merge the PR. A
smoke failure happens after the PR has landed; the controller holds later entries
and retries smoke for that same merge SHA only after explicit `/queue resume`
and confirmation that `main` has not moved. Fix delivered code forward through
another PR when required; the queue does not revert commits automatically.
For that repair, use the manual fallback below while queue intake stays paused.
After the repair PR and its checks have passed, restore queue protection and
enablement, then post `/queue recover <exact-current-main-SHA>`. This preserves
the original delivered merge and requires a new smoke success on the repaired
main before later entries advance.
A successful manual validation already in the shared slot hands back through
its completion event; waiting entries need no resume command for that case.

For a failed pre-merge candidate, inspect the run and current PR/base first. If
the author pushed a new head, post a fresh `/queue ready` for that SHA after the
readiness work is complete. If duplicate or mismatched runs made the result
ambiguous, let them finish and inspect all of them; while paused and idle,
reassert readiness for the exact current head to create a fresh transaction,
then explicitly resume. Never treat an ambiguous result as passing.

An active entry cannot be removed. For a closed failed PR, resolve the active
transaction through explicit resume so it is no longer active, remove the
waiting entry, then resume the queue. Preserve the `vera-ci-queue-state` branch
and its `queue.json`; it is the durable record of commands and transaction
identity.

## Activation and bounded rollout proof

Initial activation requires one coordinated, human-supervised GitHub Actions
window. The controller initializes paused; keep intake limited to synthetic
rollout candidates until this proof is complete:

1. Merge the controller and validation workflows to `main`. Create the
   dedicated public control issue described above.
2. Configure an active repository ruleset targeting only `main`, with strict
   `VERA queue validation` required and no bypass actors. If classic branch
   protection is retained, require that same context and include administrators.
   Allow merge commits. Verify the expected status source is GitHub Actions
   where GitHub offers source selection.
3. Initialize the durable state once from `main` using the control issue number:

   ```sh
   gh workflow run ci-queue.yml -f action=init -f control_issue=<issue-number>
   ```

   Initialization creates `queue.json` on `vera-ci-queue-state` and leaves the
   queue paused. Inspect the control issue before continuing.
4. Set repository variable `VERA_CI_QUEUE_ENABLED` to `true`, then explicitly
   `/queue resume` on the control issue. Keep intake limited to the synthetic
   rollout PRs until each item below is observed.
   Before enabling, finish all legacy PR validations. The active queue ignores
   ordinary PR publication runs because its workflow disables all their jobs.
5. Prove both classifier routes and serial delivery with two harmless,
   first-party synthetic PRs: one docs-only PR and one source/test PR. Confirm
   each run uses the exact candidate/base and the intended route, the required
   status is attached to that candidate, only one delivery is active at a time,
   post-merge smoke passes, and no issue is closed.
6. With another synthetic PR waiting, produce a controlled validation failure.
   Confirm the queue pauses, no waiting PR merges, and entries remain visible.
   Exercise a duplicate or mismatched run identity and confirm it is rejected
   and pauses the queue. Resolve the ambiguity, explicitly reattest the current
   head if needed, resume, and confirm delivery resumes only after the exact
   successful validation and smoke.
7. Record the observed PRs, SHAs, run URLs, check source, pause cause, recovery,
   and smoke result on the rollout issue. Keep rollout acceptance open until
   this external GitHub behavior is proven; unit tests alone do not establish
   it.

This initial proof is complete; [observed results](ci-queue-service-proof.md)
record the candidates, validation routes, smoke, failure and recovery. For a
future rollout, coordinate its validation window with the Producer.

## Disabling the queue

1. Post `/queue pause` and let any active `Validate` run finish. Inspect the
   active transaction and preserve state.
2. Set `VERA_CI_QUEUE_ENABLED` to `false`. Ordinary PR classification and
   validation resume.
3. Switch the ruleset and any retained classic branch protection back to the
   required `TypeScript and Python` context. Keep merge commits allowed.
4. Run `Validate` manually with mode `manual` for a forced full gate. Also wait
   for a fresh ordinary `pull_request` validation on the current head: the
   manual dispatch check does not satisfy the PR's required status. A reviewed
   repair push or reopening the unmerged PR triggers that ordinary validation;
   changing the enablement variable alone does not trigger it.
5. Merge manually only when branch protection accepts the current head status;
   if using the merge API, pass that exact head SHA. Confirm the resulting
   `Main smoke` is green before declaring manual delivery complete.

Keep the state branch while an active transaction remains. Never bypass required
checks to disable the queue.
