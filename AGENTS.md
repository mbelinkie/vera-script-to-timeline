# Repository agent instructions

These rules supersede older plans and issues. See [D-0018](DECISIONS.md).

## How we work

VERA is a one-person project. Matthew, the Producer, is not a developer.
**Agents decide everything technical; Matthew decides product and taste.**
Move fast, keep `main` green, fix bugs forward.

Ask Matthew only about: product behaviour the spec doesn't settle; taste (look,
sound, timing, wording); money, paid services, credentials; deleting, uploading
or sharing his media or data; steps only he can physically do. Ask plainly,
batched, with a recommended answer. Never ask him to approve
technical things (schemas, contracts, fixtures, goldens, dependencies, tests,
model choice, reviews, merges). Between two reasonable technical options,
pick the more reversible, note it in one PR line, and continue.

If blocked, name the missing capability and smallest action.

## Operating principles

- Use GitHub's features and the simplest workable approach. Avoid unrequested
  checking machinery; keep session docs within budget.
- Before work, answer eight `## Pre-work check` questions: who gains a real
  ability; Matthew/spec quote; simplest version; one-day fit; new checks with
  actual failure and Matthew's yes; visible finish and time budget; a cheap,
  repeatable throwaway Resolve check; at most one open blocker with its own
  human benefit.
- Older issue demands for Test Bench runs, #506 case IDs or the #473/#499
  foundation are void. Real Resolve checks use #520's under-five-minute
  save/close/reopen structural loop, never one-use runs, renders or audio
  comparisons. Stop on uncertain Resolve writes.
- Stop and tell Matthew after a second non-Resolve/non-product failure, a day
  of work, a second child issue, more checking than doing, or any need for
  GUI automation, code signing or a background service.

## Doing an issue

1. **Start.** Matthew's go-ahead is approval. Read the issue and its
   `docs/Script-to-Timeline Product Spec - Fable Rev2.md` slice.
2. **Branch.** One issue per worktree/branch (`codex/<issue>-<slug>` or
   `claude/<issue>-<slug>`) from freshly fetched `origin/main`; bootstrap with
   `npm ci` and `uv sync --frozen`. Never edit the main project folder (it
   stays on `main`). Claim with `npm run roadmap -- claim <issue> --branch
   <branch>` (marks it In progress). Push the first
   commit and open a draft PR targeting `main`.
3. **Build.** Prefer small unit tests; compiler output keeps byte-identical
   goldens (update them in the same PR for intended output changes).
   Change contracts, fixtures and dependencies when needed; say what and
   why in the PR. Fix small things in files you touch; file an Inbox issue for
   anything bigger.
4. **Check locally.** Focused tests, then `npm run validate:fast`. Never run
   the full `npm run validate` on the Mac (1–3 hours); CI runs it.
5. **Review.** For >50 lines of code, money, Matthew's data, Resolve writes or
   concurrency, write brief notes and run `npm run review -- notes.md` once.
   Fix findings; summarize in the PR. If unavailable, say so and continue.
6. **Deliver.** Update the branch from `main`, mark the PR ready, put
   `Closes #<issue>` in the body, and turn on auto-merge:
   `gh pr merge --auto --merge`. It merges once the required
   `TypeScript and Python` check passes. Keep the PR body short: changes,
   testing, choices.

**Done means merged into `main`.** Never end with unpushed work; if you must
stop, push and note what's left in the issue.

## Branch upkeep

- Deploy pilots from a recorded commit on `main`; send pilot fixes through PRs
  to `main`, then advance the deployment.
- By day seven, merge each open PR, split it into a smaller PR, or
  record its blocker, owner and next review date in the PR. Check overdue PRs
  at the next session start. Close superseded or abandoned PRs after
  preserving and linking their unique work.
- After merge, preserve any unique local work, then remove the branch and
  worktree (`npm run cleanup`).

## Acceptance

- **Automatic (default):** anything technical; the merge closes the issue.
- **Real-application check** (Resolve, Fusion, a provider): run it yourself
  where tooling allows; post one short result comment.
- **Producer:** only taste or product behaviour. Finish everything else, give
  Matthew a short checklist (what to open, judge and reply), and leave it
  `In review`.

## If CI fails

On a PR: reproduce locally, fix, push. A red `main` comes
before new work: open a bug and fix forward.
Revert only when `main` is unusable. Never weaken an assertion to get green;
fix or delete a wrong test and say why.

## Hard rules

- `main` only changes through PRs that passed CI; never force-push it.
- No secrets in the repo (it is public).
- Matthew's media and research data are deleted, uploaded or shared only
  through the product's own flows.
- Paid services (e.g. DeepSeek) run only from Matthew's label or request.
- One agent and one job drive Resolve on the Mac at a time.

## Domain notes

- Resolve: prefer its native features; check
  [the Resolve guide](docs/RESOLVE_KNOWLEDGE_GUIDE.md) before a live
  test and test only the open question. Verify real behaviour in the app,
  not in simulation. Update the guide when a finding
  changes.
- Enroll product designs in [#692](https://github.com/mbelinkie/vera-script-to-timeline/issues/692) for
  [shipped verification](docs/CLAUDE_DESIGN_STORY_PLAYBOOK.md#shipped-product-verification). Visual stories must pass the
  [capability-evidence gate](docs/CLAUDE_DESIGN_STORY_PLAYBOOK.md#capability-evidence-before-design)
  first.
- Audio timing review: [the audio timing workflow](docs/AUDIO_TIMING_REVIEW_WORKFLOW.md).
- Mark tests that probe real media, start external processes repeatedly or take
  over ~5 s with `@pytest.mark.slow`.

## Specific workflows

- **"Work on the next prepped ticket":** run `npm run prep -- --next`. For a
  DeepSeek draft, branch from it, review it against the brief and issue, finish
  it, and close its draft PR. For a Codex brief (`codex-prepped`), start
  from `main` and follow its code map and plan, checked against real
  code. See `.github/deepseek/README.md`.
- **Roadmap mechanics** (dependencies, labels): see
  `.agents/skills/vera-roadmap-coordination/SKILL.md`.
- **Codex helpers:** Luna Max subagents (`gpt-6-luna`, `reasoning_effort="max"`)
  may do bounded tasks with explicit file ownership; the parent owns the claim.
  Codex prefixes shell commands with `rtk` (see `~/.codex/RTK.md`).
- **Keeping Matthew informed:** give a rough size up front, warn early if it
  grows, then stay quiet until there's a result or question.
