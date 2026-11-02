# #399 — local Codex session links (draft; no dispatch or approval)

This draft supplies a **local-only, Producer-attested issue-to-existing-thread mapping** and an **inert read-only link-data contract**. The `codex://threads/<uuid>` navigation test has already succeeded on the Producer's Mac. Do not repeat that test, start a Codex agent, or run `codex queue` for this feature.

## No-credit Producer confirmation (after separate #399 approval)

1. In the **already-existing local Codex desktop conversation**, use **Copy chat deep link**. Do not launch a new thread or inspect private Codex databases. Its exact shape must be `codex://threads/<uuid>`; a ChatGPT web `/c/` ID, `codex://threads/new`, cloud-task ID, Share snapshot, or review prompt is not a local thread.
2. From the VERA repo checkout that contains the implementation, run **interactively**:

   ```bash
   node scripts/codex-session-register.mjs https://github.com/mbelinkie/vera-script-to-timeline/issues/399
   ```

   Paste the copied desktop deep link **at the interactive prompt, not as a shell argument**, and read the shown canonical issue key and redacted thread suffix. Type `CONFIRM <owner/repo#issue>` exactly. If a different current primary exists, it is **not** silently replaced; a separate `REPLACE` confirmation archives the old association as history. Canceling, invalid input, or a corrupt/insecure existing map fails closed. Terminal input is local but the pasted deep link can remain visible in terminal scrollback; avoid uploading terminal transcripts or screenshots.
3. Registration creates **no Codex model turns and makes no network/GitHub changes**. It writes only local private files and represents **human attestation** that this specific copied existing thread belongs to the chosen issue; it does **not** independently prove the app currently has that thread loaded. No real session metadata should be committed to the repo.

The private root is `~/Library/Application Support/VERA/` (owner-only mode 0700), containing `codex-thread-map.v1.json` and a separate `codex-installation-id.v1` (owner-only mode 0600). The independent installation identity is generated randomly, retained locally, and **must not** be derived from a copied map. Each map change is an atomic rename, protected by an owner-only `.lock` file to fail rather than race on simultaneous registrations. A stale lock needs manual inspection; do not automatically delete/override it. Never commit these files, including the installation ID, to GitHub. No migration or background collector is implemented.

## Illustrative private schema

Example **fixture only**; UUID and dates are fictional:

```json
{
  "version": 1,
  "installationId": "12345678-1234-1234-1234-123456789abc",
  "mappings": [
    {
      "issueUrl": "https://github.com/mbelinkie/vera-script-to-timeline/issues/399",
      "surface": "codex-local",
      "role": "primary",
      "deepLink": "codex://threads/12345678-1234-1234-1234-123456789abc",
      "provenance": {
        "method": "desktop-copy-deeplink",
        "confirmedBy": "producer",
        "capturedAt": "2026-11-01T20:00:00Z"
      },
      "verification": {
        "state": "producer-confirmed-existing",
        "checkedAt": "2026-11-01T20:00:00Z"
      }
    }
  ]
}
```

Canonical identity is `owner/repo#number`; two repositories' issue #399 are distinct. A session can be shared across issues, and an issue can retain multiple historical sessions, but only **one explicit primary** may supply a desktop app link. A disagreement is `ambiguous`, not newest-wins.

## Read-only #401 integration interface (not yet wired)

- `parseLocalCodexLink(raw)`: accepts exact UUID-form `codex://threads/<uuid>` only (UUID version is not assumed).
- `canonicalIssueKey(url)`: canonical GitHub owner/repo/issue identity.
- `loadLocalCodexSessionMap(path?)`: read-only map snapshot; absent returns empty, bad schema/permissions produce error.
- `readLocalInstallationId(path?)` from `scripts/codex-session-register-lib.mjs`: independently reads the private installation identity, returns null if missing or invalid; never creates it.
- `linksForIssue(issueUrl, snapshot, installationId)`: returns a status/reason, GitHub issue URL, optional independently Producer-confirmed browser conversation URL, and **`appUrl` only for one properly confirmed primary local Codex UUID on this installation**. `verified-local` describes a **recorded Producer association**, not live availability, Codex readiness/claim, current review approval, or CI status.

Suggested #401-only data flow at snapshot generation: load the local mapping and independent installation ID once; pass these inputs into the link helper keyed by canonical issue URL; render app links only for `verified-local`, with escaped URLs and an optional **Copy desktop link** fallback for browsers blocking custom protocols. All missing/invalid/cloud/web/stale/ambiguous/wrong-device states get a truthful disabled explanation and keep the GitHub issue link. **No navigation on page load, render or refresh.**

A browser fallback is a **different evidence category**. A known existing `https://chatgpt.com/c/<opaque-id>` conversation may be shown for a `chatgpt-web` mapping with independent Producer confirmation (`browserProvenance.method: "producer-confirmed-existing"`, timestamp). For a `codex-local` mapping, even an independently verified web conversation URL **must not** be called an alternative for that same thread unless the Producer separately confirms the equivalence with `browserProvenance.relation: "same-thread"`. The registration CLI never invents this relationship, so local Codex-only records normally have **no same-thread browser fallback**; retain the GitHub issue link as a separately labeled alternative. Codex-cloud records have no Codex desktop link or browser-session fallback in v1. A `/?prompt=` URL opens a *new review*, not that conversation; a `/share/` URL is a static snapshot, not a live same-thread fallback. Do not label a GitHub issue URL “Open same Codex thread in browser.”

**#401 exclusively owns renderer integration** (`scripts/project-progress-lib.mjs`, `scripts/project-progress.test.mjs`, `Open VERA Progress.command`, dashboard entry point), snapshot freshness, DOM ordering, and actual localhost smoke tests. This draft changes none of those.

**#398 is a separate project** about CI callback/agent resume and requires distinct approval, a durable outbox and acknowledgment evidence. This draft contains no Codex launch/resume, no background polling, no CI mutation, no GitHub issue status changes, and no credit-consuming operations.

## Tests

```bash
node --test scripts/codex-session-links.test.mjs scripts/codex-session-register.test.mjs
```

Tests cover local/deep-link identity, malformed URL/encoding, cross-repo keys, web/cloud/unknown links, file permissions, cancellation, explicit confirmation, local installation scoping, corrupt maps, atomic registration and history, and registration locking. They use temporary fictional test files only. Tests do **not** prove actual Mac dashboard integration or the existence of any specific private Codex thread.
