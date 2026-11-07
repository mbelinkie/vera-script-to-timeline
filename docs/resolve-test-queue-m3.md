# M3 — Finite guarded native campaigns and private mobile monitor

Issue [#448](https://github.com/mbelinkie/vera-script-to-timeline/issues/448)
layers a deterministic serial campaign coordinator on the existing
[M1 queue](resolve-test-queue-m1.md) and
[M2 authenticated native adapter](resolve-test-queue-m2.md). A campaign may
contain **one or more** cases; 100 cases / 200 trials are **upper bounds**, not
required test counts. The monitor is optional. Neither the monitor nor the
submitter supervises Resolve or calls the native adapter.

## Prerequisites and local installation

Use the same user-private queue root and bootstrapped checkout as M1/M2
(`uv sync --frozen`, matching `.venv` interpreter). All commands below run **on
the Mac** in the issue-owned checkout; set `QUEUE` to the existing private
queue root if nondefault:

```sh
export QUEUE="$HOME/Library/Application Support/VERA/resolve-test-queue"
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign \
  --root "$QUEUE" install-launchd
```

This opts into `org.vera.resolve-test-campaign-worker.m3`, one finite worker
tick every 30 seconds. It is **separate from** the original
`org.vera.resolve-test-queue.m1` (mock/individual native jobs) and the HTTP
monitor. It refuses to overwrite a different or symlinked installation. A
terminal can exit after enqueue. `worker once` and `worker serve --interval 30`
are available for diagnostics, but avoid manually starting another native
worker during an active campaign. The global owner lock and campaign
transaction fence still prevent double native starts.

The checkout, Python venv, frozen requests, package artifacts, external drive
if needed, and evidence directories must remain accessible to the same Mac
user. The user LaunchAgent is not a system daemon: it does not run while the
Mac sleeps, is shut down or its GUI user session is absent. Keep the Mac awake
and logged in for unattended Studio work, with supported Local scripting and
the native app reachable. A dialog, privacy/TCC denial, missing mounted drive,
busy owner, unreadable input, uncertain parent or expired deadline means a
truthful BLOCKED/UNKNOWN/expired result, not permission to click, bypass the
guard, start another attempt or report PASS.

## Plan, enqueue, status and operator controls

Generate and validate each supported *synthetic/public* v2 native request with
the existing `workflow_v2_cli` attestation/release/request steps and M2
`prepare-native`, assigning a **new immutable authorized request**, disposable
project target and evidence directory to **each** trial. Genuine media must be
importable in Studio; offline mock fixtures are not native proof. The parent
`vera.resolve-test-campaign/v1` plan is a closed JSON object containing
`schema`, `name`, `order` (`fixed` or `alternating`), `runAt`, `deadlineAt`,
`maxElapsedSeconds`, `maxDiskBytes`, `cases` and `trials`. `cases` consists of
`{ "id": "case-1", "comparisonKey": "fixture-a" }` rows. Each `trials`
entry contains `id`, `caseId`, `variant` (`single`, `baseline`, `candidate`),
`round` (1–5), `cacheMode` (`warm`, `isolated_fresh`), `sourceCommit`,
`planSha256` and the exact normalized `plan` (one v2 M2 native test plan,
already containing its pinned request). The `planSha256` equals SHA-256 of
that child plan's canonical sorted, compact, newline-terminated JSON bytes.
The M3 validator rejects duplicate trial, one-use request, target and evidence
identities, incomplete comparison rounds, nonconsecutive rounds, malformed
input and aggregate-time/disk violations before enqueuing anything.

```sh
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign \
  --root "$QUEUE" enqueue --plan "$PRIVATE_CAMPAIGN_PLAN"
# Save the printed resolve-campaign-... ID, then close the submitting shell.
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign \
  --root "$QUEUE" status "$CAMPAIGN_ID"
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign \
  --root "$QUEUE" report "$CAMPAIGN_ID" --format markdown
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign \
  --root "$QUEUE" pause "$CAMPAIGN_ID" --command-id operator-pause-1
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign \
  --root "$QUEUE" resume "$CAMPAIGN_ID" --command-id operator-resume-2
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign \
  --root "$QUEUE" cancel "$CAMPAIGN_ID" --command-id operator-cancel-3
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign \
  --root "$QUEUE" reconcile "$CAMPAIGN_ID" --command-id operator-observe-4
```

Each unique `--command-id` is globally audited and idempotent: repeating the
same ID/action/operator returns the original result; changing the arguments
is refused. Pause is **after the currently active native test** (or immediately
before work starts); resume permits only eligible pending work; cancel drops
**pending** tests, never kills or marks a live native operation stopped.
Reconcile only observes the **already-bound same** parent request/status under
the global lock. None of the controls can issue `parent.start`, clear an
UNKNOWN reservation, alter an authorized request or create fresh native work.

SQLite WAL plus append-only journal is authoritative. Derived private
`<queue>/<campaign-id>/status.json`, `report.json` and `report.md` are rebuilt
atomically; public-safe projections contain no full private request locator,
raw evidence, credentials or home/media paths. `status` reports scheduled/
running/paused/blocked/terminal state, last recorded heartbeat, case/trial,
counts, honest budgets and UTC times. A heartbeat indicates a *recorded worker
tick*, not that Resolve or the worker is live now. No speculative ETA is
published. `report` holds individual trial identities, outcomes, immutable
hashes, verified-only comparable raw wall-clock observations, median/range,
named overhead spans if actually observed, and matched A/B regressions.
Mocks, unknown receipts and incomparable fixture/build/cache conditions are
excluded from statistics. Source evidence remains private; actual installed
Studio save/close/reopen/readback is mandatory to claim native success.

## Optional phone monitor (private Tailscale Serve HTTPS only)

The HTTP server binds **only** to `127.0.0.1`, on port `51762` by default.
If that port is occupied, use the same alternate `--port` on both
`install-launchd` and `install-tailscale-path`; never displace an existing
service just to satisfy the example port. On the Producer's Mac, `51762` is
the running VERA conductor's single-run TCP lease, so the independent M3
monitor was installed on **`127.0.0.1:51763`**. The external HTTPS path is
still `/resolve-tests/`; the original dashboard keeps port `51761`.
The existing `/` VERA dashboard **must not be replaced**. The intended
topology is:

```
tailnet HTTPS :443 /                 -> 127.0.0.1:51761 (existing dashboard)
tailnet HTTPS :443 /resolve-tests/   -> 127.0.0.1:51762 (M3 monitor)
                                             |
                                             -> private campaign SQLite (read/control)
separate M3 LaunchAgent              -> serial native coordinator
```

Select the exact HTTPS tailnet hostname (without `https://` or `/`) and the
**exact** permitted Tailscale user login, e.g. the login visible in the
Tailscale identity page. Use your *actual* values rather than the examples:

```sh
export TAIL_HOST='YOUR-MAC.YOUR-TAILNET.ts.net'
export TAIL_LOGIN='YOUR-TAILSCALE-LOGIN@example.com'
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign_web \
  --root "$QUEUE" init-secret
# Read the secret on the private Mac terminal; do not paste into URLs,
# screenshots, logs, issue comments or public/shared documents.
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign_web \
  --root "$QUEUE" show-secret
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign_web \
  --root "$QUEUE" --host "$TAIL_HOST" --operator "$TAIL_LOGIN" \
  install-launchd
```

This creates the independent user LaunchAgent
`org.vera.resolve-test-campaign-monitor.m3`, which serves the page as long as
the GUI session is active. It uses a private mode-0600, same-UID random access
token; nothing secret is stored in its plist, public reports or URL. The token
is not regenerated on subsequent `init-secret` calls. Open the Serve HTTPS
page on an **authorized tailnet phone** and enter the local token in the form.
The login step requires both an exact `Tailscale-User-Login` header and the
unpredictable token, issuing a one-hour in-memory Secure/HttpOnly/SameSite
cookie scoped to `/resolve-tests/` plus a session-bound CSRF token. GET status/report and audited POST
controls require the same exact login and session; POST additionally requires
the exact HTTPS Origin and CSRF header. A mere identity header from a direct
loopback connection does not authorize controls. Sessions expire, and a
monitor restart requires re-login; nothing about the native queue is reset.

**Add the Serve path explicitly after checking the existing root.** The
installer snapshots `tailscale serve status --json`, refuses a missing root,
conflicting mount or Funnel, adds one background **Serve** path, then compares
the original `/` proxy byte-for-byte and verifies the new path:

```sh
umask 077
tailscale serve status --json > /tmp/tailscale-serve-before-m3.json
uv run --frozen python -m vera_timeline_agent.resolve_test_campaign_web \
  --root "$QUEUE" install-tailscale-path
tailscale serve status --json > /tmp/tailscale-serve-after-m3.json
# Expect: https://$TAIL_HOST/resolve-tests/ (only on the tailnet)
```

The `install-tailscale-path` command **does not** launch a monitor, ask for
Funnel, clear/reset Serve or overwrite `/`. It assumes the existing HTTPS
`:443` `/` root points to a local proxy (at the time of the request,
`127.0.0.1:51761`). It refuses a previously configured M3 mount, rather than
silently changing it. Confirm both URLs from the Mac and authorized phone:
the existing root dashboard remains available, and `/resolve-tests/` shows
the M3 access form. If status verification fails, do not run more Serve
commands blindly; inspect the before/after status snapshots and restore the
existing root manually as necessary. Do **not** use `tailscale serve reset`,
`tailscale serve off` (without a path), or `tailscale funnel`.

To disable only this mount after verifying the exact Tailscale CLI syntax:

```sh
tailscale serve --set-path=/resolve-tests/ http://127.0.0.1:51762 off
tailscale serve status --json  # confirm original '/' remains unchanged
```

To stop **only** the monitor and keep the campaign worker untouched:

```sh
launchctl bootout gui/$(id -u)/org.vera.resolve-test-campaign-monitor.m3
```

To stop **only** the campaign worker (no new cases start; live detached native
work must still be reconciled on restart):

```sh
launchctl bootout gui/$(id -u)/org.vera.resolve-test-campaign-worker.m3
# resume only the worker by bootstrapping its exact existing plist:
launchctl bootstrap gui/$(id -u) \
  "$HOME/Library/LaunchAgents/org.vera.resolve-test-campaign-worker.m3.plist"
```

Do not erase the SQLite database, parent requests, evidence or journals. The
three LaunchAgents are deliberately independent. Disabling Serve or closing
the phone/browser/monitor does not cancel, pause or run an M3 campaign. Reboot
may restore a background Serve route, but user LaunchAgents and Resolve can
still require login; expired cases remain expired rather than being run late.

### Privacy and operational limits

- Only supported synthetic/public disposable native work; do not upload
  private project/media/evidence or bind the monitor beyond loopback.
- Tailscale Serve identity headers are stripped/replaced by Serve for tailnet
  traffic, but **direct local processes can forge them**. The separate private
  access token is necessary and remains private to this Mac. A hostile process
  acting as the same OS user can also read local queue files: this is not a
  sandbox against a compromised Mac account.
- The session cookie is restricted to `/resolve-tests/`, so normal root
  dashboard requests do not carry it. This is **not** JavaScript-origin
  isolation: a compromised root-dashboard script under the *same* HTTPS origin
  could still issue same-origin requests to `/resolve-tests/`. Treat the
  existing root dashboard as trusted code; a distinct HTTPS origin would be
  required for isolation from a compromised dashboard.
- Tailscale Funnel sends no Serve user identity; it is prohibited. Tailnet
  ACLs/sharing must allow only intended users. Shared devices may carry valid
  identities; the exact-login check still applies.
- The phone UI shows only sanitized case IDs/counts/journal summaries and
  report links. A stale heartbeat, an UNKNOWN/blocked reason, a pending
  expired deadline or an interactive Resolve dialog needs human attention.
  No browser action drives the Resolve UI.

## Evidence and downstream use

### Phase-5 real Studio acceptance result (2026-11-06)

An independently launched macOS user LaunchAgent ran a **bounded 2-case,
8-trial** pilot in DaVinci Resolve Studio 21.1.1 using fresh, independently
verified synthetic v2 packages and authorized one-use native requests for
every trial. Trial order was A/B followed by B/A **within each case**. The
fixture used the same offline-generated 25-fps video source as the prior #447
acceptance; two case IDs exercise campaign isolation, not distinct editing
workloads. The submitter exited before due time, and the campaign LaunchAgent
was booted out and back in **while a detached native parent was LIVE**.
Read-only reconciliation retained its one committed intent and identity.

The authenticated M2 terminal database and native readback report showed
all eight *completed_verified* **and comparable** results, each with one
expected timeline event, one media reference, zero markers, and a successful
native save/reopen/readback. Times are parent monotonic native wall seconds,
not render times or evidence of a production speed improvement:

| Case | Round | Variant | Native wall seconds | Authenticated result |
| --- | --- | --- | ---: | --- |
| synthetic-case-a | 1 | baseline | 68.801 | completed_verified |
| synthetic-case-a | 1 | candidate | 66.150 | completed_verified |
| synthetic-case-a | 2 | candidate | 106.591 | completed_verified |
| synthetic-case-a | 2 | baseline | 32.950 | completed_verified |
| synthetic-case-b | 1 | baseline | 42.793 | completed_verified |
| synthetic-case-b | 1 | candidate | 28.444 | completed_verified |
| synthetic-case-b | 2 | candidate | 24.405 | completed_verified |
| synthetic-case-b | 2 | baseline | 21.252 | completed_verified |

Pilot campaign: `resolve-campaign-7a818136c76149aeaa451d400c5f937a`,
frozen plan SHA-256:
`93a3815fd9302f82b45f88650b72f2bfe2524b4dc15a7722297bb8c13f90ed6b`.
Final authenticated status: **8/8 completed_verified; 8/8 comparable; plan
integrity verified; `all_children_native_verified`**, ended
`2026-11-07T00:08:01Z` (November 6, 7:08 PM Eastern). The pinned one-use
request identities, per-trial native receipts, target identities, native
timings, original journal, and preserved restart evidence remain under the
private Mac queue. The published `report.json` includes eight independent
`authenticated_native_receipt` observations and no failed/blocked/unknown
trials. The campaign coordinator LaunchAgent was restarted while a detached
native parent was still executing; no second native start was made for that
intent.

**Independent monitor deployment check (November 6):** the separate macOS
Python 3.12.14 LaunchAgent is loaded and its process listens only on
`127.0.0.1:51763`. Tailscale Serve exposes just the additional tailnet-only
`/resolve-tests/` path to that port, without Funnel, and the pre-existing `/`
proxy remains byte-identical at `127.0.0.1:51761`. Both HTTPS paths returned
HTTP 200 from the Mac. Loopback acceptance verified exact Tailscale login
plus private-token authorization, session/cookie scope, sanitized 8/8 status
and report, refusal without identity/session/Origin/CSRF, and refusal of an
invalid authenticated control without any command audit mutation. Private
token values and Mac-specific evidence paths are not included here.

**Still pending:** the Producer must open the tailnet HTTPS URL on the phone,
authenticate with the token retrieved privately on the Mac, and explicitly
confirm the 8/8 report is usable. Mac-origin HTTPS/HTTP and simulated session
tests are not a substitute for phone acceptance. PR #462 must remain draft
and #448 open until this confirmation and the post-documentation exact-head
CI / merge checks pass.

M1 simulated output never qualifies for native statistics. M2's genuine
single-request Studio save/reopen/readback acceptance is recorded in the
[#447 issue](https://github.com/mbelinkie/vera-script-to-timeline/issues/447);
M3 **multi-case unattended** qualification, restart/reconcile, and objective
native results are demonstrated by the real eight-trial Studio campaign,
not by the pure HTTP tests alone; phone acceptance is still pending.
#312/#313 consume the same immutable trial identity, comparison key,
baseline/candidate ordering,
raw timing, and verified native reports; their own representative fixtures,
four-hour *per-issue* benchmark budgets, genuine edit decisions and numeric
improvement targets are not part of M3's aggregate budget and are not reset
per child trial.
