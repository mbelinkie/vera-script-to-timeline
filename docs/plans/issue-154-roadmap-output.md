# Issue 154: bounded roadmap response transport

## Scope and exclusions

Bound `spawnSync("gh", ...)` output in `scripts/roadmap.mjs`, report transport
failures without printing partial oversized JSON, and add an issue-owned
process-boundary test for a valid response over 1 MiB plus a real bounded
overflow. Preserve claim-comment pagination, dependency checks, rate-limit
preflights, roadmap locks, and command output on successful calls.

Expected files: `scripts/roadmap.mjs`, a new
`scripts/roadmap-transport-154.test.mjs`, `package.json` to run the new test
with the roadmap suite, and this plan/evidence record. Existing accepted tests
remain unchanged. No contracts, fixtures, goldens, product APIs, or generated
types are touched. No dependency is needed: Node's existing `spawnSync` supports
an explicit `maxBuffer` and reports `ENOBUFS`.

This is a roadmap tooling slice; the product specification does not define the
CLI transport contract. The related discovery and reproduction are retained in
`docs/investigations/issue-144/roadmap-inspect-buffer-discovery.md`.

## Pre-change reproduction

On Node v24.19.0 / npm 11.17.0, a read-only inspect of the large-history #144
exits 1 with 1,114,113 bytes on stderr and no JSON result. The command was
wrapped to retain only process metadata so the partial comment response did not
enter the evidence record:

```sh
rtk env PATH=/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH node --input-type=module -e 'import { spawnSync } from "node:child_process"; const r = spawnSync(process.execPath, ["scripts/roadmap.mjs", "inspect", "144"], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 }); const text = r.stderr ?? ""; console.log(JSON.stringify({ status: r.status, signal: r.signal, errorCode: r.error?.code ?? null, stdoutBytes: Buffer.byteLength(r.stdout ?? ""), stderrBytes: Buffer.byteLength(text), knownBufferMarker: /ENOBUFS|buffer length/i.test(text), jsonParseFailure: /Unexpected end of JSON input|Unexpected token/i.test(text) }));'
```

Result: `{"status":1,"signal":null,"errorCode":null,"stdoutBytes":0,"stderrBytes":1114113,"knownBufferMarker":false,"jsonParseFailure":false}`. The CLI's captured diagnostic is the truncated oversized response described by #154's original transport evidence.

## Planned checks

- New process-boundary tests: a valid synthetic issue response larger than 1 MiB succeeds; a response beyond the configured bound yields a concise size error and no partial JSON parse/result.
- `npm run test:roadmap` for current claim pagination, dependency, rate-limit, and lock behavior plus the new transport test.
- `npm run lint:typescript` and `npm run typecheck:typescript`.
- Read-only `npm run roadmap -- inspect 144`, retaining only the result summary and selected inspection fields; no claim/status/dependency mutation.
- `git diff --check`.

## Acceptance and producer steps

Acceptance is Automated, so the retained passing commands and read-only #144
inspection are the acceptance evidence. No producer action is required.

## Results

On Node v24.19.0 / npm 11.17.0, all required checks passed:

- `rtk env PATH=/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run test:roadmap`: 29/29 passing, including claim pagination, dependencies, GraphQL budget, and lock tests plus six transport tests.
- `rtk env PATH=/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run lint:typescript`: passed.
- `rtk env PATH=/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run typecheck:typescript`: passed.
- `rtk git diff --check`: passed.

The dedicated worktree had no `node_modules`; lint and typecheck used a temporary
ignored symlink to the existing #148 worktree's installed dependencies (ESLint
10.9.1 and TypeScript 6.0.3). No package was installed or added.

The read-only live inspection command was
`rtk env PATH=/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run roadmap -- inspect 144`.
It returned status 0 with 19,625 bytes of JSON from the CLI. Its selected result
was:

```json
{
  "issue": {
    "number": 144,
    "title": "Build a bounded headless script–Resolve round-trip proof harness",
    "state": "CLOSED",
    "labels": ["model:sol", "effort:xhigh", "type:investigation"]
  },
  "project": { "status": "Done", "acceptance": "Automated" },
  "dependencies": { "valid": true, "resolved": true, "count": 4 },
  "claim": {
    "state": "active",
    "model": "gpt-6.1-sol",
    "effort": "xhigh",
    "task": "01a103aa-e47a-79e0-88b5-62e6d9637d1b",
    "branch": "codex/issue-144-roundtrip-harness",
    "startedAt": "2026-10-03T21:39:04.613Z"
  }
}
```

The synthetic process-boundary suite also exercises the complete claim-page
path: a greater-than-1-MiB initial issue response sets `hasPreviousPage: true`,
then an older comments response supplies an active claim, and `inspect` returns
that exact claim. Other cases confirm a large valid response succeeds, a 32 MiB
issue response crosses the 16 MiB cap and yields a short error without parsing
partial JSON, malformed JSON returns no inspection, nonzero rate-limit
responses retain reset guidance, and startup/exit/signal failures are reported
clearly. No live claim, status, or dependency was changed.
