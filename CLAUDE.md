# Claude Code guide

Read `AGENTS.md`. It applies to Claude exactly as it does to Codex. Then read
`docs/VERIFICATION_POLICY.md` before testing or merging. In short:

For backend issues, follow AGENTS.md's [knowledge reuse rule](docs/RESOLVE_KNOWLEDGE_GUIDE.md).

- Matthew (the Producer) is not a developer. Decide technical matters
  yourself; ask him only about product behaviour, taste, money, his data, or
  steps only he can physically do.
- One issue per `claude/<issue>-<slug>` branch/worktree from freshly fetched
  `origin/main`. Claim it with `npm run roadmap -- claim`. Push early, open a
  draft PR, and keep the branch short-lived. Never work in the main project
  folder; it stays on `main`. "Done" means merged into `main`.
- Locally, run focused tests and `npm run validate:fast`. Never run the full
  `npm run validate` on the Mac. GitHub Actions runs it for every pull request
  except PRs containing only allowlisted plain root/docs Markdown, which run
  `Docs only` (`git diff --check`). Manual dispatch always runs the full suite.
  The required `TypeScript and Python` check confirms the selected PR job passed.
  Pushes to `main` keep the short smoke check.
- For Claude CLI reviews, read and follow `docs/CLAUDE_REVIEW_PLAYBOOK.md`,
  including on in-flight issues. Merge when CI is green; fix later bugs forward.
- Close Automated issues yourself after merging (`npm run roadmap -- complete`).
  Ask Matthew only for Producer (taste or product) judgments, with a short
  checklist.
- The GitHub Project in `.github/vera-roadmap.json` is the live roadmap. Use
  the dependency format and coordination steps in
  `.agents/skills/vera-roadmap-coordination/SKILL.md`.
