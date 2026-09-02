# Issue 28: offline public-page capture spike

This standalone experiment renders frozen synthetic public pages in Chromium
and publishes immutable local PNG/provenance revisions. It has **no live page
transport**. Public-looking fixture URLs are fulfilled from checked-in bytes;
the browser's operating-system sandbox denies network access independently.

Browser authoring can eventually request these capture mechanics through the
trusted local worker and consume an exact saved revision. This spike supplies
no authoring UI, hosted API, production authorization, or build integration.
The accepted #27 contract remains the authority for that later integration.

## Run

Requirements: macOS, `/usr/bin/sandbox-exec`, `/usr/bin/python3` with standard
`fcntl`, Node **24.19.0**, and npm **11.17.0**. Other OSes fail closed; the full
suite intentionally fails rather than skipping unavailable browser isolation.
The socket-denial test also uses `/usr/local/bin/node` on the tested Mac.

From the repository root with the pinned Node on PATH:

```sh
rtk npm --prefix spikes/public-capture ci --ignore-scripts
rtk proxy node spikes/public-capture/node_modules/playwright/cli.js install --only-shell chromium
rtk npm --prefix spikes/public-capture test
rtk proxy node spikes/public-capture/cli.mjs demo out/issue-28-demo
```

The install command downloads a pinned browser runtime, not webpage content.
If Node 24.19.0 is not on PATH, the verified invocation is
`rtk proxy npm exec --yes --package=node@24.19.0 -- <command>`, for example
`rtk proxy npm exec --yes --package=node@24.19.0 -- npm --prefix spikes/public-capture test`.

`demo` runs initial, unchanged and changed captures using three explicit
command keys. Running it again returns those same three outcomes. `inspect`
verifies PNGs and provenance before listing paths:

```sh
rtk proxy node spikes/public-capture/cli.mjs inspect out/issue-28-demo
rtk proxy node spikes/public-capture/cli.mjs capture out/issue-28-demo my-new-command article-v1
```

Each deliberate recapture needs a new opaque command key. There are no options
for cookies, storage state, browser attachment, profiles, authentication,
arbitrary HTML, a live transport, or production periodic recapture.

## Boundaries and judgment calls

- Each attempt launches a fresh headless Chromium process and non-persistent
  context. It receives an allowlisted environment, a unique private scratch
  directory, no state import, no credentials and no browser extensions.
- macOS forbids reinitializing Seatbelt inside an already sandboxed process.
  Chromium's internal sandbox is therefore disabled; **the outer Seatbelt
  sandbox is mandatory and inherited by every browser child**. The wrapper
  cannot fall back to an unsandboxed executable. It denies network, unrelated
  file contents, arbitrary Mach services and signaling outside its sandbox.
  Only bounded system/runtime reads, private scratch writes, Chromium IPC,
  font/preferences services and a power-state user client are allowed.
  This is a tested local fixture boundary, not a production browser-exploit
  certification or a portable deployment sandbox.
- No real resolver or socket client exists in the fixture transport. Synthetic
  A/AAAA answers and peers exercise policy logic. Receipts explicitly mark
  live DNS, TLS and actual-peer evidence unavailable; `actualConnections` is
  zero. These tests do not prove a future live egress implementation safe.
- URL parsing rejects literal IPs (including alternate numeric spellings),
  ambiguous authorities, local/metadata names, unsupported schemes/ports and
  suspected secrets. Query keys are restricted to short `lang`, `page`, and
  `view` values; even those values are redacted in normal output. Every address
  must be public, and a synthetic peer must belong to the admitted set.
- Redirects are preflighted completely before browser launch. Chromium then
  navigates the resolved fixture URL. Unexpected browser navigation fails;
  subresources use the same guard. Missing/forbidden resources produce visible
  `review_required` warnings, never a fallback network request.
- The fixed profile disables page JavaScript, service workers, frames, forms,
  webfonts, media, downloads, permissions and popups. CSP and request routing
  add defense in depth. No click, login or consent action occurs. Response
  headers are rebuilt; `Set-Cookie` never reaches the browser. A cookie-bearing
  request or nonempty cookie jar fails the attempt.
- `profile.mjs` records all finite limits, including 800×450 at scale 1,
  24 requests, 4 redirects, 256 KiB/response, 1 MiB transferred, 15 seconds
  overall, and a 20-second single-attempt lease with zero retries. Browser RSS
  (768 MiB) and process count (12) are sampled every 100 ms; CPU is limited to
  10 seconds **per process** by the launcher. Sampling can detect overshoot,
  not prevent every transient allocation; this is not a production resource
  isolation guarantee. Frozen HTML and disabled scripts bound this experiment.
- Raster verification checks length, encoding, chunk framing, dimensions,
  CRC and full PNG decode. Only bounded non-interlaced 8-bit RGB(A) is accepted;
  the interlaced decoder's unbounded inflation path is never entered.

The implementation uses Playwright's documented
[non-persistent contexts](https://playwright.dev/docs/api/class-browsercontext),
[request fulfillment and service-worker blocking](https://playwright.dev/docs/network),
and [pinned headless browser runtime](https://playwright.dev/docs/browsers).

## Local publication and recovery

The output directory must be private (`0700`) and owned by the local operator.
It is outside application data and ignored by Git under `out/`. Files are
`0600`; exact URLs are confined to these local restricted receipts. This is
local filesystem confidentiality, not suite project membership enforcement.

```text
capture.json                  immutable local intent
writer.lock                   OS flock; process loss releases it
jobs/<job>/request.json        hashed request and idempotency identity
jobs/<job>/attempt.json        written before browser launch
jobs/<job>/outcome.json        failure/abandonment only
audit/<event>.json             append-only lifecycle/read evidence
staging/<candidate>/           incomplete/quarantined output, never history
commits/<number>-<revision>/
  artifact.png                only when these exact bytes are new
  provenance.json             complete restricted observation receipt
  commit.json                 artifact/provenance hashes and terminal result
```

An OS lock serializes a store's writer. Files and directories are synced before
an atomic same-filesystem directory rename publishes the entire candidate.
The commit includes the terminal job/attempt/lease events and references an
existing verified PNG only when the bytes themselves compare equal. Content
hashes alone do not authorize reuse. All revision numbers are allocated under
the lock, and every committed observation has distinct job/attempt/revision
and provenance identities.

`history()` reads only committed bundles and checks their hashes and PNGs.
It ignores only Finder's `.DS_Store` directory metadata when indexing commits;
any other unexpected commit entry fails closed.
Staging and partial records are never revisions. A repeated command after an
uncertain commit returns the existing result. An interrupted command with no
commit becomes `abandoned_after_process_loss`; it does not launch another
browser. A fresh explicit command may recapture. No committed artifact,
receipt or attempt is overwritten, selected, pruned or deleted. Staging and
private scratch directories are retained for inspection, never reused by
another attempt; Chromium context state is destroyed on process exit. This
spike provides no cleanup/retention-delete command.

These tests cover process crashes, not loss of power, filesystem corruption
recovery or network filesystems. Use a local filesystem. Corruption of committed
bytes/receipts fails closed; it does not rewrite history.

## Producer review

The exact ordered checklist and recorded evidence are in
[`docs/investigations/issue-28-isolated-public-capture.md`](../../docs/investigations/issue-28-isolated-public-capture.md).
Passing tests do not accept the slice. #28 remains In review until the Producer
records acceptance.
