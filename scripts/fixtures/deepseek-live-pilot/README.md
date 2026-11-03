# DeepSeek live pilot packet

**Status:** proposal only. No issue, approval event, provider request, or spend authorization has been created.

## Exact task

Implement `safe_relative_path(value: object) -> str` in `target.py`. Return accepted nonempty relative POSIX path strings unchanged. Reject invalid inputs with `ValueError`.

Accept ordinary dots inside filenames and spaces in path segments. Reject non-strings, blank strings, absolute paths, leading tildes, backslashes, colons, ASCII controls (code points below 32 or 127), empty path segments, exact `.` or `..` segments, any exact `.git` segment, and an exact top-level `.github` segment. The reserved-name rules are case-sensitive. Nested `.github` and names such as `.githubish` are allowed.

The model may replace only `scripts/fixtures/deepseek-live-pilot/target.py`. Its response must be exactly one JSON object with the sole key `replacement`, whose string value is the complete replacement file contents. Diffs, extra files, and prose are not accepted.

## Frozen local check

```sh
/usr/bin/python3 -I scripts/fixtures/deepseek-live-pilot/check.py
```

The standard-library `unittest` harness loads only its explicit sibling `target.py` through `runpy.run_path`. It does not import project modules or add a repository path. `unittest.main(failfast=True, verbosity=1)` bounds the unimplemented baseline to its first failure: the exact command currently exits 1 with one error and 999 raw output characters. A temporary reference candidate passes all 17 test methods and their subcases. Frozen check SHA-256 for this packet: `90bc4dfe62c2a0cc4df89fdf57e4000dd6414cadfd51f39a9d7e655ac2d5dfe7` (packet artifact only; final approval manifest remains pending).

## Proposed one-attempt envelope

- Model: `deepseek-flash`
- Effort: `high`
- Maximum input: 20,000 tokens
- Maximum output: 4,096 tokens
- Attempts: one; retries: zero
- Task cap: USD 0.25
- Campaign cap: USD 0.25
- Lifetime cap: USD 10, including the existing issue #411 hold
- Tools, web search, DeepSeek Search/Fetch, and other external calls: disabled

Peak rates checked against the [official DeepSeek Models & Pricing page](https://api-docs.deepseek.com/quick_start/pricing/) on 2026-11-03 are USD 0.006 per million cache-hit input tokens, USD 0.30 per million cache-miss input tokens, and USD 1.20 per million output tokens. The reservation assumes every input token is a cache miss and all usage lands at peak rates:

`20,000 × 0.30 / 1,000,000 + 4,096 × 1.20 / 1,000,000 = USD 0.0109152`.

No Search/Fetch or other billable tool request is included or enabled.

## Finalization boundary

This packet is not an approval record. After the relevant implementation is merged, the exact manifest and all source/build identities must be computed from the merged artifacts. Only then may the owner create the separate pilot issue and dispatch event and prepare a new independent canonical approval. No hashes or IDs below are being represented as final:

- Manifest SHA-256: pending after merge
- Source SHA: pending after merge
- Adapter/build SHA-256: pending after merge
- Reconciliation/build SHA-256: pending after merge
- Attempt ID and campaign: pending after merge
- Pilot issue number and owner comment ID: not created

There are no new credentials or services, no poller, and no automatic retry. The reference candidate used to prove the harness green belongs in a disposable temporary directory; do not replace the repository's intentionally unimplemented `target.py` during this proposal work.
