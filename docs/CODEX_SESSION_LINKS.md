# #399 — local Codex session links (draft; no dispatch or approval)

This module is a **read-only link-data contract**, not a working dashboard button or Codex agent control surface. The existing `codex://threads/<uuid>` navigation test has already succeeded on macOS. Do not repeat it or run `codex queue` for this feature.

## Local identity and trusted capture

Codex desktop **Copy chat deep link** on an *existing local conversation* supplies a `codex://threads/<uuid>` value. Manually associate the copied link with the exact GitHub issue URL, recording which Producer made that association and when. This is **human-attested provenance**, not cryptographic authentication or evidence of current availability. Never infer UUIDs from ChatGPT `/c/` IDs, review-prompt links, cloud task IDs, issue numbers, PR numbers, filenames, or the most recently opened thread.

The proposed map is a version-1 JSON file **outside the repository** at `~/Library/Application Support/VERA/codex-thread-map.v1.json`. Keep the enclosing directory owner-only (0700), the file owner-only (0600), and never commit it or send its real contents to GitHub. Any local registration UI/tool must write by atomic replacement, preserve historical associations, and require a separate explicit Producer confirmation for the issue/session pairing. **Registration is not implemented in this draft.**

Example **fixture only**; UUID and dates are fictional, and `installationId` must match an independently configured ID for this Mac:

```json
{
  "version": 1,
  "installationId": "example-mac-installation",
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

The calling integration must obtain this Mac's `installationId` **independently**, not from the map itself, and pass it to `linksForIssue(issueUrl, snapshot, installationId)`. A copied map from another machine must fail closed. If there are multiple threads for one issue, mark older records `secondary` or `history` and explicitly select **one** primary; never silently choose the newest.

## Inert interface for #401

- `parseLocalCodexLink(raw)`: exact existing-local UUID link syntax only; never accepts `new`, query strings, encoded paths or web URLs.
- `canonicalIssueKey(url)`: lowercased `owner/repo#number` key (not issue number alone).
- `loadLocalCodexSessionMap(path?)`: read-only loader; missing file returns an empty map, bad schema/permissions return an error state; no network or model calls.
- `linksForIssue(issueUrl, snapshot, installationId)`: status, safe GitHub issue URL, optional separately verified browser conversation URL, and **app URL only when a single primary Codex-local thread has explicit Producer provenance and the device matches**.
- The `verified-local` status means **recorded Producer-confirmed association**, not live thread loaded, active agent, task approval, or CI eligibility. Display `lastConfirmedAt` and don't assert availability was recently checked.

Browser fallback is **independent**: accept only a separately Producer-confirmed existing `https://chatgpt.com/c/<opaque-id>` URL. Review links (`/?prompt=`) start a new review; shared snapshots (`/share/`) are not a resumable thread and may expose private details. If no real browser conversation exists, keep the **GitHub issue** link and copyable Codex app link with protocol-handler guidance, but do not label the issue link “Open same thread in browser.”

**#401 owns the integration**, including its renderer, dashboard entry point, queue display, HTML escaping, and localhost smoke tests. This branch must not edit `scripts/project-progress-lib.mjs`, `scripts/project-progress.test.mjs`, `Open VERA Progress.command`, or `scripts/project-progress.mjs`. The helper should be loaded once while producing the snapshot, not called from the browser or from `GET /status`.

**#398 is separate**: CI callbacks and same-thread resumption require independent authorization, testing, outbox and acknowledgement semantics. Nothing here queues/resumes a Codex task, changes GitHub Projects, declares a ticket approved, or consumes model credits.

Local standalone test: `node --test scripts/codex-session-links.test.mjs`. This draft intentionally does not create a real mapping file or wire a dashboard action.
