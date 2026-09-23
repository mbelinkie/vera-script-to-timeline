# External Resolve Free Codex handoff

Use this procedure when a VERA issue must run against the isolated Resolve Free
installation on the dedicated external startup disk. It applies only after
issue #134 is accepted and Done.

The handoff boundary is the GitHub issue plus committed repository state.
OpenAI distinguishes an agent session from the environment that supplies its
files and commands, and Codex asks the operator to choose the host, workspace,
branch, and worktree before a new task begins. Do not assume an internal task
will rebind itself to the external filesystem after a reboot; a subagent also
shares its parent's host. Start the issue's one implementation task from
ChatGPT/Codex **after booting the external macOS**. See OpenAI's
[environment architecture](https://developers.openai.com/api/docs/guides/agents-api/architecture)
and [host/workspace guidance](https://developers.openai.com/blog/mastering-codex-remote-for-engineering).

## Eligibility gate

Hand off an issue only when all of these are true:

- #134 is closed and Done, so the external macOS, Resolve Free installation,
  test-only account, test root, and return-to-Studio check have accepted
  evidence.
- The target issue is Ready, every dependency is closed and Done, its
  acceptance criteria are complete, and it has exactly one `model:*` and one
  `effort:*` label.
- The target issue has no active claim. An issue already claimed by an
  internal task needs steward resolution; a second task must not claim or work
  it.
- The whole issue can be completed from the external checkout. Split mixed
  internal/external work into separate issues before either issue becomes
  Ready.
- Every prerequisite change is available from the repository's agreed shared
  base. The handoff must not depend on an uncommitted internal worktree, an
  internal-only branch, or files copied from the Studio account.
- The external account can launch ChatGPT/Codex, access the repository, and
  run the repo's pinned toolchain. `rtk`, Node/npm, uv/Python, and any
  issue-specific media tools must resolve before the issue is claimed.

If any gate fails, leave the target issue unclaimed and report the failed gate.

## Originating-agent handoff packet

The originating agent prepares the following durable packet, then stops. It
does not create an internal implementation task for the target issue.

```text
External execution request

Issue: #<number> — <exact title and URL>
Required environment: separately booted VERA Resolve Free macOS
Routing: <exact model label> / <exact effort label>
Acceptance authority: <Automated | External | Producer>
Shared base: <branch or full commit SHA available to the external clone>
Required inputs: <repo-relative paths and hashes, when relevant>
Resolve actions: <ordered manual actions and expected results>
Evidence destination: <repo-relative evidence document or issue comment>
Explicit exclusions: <issue-specific boundaries>
```

Keep the packet public-safe: no credentials, serials, personal paths, private
screenshots, source-media contents, or Studio project details.

## Start the external task

1. Shut down and boot the dedicated external macOS. Sign in to its test-only
   local account.
2. Confirm the active startup system is on the external physical device and
   record only public-safe facts: external connection, macOS version/build,
   Resolve Free edition/version, free capacity, and the Git commit used. Stop
   if the startup system or Resolve edition is wrong.
3. Launch ChatGPT/Codex from that external macOS and open the clean VERA clone
   under the external test root. Confirm the checkout and all issue inputs are
   on the external disk; do not open or copy the internal Studio checkout,
   projects, databases, media, caches, preferences, or credentials.
4. Choose the external host and workspace before the first prompt, then create
   exactly one Codex task for the issue using its exact routed model and
   effort. The Producer may explicitly invoke `$vera-roadmap-dispatch` while
   booted externally, or start the named issue directly in the external saved
   project.
5. In the new task, read `AGENTS.md`, inspect the issue with
   `rtk npm run roadmap -- inspect <issue>`, read the authoritative product-spec
   slice and relevant plan, and re-check every eligibility gate.
6. Claim only from that external task, using its actual task ID and dedicated
   `codex/` branch:

   ```sh
   rtk npm run roadmap -- claim <issue> \
     --model <exact-model> \
     --effort <exact-effort> \
     --task <external-task-id> \
     --branch <codex/issue-branch>
   ```

The claim is the completion criterion for the handoff. Until it succeeds, no
implementation or Resolve acceptance work begins.

## Work and evidence boundary

- Keep the checkout, generated packages, disposable media, Resolve libraries,
  cache/proxy, gallery, renders, and evidence under the external test root.
- Run automated checks before the Resolve step and retain the exact command,
  result, relevant versions, and artifact hashes required by the issue.
- Resolve Free cannot be queried through the supported external scripting API.
  The Producer performs the issue's named Resolve UI actions while the agent
  supplies the ordered checklist and records the reported result. UI
  automation and undocumented project-file editing are not substitutes for
  Free acceptance.
- Record only the observations required by the issue. Crop or omit any image
  that would expose personal data, unrelated projects, serials, credentials,
  or source-media contents.
- Treat a boot, edition, path, or data-isolation discrepancy as a stop gate.
  Preserve the evidence, mark or file the appropriate roadmap item, and do not
  improvise with the internal Studio environment.

## Finish before leaving the external system

1. Commit the issue's authorized repository changes and retain its external
   evidence. Make the branch available through the approved repository
   workflow only when that workflow is part of the task's authorization.
2. Re-run the issue's required checks from the external checkout.
3. Move the issue to In review with a concise evidence summary:

   ```sh
   rtk npm run roadmap -- review <issue> --evidence '<public-safe summary>'
   ```

4. Close only with the authority named by the Project. External acceptance
   requires retained real-Resolve evidence; Producer acceptance requires the
   Producer's explicit acceptance response.
5. Persist every fact needed for continuation in Git or the issue before
   rebooting. Reopening a session from another installation is not evidence
   that its local filesystem, tools, or running applications moved with it.
6. Follow the shutdown, disk-removal, internal-Studio return check, and eventual
   T2 restoration procedure in
   `docs/verification/issue-134-resolve-free-environment.md`.

## Failure cases

- **Issue was claimed internally:** stop; do not create an external duplicate.
  Ask the roadmap steward to resolve ownership or split the work.
- **Required input exists only internally:** stop; put it through the issue's
  approved, reviewable handoff route before retrying.
- **External tooling is incomplete:** stop before claim and finish environment
  provisioning as separate operations work.
- **Resolve reports Studio or the wrong version:** stop and preserve the
  version evidence; no Free acceptance is valid in that session.
- **A test needs Studio data:** stop and file a bounded Inbox issue. The
  isolated Free environment never opens or copies that data.
