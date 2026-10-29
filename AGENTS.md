# Repository Agent Instructions

These instructions apply to the whole repository and to every agent: Codex,
Claude and their helpers. They were rewritten on 2026-10-16 at the Producer's
direction ([D-0016](DECISIONS.md)). Where an older plan, issue or historical
record asks for more process, this file and
[the verification policy](docs/VERIFICATION_POLICY.md) win.

## How we work

VERA is a one-person project. Matthew, the Producer, is not a developer and is
not on a team that needs enterprise-grade controls. Move fast. Bugs get fixed
later in their own issues. **Agents lead every technical decision; Matthew
decides product and taste.**

### Ask Matthew only about

- **Product behaviour.** What VERA should do, or how a workflow should feel,
  when the spec does not settle it and the choice changes what he will see or
  use.
- **Taste.** Look, sound, timing, on-screen wording: anything judged by
  watching or listening, usually in Resolve.
- **Real-world consequences.** Spending money, new paid services or accounts,
  credentials, and deleting, uploading or sharing his media or data.
- **Hands-on steps only he can do.** For example, signing in or approving an
  OS permission prompt that the available tools cannot handle.

Ask in plain language, give a recommended default, and batch questions so he
gets as few interruptions as possible.

Perform authorized mechanical steps yourself: stage/install files, run commands,
launch apps and execute checks through available tools. Use a wizard only for
genuinely human-only actions, then resume the automated work. An existing
helper's prompt or TTY requirement is not itself a reason to delegate the work.
If blocked, name the actual missing capability and ask for the smallest action;
preserve data-safety limits and never fabricate human authorization.

**Never ask him to approve:** schemas, contracts, sidecars, fixtures, goldens,
helper code, dependencies, test changes, model routing, review waivers, test
queues, evidence or merges.

### Decide everything technical yourself

When two technical readings are reasonable, pick the more reversible one, note
the choice in one line in the PR, and keep going.

## Starting an issue

- Read the issue on the GitHub Project configured in
  `.github/vera-roadmap.json`, the relevant slice of
  `docs/Script-to-Timeline Product Spec - Fable Rev2.md`, and the relevant plan
  if there is one. `docs/IMPLEMENTATION_PROGRESS.md` is a historical record,
  not a tracker.
- Work on one issue in one dedicated branch/worktree (`codex/<issue>-<slug>` or
  `claude/<issue>-<slug>`) created from a freshly fetched `origin/main`.
  Bootstrap a new worktree with `npm ci` and `uv sync --frozen`.
- Claim it with `npm run roadmap -- claim <issue> --model <model> --effort
  <effort> --task <task> --branch <branch>`. If the issue clearly needs a
  different model or effort, relabel it (`gh issue edit`), say so in a comment
  and continue; don't park it waiting for a steward.
- Record prerequisites under `## Dependencies` as one `- Blocked by #123` (or
  `- Blocked by owner/repo#123`) line each, or `None`. The roadmap tooling reads
  this format. Promote with `npm run roadmap -- ready <issue>`.
- Small, low-risk fixes you find in the files you are already touching: just
  do them and mention them. Anything bigger: file an Inbox issue and keep
  going.
- When a clearly adopted future requirement has no issue yet, add an Inbox
  placeholder so the roadmap and progress dashboard show the known scope.

## Building

- Prefer small unit tests over end-to-end tests. Compiler-touching work keeps
  byte-identical golden tests. Mark slow tests as the verification policy
  describes.
- Contracts (`/contracts`), fixtures, goldens and earlier acceptance tests may
  change when the work needs it. Regenerate types, update affected tests, and
  explain the change in the PR description: what changed, why, and what it
  affects. No separate change note or approval is needed.
- Adding a dependency is fine; give a one-line reason in the PR.
- Do feasibility checks against the real application early when an
  external-application assumption could sink a design. Simulated tests do not
  prove what Resolve can do.
- Prefer Resolve's native capabilities over custom reimplementations. Check
  the installed edition/version and supported automation/import route first;
  verify the needed behavior in the real application, including save/reopen.
  Build a custom fallback only for a demonstrated gap and explain that gap.
- Before starting a backend issue, consult the relevant [Resolve knowledge guide](docs/RESOLVE_KNOWLEDGE_GUIDE.md)
  entries and reuse their supported conclusions. Before a live Resolve test, cite
  finding IDs and the unanswered question, changed assumption or affected regression;
  test only that delta. Current target authorization, freshness and integrity checks
  still apply. Update or supersede material findings/corrections in the same PR with
  evidence and tested conditions. If no entry applies, record the new question;
  if no knowledge changed, no new entry is needed. A new ticket or version alone
  calls for assessment, not wholesale requalification.
- Anything irreversible in the real world (deleting, uploading or sharing the
  Producer's media or the research project's data) happens only through the
  product's own flows, never as an agent side effect.

## Testing, review and merging

