# Verification policy

The working rules live in [AGENTS.md](../AGENTS.md) (simplified on 2026-11-04,
[D-0018](../DECISIONS.md)). In short:

- **Locally:** focused tests, then `npm run validate:fast`. Never the full
  suite on the Mac.
- **CI:** every PR and every push to `main` runs the full `npm run validate`
  equivalent in GitHub Actions, split across parallel free runners. PRs that
  change only allowlisted Markdown take the fast `Docs only` route. The
  required check is `TypeScript and Python`.
- **Review:** one `npm run review` for code over ~50 lines or touching risky
  areas; fix real findings; no review loops.
- **Merge:** auto-merge when the required check passes. If `main` goes red,
  fix forward first.
- **Evidence:** the PR (diff, short description, CI result), plus one comment
  for real-application checks. Nothing else: no receipts, hash bundles,
  approval records or evidence manifests.
