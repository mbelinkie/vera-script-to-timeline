# Claude CLI review: getting adversarial value for few tokens

Applies to step 2 of `docs/VERIFICATION_POLICY.md`: one adversarial Claude
review per code issue. Most review cost comes from three places: how often
you ask, how much context you send, and how much Claude writes back. Cut
those three and leave the adversarial part alone.

## 1. When to review

- **Review once, at the end**, on the final diff against `origin/main`.
  Don't review the plan, intermediate checkpoints or individual commits.
- **Don't loop.** Fix the real findings and merge. Don't send the fix back
  for another full review. Each round turns up narrower edge cases, and the
  value per round drops fast. A string of commits like "bound X", "anchor X
  to Y", "refuse X when Z" on one branch is a sign the loop has gone on too
  long.
- **Delta review only when a fix is big**, meaning a new code path or more
  than about 50 changed lines. Send only `git diff <reviewed-sha>..HEAD`
  plus a one-line list of the findings it addresses. Never re-send the
  whole branch.
- **Leftover edge cases go to new issues** (fix forward), not to more
  review rounds.
- **Skip review entirely** for docs, metadata, roadmap JSON, regenerated
  goldens and lockfiles.

## 2. What to send

- **Pipe the diff in.** Don't ask Claude to explore the repo. With the diff
  on stdin, Claude opens extra files only when it needs surrounding context.
- **Leave noise out of the diff:** lockfiles, generated contracts, goldens
  and fixtures. Exclude them with pathspecs (see the command below). If a
  golden changed, write one line saying so and why.
- **Large diffs (over about 1,500 lines):** send `git diff --stat` plus the
  full diff of the 3–6 riskiest files, and name the rest as "changed, lower
  risk, read if needed".
- **Keep the prompt short, ideally under 15 lines.** Include only:
  1. The issue goal in 1–2 sentences.
  2. What changed and why, in 2–4 bullets.
  3. What you tested and what you could *not* test.
  4. The 2–3 places you are least sure about. This steers the adversarial
     effort to where it pays off.
- **Leave out:** policy recaps, authority and scope paragraphs, branch
  history, earlier verbatim reviews, "do not run Resolve" style
  boilerplate (tool restrictions already enforce that), and whole plan
  documents.

## 3. What to ask for back

Ask for findings only, in a fixed, compact format:

```text
You are an adversarial reviewer. Find defects that would cause wrong
behaviour, data loss, crashes, races, or broken contracts in this diff.
Ignore style, naming, and nits. Before reporting a finding, confirm it by
reading the relevant code; drop anything you cannot tie to a concrete
failing input or sequence.

Output at most 8 findings, most severe first, each as:
[severity: high|medium|low] path:line — defect — concrete failure scenario
— suggested fix (one line)
No preamble, no summary, no praise. If nothing survives, output exactly:
NO FINDINGS
```

The "confirm before reporting" line keeps the review adversarial while
cutting false positives that you would otherwise spend tokens arguing about.

## 4. The command

```bash
BASE=$(git merge-base origin/main HEAD)
{
  cat review-prompt.md
  echo; echo '## Diff'; echo '```diff'
  git diff "$BASE"...HEAD -- . \
    ':!**/package-lock.json' ':!**/uv.lock' ':!**/*.golden*' ':!**/generated/**'
  echo '```'
} | claude -p \
    --model opus --effort high \
    --tools "Read,Grep,Glob" \
    --strict-mcp-config \
    --disable-slash-commands \
    --settings '{"disableAllHooks": true}' \
    --no-session-persistence
```

Why each flag is there:

- `--tools "Read,Grep,Glob"` keeps the review read-only and avoids loading
  every other tool definition. Bash is off on purpose, so Claude cannot run
  `git diff` itself; the diff must arrive on stdin.
- `--strict-mcp-config`, `--disable-slash-commands` and `disableAllHooks`
  stop the Mac's MCP servers, plugins, skills and session-start hooks from
  loading. Measured on 2026-10-20, a trivial prompt cost about 60,000 input
  tokens with the defaults and about 8,000 with these flags, before Claude
  reads a line of the diff.
- `--no-session-persistence`: the review is a one-off.
- **Model and effort:** use `opus` with `--effort high` for concurrency,
  timing, file-system, Resolve-bridge or contract code. Use `sonnet` with
  `--effort medium` for small, contained changes (under about 150 lines,
  one module, well tested).
- Don't use `--bare`. It needs an API key and ignores the subscription
  login.

## 5. After the review

- **Triage the findings yourself.** For each one, either fix it or write a
  one-line reason it is wrong. Don't send rebuttals back to Claude to
  debate.
- **Record the outcome in the PR body** as one short list of findings with
  fixed/rejected and why. Don't commit verbatim reviews or disposition files
  under `docs/`.
- **If the output is `NO FINDINGS`**, say so in the PR and merge when CI is
  green.