Follow [docs/VERIFICATION_POLICY.md](docs/VERIFICATION_POLICY.md):

- Before operating, changing, or activating the GitHub CI queue, follow
  [docs/CI_QUEUE.md](docs/CI_QUEUE.md) for its activation state, commands,
  fail-stop behavior, and recovery.

- Fast and focused checks run locally.
- Before any Claude CLI review, read and follow
  [docs/CLAUDE_REVIEW_PLAYBOOK.md](docs/CLAUDE_REVIEW_PLAYBOOK.md).
  It governs current and future issues, including those with older review instructions.
- The full suite runs only in GitHub Actions; never run it on the Mac.
- Merge when CI is green.
- Fix bugs forward.

## Branches: everything lands on `main`

`main` on GitHub is the only place work counts. On 2026-10-16, several issues
were marked done while their code existed only in local worktrees, and 38
branches held work that never reached `main`. Don't let that happen again:

- **Push early.** Push your branch to GitHub as soon as it has a commit, and
  open a draft PR. Work that exists only on the Mac is one disk failure from
  gone.
- **Every change goes through a PR into `main`,** including docs, rules and
  process changes. Don't edit or commit in the main project folder. It stays
  on `main` and is only ever pulled, so every new worktree and agent reads the
  same rules.
- **Keep branches short-lived.** Merge within the issue. Before merging, bring
  the branch up to date with `main` (merge or rebase) so CI tests what will
  actually land. If an issue stalls, open a smaller PR for what's finished
  rather than letting the branch drift.
- **Don't end a task with uncommitted or unpushed work.** If you must stop,
  commit, push, and say in the issue what's left.
- **"Done" means merged into `main`.** A passing test run on a branch that
  isn't merged is not delivery. Evidence-only closure is not allowed.
- After merging, delete the branch and remove its worktree.

## Closing an issue

The Project's `Acceptance` field says who closes it. In every case the work
must already be merged into `main`:

- **Automated** (the default): when the PR is merged and CI is green, close it
  yourself with `npm run roadmap -- complete <issue> --accepted-by Automated
  --evidence <PR link>`.
- **External**: real application or service evidence is needed. Run the check
  yourself where the tooling allows, post the result as one comment and close.
  Ask Matthew only for steps he must physically do.
- **Producer**: reserved for taste or product judgment. Finish everything
  else first, then give him a short checklist: what to open, what to look or
  listen for, and exactly what to reply. Leave it `In review` until he
  answers.

Use a separate design-first issue only when the design is a product or taste
choice. For technical design, decide and build in the same issue.

## Helpers

- Use Luna Max subagents (`gpt-6-luna`, `reasoning_effort="max"`) for bounded
  implementation, tests, inspection and documentation. Standing authorization;
  no route selection needed.
- Give each helper a coherent task, explicit file ownership, minimal fresh
  context (`fork_turns="none"`) and constraints. Helpers share the checkout:
  preserve others' edits. The parent owns integration and the claim.

## Keeping Matthew informed

At the start, give a rough size. Tell him promptly if the work turns out much
bigger than expected, why, and a sensible way to split it. Otherwise stay quiet
until there is a result or a question that needs him.

## Specific workflows

- Every visual design story must pass the capability-evidence gate in
  [docs/CLAUDE_DESIGN_STORY_PLAYBOOK.md](docs/CLAUDE_DESIGN_STORY_PLAYBOOK.md#capability-evidence-before-design)
  before feature design or Claude edits; missing feasibility is a design blocker.
- Manual audio timing or human-verified word boundaries: follow
  [docs/AUDIO_TIMING_REVIEW_WORKFLOW.md](docs/AUDIO_TIMING_REVIEW_WORKFLOW.md),
  which prepares machine timing and a prefilled Audition marker file so
  Matthew only corrects.

## Producer learning channel

- Keep implementation, roadmap and review tasks focused. Do not put teaching
  asides in their commentary or final responses.
- When a completed milestone, important trade-off, surprising failure or useful
  test reveals a genuinely helpful technical lesson, send the context to the
  Codex task **VERA Engineering Lessons**
  (`threadId: 01a0627e-a2ea-7ab1-8975-9a85c5e8b4e9`, `hostId: local`) with
  `send_message_to_thread`. Send source material, not a finished lecture:
  named libraries/tools and their roles, exact source paths or commit links,
  the source issue, and actual outcomes with limitations. The lessons task
  owns its current teaching brief and selects useful five-minute, tool-focused
  explanations for a non-engineer. Keep private workplace context and mappings
  in that task, never in this repository, GitHub, CI or reviewer inputs. At most
  one handoff per meaningful milestone; skip forced or repetitive ones.

## Shell commands

Codex sessions prefix shell commands with `rtk`, following
`/Users/matthewbelinkie/.codex/RTK.md`:

```sh
rtk git status
rtk npm run validate:fast
rtk uv run pytest tests/test_example.py
```
