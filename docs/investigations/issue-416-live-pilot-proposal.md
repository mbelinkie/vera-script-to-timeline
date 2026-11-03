# Issue #416 live pilot proposal

**State: proposal only.** This document describes a bounded synthetic coding pilot. It is not an approval marker, provider request, issue, dispatch event, or spend authorization. No issue or owner event has been created.

## Frozen task

Implement exactly one function in `scripts/fixtures/deepseek-live-pilot/target.py`:

```python
def safe_relative_path(value: object) -> str: ...
```

For an accepted value, return the original string unchanged. Accept nonempty relative POSIX paths, including ordinary dots within filenames and spaces in path segments.

Raise `ValueError` for every invalid value:

- non-string values and blank strings;
- absolute paths and values beginning with `~`;
- any backslash, colon, ASCII control character with ordinal below 32, or DEL (ordinal 127);
- empty slash-delimited segments, including repeated or trailing slash;
- a segment exactly equal to `.` or `..`;
- a segment exactly equal to `.git` anywhere;
- a top-level segment exactly equal to `.github`.

These reserved-name checks are case-sensitive. The `.github` restriction applies only at the top level. Do not normalize accepted strings.

## Allowed output

Only `scripts/fixtures/deepseek-live-pilot/target.py` may be replaced. The complete model response must be valid JSON shaped as:

```json
{"replacement": "<entire UTF-8 replacement contents of the one approved target.py>"}
```

The response must have exactly the `replacement` key with a string value. Reject patches, extra files, explanations, markdown wrappers, or non-JSON output. Do not commit the model candidate into the repository as part of this pilot proposal.

## Frozen acceptance command

```sh
/usr/bin/python3 -I scripts/fixtures/deepseek-live-pilot/check.py
```

`check.py` uses only the Python standard library and loads `target.py` by its explicit sibling path with `runpy.run_path`. It does not import arbitrary project code or modify `sys.path`. The committed `target.py` raises `NotImplementedError` by design. `unittest.main(failfast=True, verbosity=1)` bounds the baseline failure: the exact command exits 1 with one error and 999 raw output characters. A reference implementation in a temporary copy passes all 17 test methods and their subcases. The frozen check SHA-256 for this packet is `90bc4dfe62c2a0cc4df89fdf57e4000dd6414cadfd51f39a9d7e655ac2d5dfe7`; this is a packet artifact hash, not the final approval manifest identity.

## Proposed request limits

| Setting | Limit |
| --- | --- |
| Model | `deepseek-flash` |
| Effort | `high` |
| Maximum input | 20,000 conservative input units |
| Maximum output | 4,096 tokens |
| Attempts | 1 |
| Retries | 0 |
| Task cap | USD 0.25 |
| Campaign cap | USD 0.25 |
| Lifetime cap | USD 10, including the existing issue #411 hold |
| Tool calls | Disabled, including web search and DeepSeek Search/Fetch |

The official [DeepSeek Models & Pricing page](https://api-docs.deepseek.com/quick_start/pricing/) was checked on 2026-11-03. Its peak `deepseek-flash` rates are USD 0.006 per million cache-hit input tokens, USD 0.30 per million cache-miss input tokens, and USD 1.20 per million output tokens. The estimate uses the cache-miss input rate for every input token and peak rates for the entire request:

- Input reservation: `20,000 × USD 0.30 / 1,000,000 = USD 0.006`
- Output reservation: `4,096 × USD 1.20 / 1,000,000 = USD 0.0049152`
- Worst-case token reservation: **USD 0.0109152**

The proposal enables no web/tool requests, so it makes no Search/Fetch request and incurs no per-request Search/Fetch charge. The USD 0.25 task and campaign caps remain hard limits. The USD 10 lifetime cap continues to include the pre-existing #411 hold; this proposal does not release or alter that hold.

## Approval and identity remain pending

The immutable manifest, source, adapter/build, and reconciliation/build hashes cannot be finalized until the implementation is merged. The attempt ID and campaign must bind those final artifacts. The separate pilot issue and exact owner dispatch comment must also be created before their IDs can be recorded.

| Identity field | State |
| --- | --- |
| Manifest SHA-256 | Pending merged artifacts |
| Source SHA | Pending merged artifacts |
| Adapter/build SHA-256 | Pending merged artifacts |
| Reconciliation/build SHA-256 | Pending merged artifacts |
| Attempt ID | Pending merged artifacts |
| Campaign | Pending merged artifacts |
| Pilot issue number | Not created |
| Owner event/comment ID | Not created |
| Independent canonical approval | Not requested or recorded |

No provider request, credential setup, new service, poller, automatic retry, or issue creation is part of this work. After merge and identity finalization, a separate independent approval must bind the exact live marker and dispatch event before any live request is considered.
