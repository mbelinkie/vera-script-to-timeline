# Issue 28 — isolated public-page capture evidence and producer review

Status: awaiting Producer acceptance. Authority: issue #28 and producer-accepted
#27 contract, merged in baseline `12c262c`. This implements the isolated local
spike only; the product's authoring integration and live transport remain later
slices. Production periodic recapture stays deferred.

## What to review

`spikes/public-capture/` is a standalone package with an offline fixture
transport, a fresh sandboxed Chromium per attempt, complete restricted receipts,
verified raster output and immutable local publication. No root contracts,
fixtures, goldens, accepted tests, generated types or production dependencies
change. The full boundary and limits are in its `README.md` and `profile.mjs`.

The central #27 rule is preserved: **unchanged successful recapture still
creates a new revision**. Only the raster bytes are reused. Failed admission,
browser/decoder failure, lease expiry and partial publication create no
revision. New results remain unselected, and nothing deletes prior history.

## Automated and visual evidence

Verified on macOS 15.1 / x64 with Node 24.19.0, npm 11.17.0, Playwright 1.62.1,
Chromium 151.0.7922.34 and pngjs 7.0.0:

- Final focused verification after the Finder-metadata regression fix:
  **20 tests passed, zero skipped**. The repository
  gate `rtk proxy npm exec --yes --package=node@24.19.0 -- npm run validate`
  also passed: generated contracts current; TypeScript lint/typecheck;
  91 contract tests, 1 tooling test, 6 progress tests and 23 roadmap tests;
  Ruff/format; strict mypy across 51 source files; and 173 Python tests.
  A fresh worktree initially lacked root npm dependencies; installing the
  existing lockfile with `npm ci --ignore-scripts` resolved that setup failure.
- `rtk proxy npm exec --yes --package=node@24.19.0 -- npm --prefix spikes/public-capture test`
  runs the focused policy, transport, store, actual-browser and crash suites.
  The browser suite is mandatory, not skipped on a missing runtime/sandbox.
  `history()` ignores only `.DS_Store` in the commits index, so inspecting the
  output with Finder does not create a false invalid revision; the regression
  is covered by the store tests.
- URL/address tests cover unsafe schemes, alternate IP spellings, reserved
  IPv4/IPv6 classes, metadata/local hosts, mixed DNS, peer mismatch, unsafe
  redirect chains, redirect loops and finite request/byte limits.
- Actual Chromium captures confirm fresh context IDs, zero initial/final
  cookies, no imported state, unchanged-byte reuse, changed-byte revisions and
  review-required blocked resources. The hostile fixture includes a script
  cookie setter; an injected `Set-Cookie` response is also suppressed.
- The actual OS sandbox denies reading an unrelated synthetic sentinel file
  and denies both an outbound loopback socket and an inbound listener in the
  kernel. No test contacts a real private service or real webpage.
- Publication tests kill Node with SIGKILL at eight points (after job-directory
  creation but before its request record, after admission,
  before browser, after browser, after PNG staging, after provenance staging,
  before publication, after publication). Recovery returns exactly the old
  complete history or the new complete bundle, with no partial revision. The
  baseline PNG/receipt hashes remain unchanged. Lock release, lease expiry,
  staging corruption, invalid PNG/CRC/dimensions/encoding, missing provenance,
  browser failure and retained-artifact corruption also fail closed.
- The generated local demo was visually inspected: revision 1 shows a teal
  42 cm bulletin, revision 2 reuses that exact PNG, and revision 3 shows a
  longer orange 63 cm bar. No text is clipped. The images are synthetic fixtures,
  not captures of live third-party content.

Observed demo PNG SHA-256 values on this runtime:

| Revision | Change signal | SHA-256 |
| --- | --- | --- |
| 1 | `initial_observation` | `5a8e880becb39b2722c8193408ba91869131c3aec47ae7f2c8c43b482d938543` |
| 2 | `same_exact_bytes` | `5a8e880becb39b2722c8193408ba91869131c3aec47ae7f2c8c43b482d938543` |
| 3 | `different_exact_bytes` | `ad23ac1f22a7c151030572fced47ff7aa37c6532b4f5526e38a414a2c97dc799` |

