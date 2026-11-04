# Repository agent instructions

For every agent (Codex, Claude and helpers). Simplified on 2026-11-04
([D-0018](DECISIONS.md)). Where an older plan, issue or record asks for more
process, this file wins.

## How we work

VERA is a one-person project. Matthew, the Producer, is not a developer.
**Agents decide everything technical; Matthew decides product and taste.**
Move fast, keep `main` green, fix bugs forward.

Ask Matthew only about: product behaviour the spec doesn't settle; taste (look,
sound, timing, wording); money, paid services, credentials; deleting, uploading
or sharing his media or data; steps only he can physically do. Ask in plain
language, with a recommended answer, batched. Never ask him to approve
technical things (schemas, contracts, fixtures, goldens, dependencies, tests,
model choice, reviews, merges). When two technical options are reasonable,
pick the more reversible one, note it in one PR line, and continue.

Do mechanical steps yourself. If blocked, name the missing capability and ask
for the smallest action.

## Operating principles

- Use GitHub's built-in features before building our own.
- Build the simplest thing that works. If infrastructure or tooling work runs
  past about a day, stop and check with Matthew.
- Don't add gates, approval steps, receipts or required reading unless Matthew
  asks. Every rule here names the real risk it prevents; prefer deleting
  process to adding it.
- Keep this file and the other session docs short; a test enforces a word
  budget.

## Doing an issue

1. **Start.** Matthew's go-ahead in any form ("work on #123", "next prepped
   ticket", an issue in `Ready`) is the approval. Read the issue and the
   relevant slice of `docs/Script-to-Timeline Product Spec - Fable Rev2.md`.
   Run `npm run cleanup` to remove merged worktrees.
2. **Branch.** One issue per worktree/branch (`codex/<issue>-<slug>` or
   `claude/<issue>-<slug>`) from freshly fetched `origin/main`; bootstrap with
   `npm ci` and `uv sync --frozen`. Never edit the main project folder; it
   stays on `main`. Claim with `npm run roadmap -- claim <issue> --branch
   <branch>` (marks it In progress so two agents don't collide). Push early and
   open a draft PR.
3. **Build.** Prefer small unit tests; compiler output keeps byte-identical
   goldens (update them in the same PR when output changes on purpose).
   Contracts, fixtures and dependencies may change when needed: say what and
   why in the PR. Small fixes in files you're touching: just do them. Anything
   bigger: file an Inbox issue.
4. **Check locally.** Focused tests, then `npm run validate:fast`. Never run
   the full `npm run validate` on the Mac (1–3 hours); CI runs it.
5. **Review.** For code changes over ~50 lines, or any change touching money,
   Matthew's data, Resolve writes or concurrency, write 5–10 lines of notes and
   run `npm run review -- notes.md` once. Fix real findings; list them as
   fixed/rejected in the PR. No second full round. If the CLI is unavailable,
   say so and continue.
6. **Deliver.** Mark the PR ready, put `Closes #<issue>` in the body, and turn
   on auto-merge: `gh pr merge --auto --merge`. It merges when the required
   `TypeScript and Python` check passes, the issue closes itself, and your job
   is done. Keep the PR body short: what changed, how it was tested, choices
   made.

**Done means merged into `main`.** Don't end a task with unpushed work; if you
must stop, push and say what's left in the issue.

## Acceptance

- **Automatic (default):** anything technical. The merge closes the issue.
- **Real-application check** (Resolve, Fusion, a provider): run it yourself
  where tooling allows; post one short result comment.
- **Producer:** only taste or product behaviour. Finish everything else, then
  give Matthew a short checklist (what to open, what to judge, what to reply)
  and leave it `In review`.

## If CI fails

On a PR: reproduce the failing tests locally, fix, push. If `main` goes red
after a merge, fixing it comes before new work: open a bug and fix forward.
Revert only when `main` is unusable. Never weaken an assertion to get green;
fix or delete a wrong test and say why.

## Hard rules

- `main` only changes through PRs that passed CI; never force-push it.
- No secrets in the repo (it is public).
- Deleting, uploading or sharing Matthew's media or the research data happens
  only through the product's own flows, never as an agent side effect.
- Paid services (e.g. DeepSeek) run only from Matthew's label or request.
- Only one agent drives Resolve on the Mac at a time.

## Domain notes

- Resolve: prefer its native features; check
  [the Resolve knowledge guide](docs/RESOLVE_KNOWLEDGE_GUIDE.md) before a live
  test and test only the open question. Verify real behaviour (including
  save/reopen) in the app; simulated tests don't prove what Resolve can do.
  Update the guide when a finding changes.
- Visual design stories must pass the
  [capability-evidence gate](docs/CLAUDE_DESIGN_STORY_PLAYBOOK.md#capability-evidence-before-design)
  first.
- Audio timing review: [the audio timing workflow](docs/AUDIO_TIMING_REVIEW_WORKFLOW.md).
- Mark tests that probe real media, start external processes repeatedly or take
  more than ~5 s with `@pytest.mark.slow`.

## Specific workflows

- **"Work on the next prepped ticket":** run `npm run prep -- --next`. Start
  your branch from the DeepSeek branch it names, review the draft against the
  brief and issue, finish it, deliver as usual, and close DeepSeek's draft PR.
  See `.github/deepseek/README.md`.
- **Roadmap mechanics** (dependencies, labels): see
  `.agents/skills/vera-roadmap-coordination/SKILL.md`.
- **Codex helpers:** Luna Max subagents (`gpt-6-luna`, `reasoning_effort="max"`)
  may do bounded tasks with explicit file ownership; the parent owns the claim.
  Codex prefixes shell commands with `rtk` (see `~/.codex/RTK.md`).
- **Keeping Matthew informed:** give a rough size at the start; tell him early
  if it's much bigger than expected; otherwise stay quiet until there's a
  result or a question.
