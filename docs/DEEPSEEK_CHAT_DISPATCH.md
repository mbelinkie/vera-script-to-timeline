# Chat → GitHub → DeepSeek dispatch (staged; not active)

This is an **add-on to the existing private DeepSeek repair controller**, not a new model agent. See [issue #396](https://github.com/mbelinkie/vera-script-to-timeline/issues/396). ChatGPT can prepare and review a ticket, apply `chat-reviewed` and `deepseek-ready`, and post the exact issue comment `/deepseek dispatch`. A trusted self-hosted GitHub Actions runner can then pass the issue number to the *existing* private controller. Sol retains integration, review, CI/queue and acceptance authority.

**Current status:** the code and tests are on a draft PR only. The Actions workflow is intentionally staged at `deploy/deepseek-dispatch.workflow.yml`, not installed at `.github/workflows/deepseek-dispatch.yml`. No self-hosted runner, private controller adapter, or authenticated Cloudflare Worker has been configured here. No paid DeepSeek execution has been attempted by this implementation.

## Dispatch trust boundary

- `issue_comment` event on `mbelinkie/vera-script-to-timeline`, **not** arbitrary web callbacks; exact comment `/deepseek dispatch`.
- Author must be repository owner or explicitly configured `VERA_DEEPSEEK_ALLOWED_ACTORS` GitHub login (e.g. the actual Chat GitHub app/bot actor once verified from a non-dispatch comment). Never allow `*` or unknown actors.
- Live issue must be open, and have both `chat-reviewed` and `deepseek-ready` labels with no `chat-review-pending` label. A label alone does not start a job.
- Dispatch is fail-closed unless `VERA_DEEPSEEK_DISPATCH_ENABLED=true`. A second replay of the same issue fails before any provider call because a private owner-only receipt already exists.
- The `VERA_DEEPSEEK_TASK_CAP_USD` value is a **per-task upper bound**, additionally constrained by the private **USD10 total cumulative campaign ledger**, including all historical costs, pending/ambiguous reservations and prior #118/#326 work. The dispatcher deliberately **does not** attempt to reconstruct or reset that private ledger. The wrapper must reserve against the same shared ledger *before each call* and refuse if it cannot prove the remaining balance.
- Never send secrets, Producer footage, personal data or unpublished research media to DeepSeek. No other provider, no automatic resubmissions on uncertain outcomes, no changing tests to make a candidate pass.
- GitHub Actions checks out the trusted `main` branch. The runner uses the GitHub token to read issue metadata but never sends that token to the private worker. Never check out or execute issue-provided branches/patches as trusted dispatcher code.
- DeepSeek may prepare only a bounded *candidate*. It cannot merge, close an issue, run paid tests on Resolve, invoke cloud CI or declare external/product acceptance.

## Preparation of each ticket

1. Chat reviews scope, tests, dependencies and current product authority, and preserves the repository's existing review approval process. It adds `chat-reviewed` only after required Producer approval.
2. Add a short **DeepSeek Handoff** section to the issue describing the precise allowed production paths, frozen independent tests, prohibited edits, source/fixture restrictions, controller repair limits and task spend cap. Keep the public issue free of credentials/private data.
3. Apply `deepseek-ready` only when the ticket can be handled by one bounded private worker. Human product/design or native Resolve work stays with its owning agent.
4. Chat posts exactly `/deepseek dispatch` as a separate issue comment. If GitHub exposes a different author for Chat comments, verify its actual login and explicitly add it to the trusted actor list before testing.
5. The existing private wrapper receives `issue_number` and `comment_id`, resolves approved public context and frozen tests, checks private cost/attempt ledger, runs the existing `issue-326/repair-trial/run-repairs.py` mechanism and records a candidate for Sol. This repository does not provide access to that private file and cannot assert its command-line interface.
6. Sol independently reviews and integrates the result in the normal one-issue/one-worktree, PR, Claude review, CI queue and acceptance workflow.

## One-time installation (human-controlled)

1. Keep the repository variable `VERA_DEEPSEEK_DISPATCH_ENABLED=false` until all following steps pass.
2. Install a dedicated **self-hosted macOS runner** with custom label `vera-deepseek`. Restrict access and keep it free of untrusted PR code; do not use a runner that executes arbitrary contributor branches. A Cloudflare Worker cannot itself execute a file that lives on the Mac.
3. Place an owner-owned, executable, non-group/world-writable adapter at `~/.codex/bin/vera-deepseek-runner`. The adapter receives exactly `$1 = issue`, `$2 = comment ID`, plus `VERA_REPOSITORY`, `VERA_DEEPSEEK_TASK_CAP_USD`, `VERA_DEEPSEEK_CAMPAIGN_CAP_USD`, and `VERA_DEEPSEEK_RECEIPT`. It must enforce the shared cumulative ledger, allowed edit/test boundaries, credential handling, no native/full CI effects, and one bounded repair campaign; return nonzero on uncertainty. Do **not** assume the private trial script's CLI until it is inspected. No adapter is bundled or silently installed.
4. Use an authorized GitHub credential to copy `deploy/deepseek-dispatch.workflow.yml` to `.github/workflows/deepseek-dispatch.yml` **through a reviewed PR**, never directly to protected `main`. GitHub workflow changes require a token/App with both **Contents:write and Workflows:write**. The connected GitHub-for-Chat file writer explicitly blocks `.github`; the separate GitHub action available to Chat returned HTTP 403. Cloudflare may hold a narrowly scoped workflow-installer token as a **secret**, never paste it in Chat or issue comments.
5. Set repository variables: `VERA_DEEPSEEK_TASK_CAP_USD=0.25` as an initial per-task cap; `VERA_DEEPSEEK_ALLOWED_ACTORS=` (empty by default; add the verified Chat GitHub actor if needed); `VERA_DEEPSEEK_DRY_RUN=true`; `VERA_DEEPSEEK_DISPATCH_ENABLED=true` only for a verified no-spend test. The USD10 cumulative hard cap lives in the private controller and may have **less than USD10 remaining**.
6. On a dedicated synthetic/open issue, complete review and apply both approval labels, then post the exact command from an authorized actor. Check the Actions run proves correct actor and issue/label gating with **zero paid calls**. Confirm wrong actor, missing label and duplicate delivery all refuse. Verify receipts and ledger outside the public repo.
7. Switch `VERA_DEEPSEEK_DRY_RUN=false` only after the private wrapper and shared ledger were independently verified. Use a low-risk synthetic task with an expressly approved spending cap. Do not reuse the #326 trial or treat its 51/51 as an acceptance test for a different ticket.

## Recovery and disable

- Emergency stop: set `VERA_DEEPSEEK_DISPATCH_ENABLED=false`; additionally disable the self-hosted runner before allowing new jobs to start. Changing a repository variable does not stop an already running private process.
- On timeout/error, the issue-specific private receipt remains **uncertain-or-failed**. Do not delete receipts or replay the issue until a human reconciles the same shared ledger, possible in-flight provider charges and candidate artifacts.
- The dispatch worker does not alter GitHub Project Ready/claim state or auto-close tickets. An issue comment is not permission to bypass original dependencies, review authority or publication holds.
- Cloudflare plugin integration is optional: expose a tightly authenticated `dispatch(issue)` action that applies the existing GitHub authorization, not a separate model controller or a new budget ledger. Let GitHub/your private runner remain the execution source of truth.