These are retained observations, not new frozen goldens or a promise that other
OS/font/browser versions render identical pixels. Provenance reports actual
runtime and synthetic network evidence honestly. The test suite checks exact
equality for recaptures under the same runtime.

## Producer acceptance checklist

Use the dedicated issue #28 branch/worktree. Run commands from its repository
root with Node 24.19.0 on PATH, or use the pinned `npm exec` prefix documented
above. Choose a fresh output directory if the example name already contains a
previous review; do not remove or overwrite that review.

1. **Install and capture the first fixture.**

   ```sh
   rtk npm --prefix spikes/public-capture ci --ignore-scripts
   rtk proxy node spikes/public-capture/node_modules/playwright/cli.js install --only-shell chromium
   rtk proxy node spikes/public-capture/cli.mjs capture out/issue-28-review first article-v1
   rtk proxy node spikes/public-capture/cli.mjs inspect out/issue-28-review
   ```

   Expected: one `ready` revision, `initial_observation`, zero actual
   connections and `importedState: false`. Open the printed `artifact` path:
   it shows the teal 42 cm bulletin. Open `restrictedReceipt`: inspect identity,
   authorization, request/profile, network, runtime, timing, output, warnings,
   lease and change fields. Exact URLs are restricted local metadata; DNS/peer
   values are explicitly synthetic and no production authorization is claimed.

2. **Recapture unchanged input.**

   ```sh
   rtk proxy node spikes/public-capture/cli.mjs capture out/issue-28-review unchanged article-v1
   rtk proxy node spikes/public-capture/cli.mjs inspect out/issue-28-review
   ```

   Expected: two distinct revision and attempt IDs. Revision 2 says
   `same_exact_bytes`, uses the same PNG path/hash, and has its own provenance
   file, timestamp and clean browser context. Both remain unselected.

3. **Recapture changed input, then repeat its command.**

   ```sh
   rtk proxy node spikes/public-capture/cli.mjs capture out/issue-28-review changed article-v2
   rtk proxy node spikes/public-capture/cli.mjs capture out/issue-28-review changed article-v2
   rtk proxy node spikes/public-capture/cli.mjs inspect out/issue-28-review
   ```

   Expected: exactly three revisions. Revision 3 says `different_exact_bytes`
   and its new PNG shows an orange 63 cm bar. The repeated command returns
   `duplicate: true` and the same revision ID. Reopen revision 1: its teal
   bulletin and receipt are unchanged. Stored integrity is checked by inspect;
   automated tests additionally compare all prior bytes before/after recapture.

4. **Reject a private URL before browser execution.**

   ```sh
   rtk proxy node spikes/public-capture/cli.mjs capture out/issue-28-review unsafe article-v1 http://127.0.0.1/
   rtk proxy node spikes/public-capture/cli.mjs inspect out/issue-28-review
   ```

   Expected: the first command exits 1 with `ip_literal_denied`,
   `navigationStarted: false` and no revision ID. History still contains
   exactly three revisions. This input is rejected without contacting loopback.

5. **Run the isolation/security/fault checks.**

   ```sh
   rtk npm --prefix spikes/public-capture test
   ```

   Expected: all tests pass, including the real Chromium tests, OS sandbox
   denial probes and SIGKILL recovery test. Review `browser.mjs` and the README:
   there is no browser attachment/profile/cookie import. Chromium's internal
   sandbox is disabled because macOS forbids nested initialization; every child
   inherits the mandatory outer Seatbelt sandbox. The suite never reaches a
   live webpage. The fixed profile is deliberately restrictive; this is not a
   production egress or general browser compatibility certification.

6. **Record the producer judgment on issue #28.**

   If these mechanics and stated spike limitations are acceptable, reply:
   `Accepted issue #28 isolated public-page capture spike.`

   Otherwise reply:
   `Issue #28 acceptance failed at step <number>: <first mismatch>.`

The issue stays **In review** until that response. No browser-authoring UI,
live capture, periodic schedule, OCR, build integration or deletion is accepted
implicitly by accepting this spike.
