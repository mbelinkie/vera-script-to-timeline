# Issue #416 live pilot proposal

**State: completed single-task pilot.** The original proposal below was approved and run as [#422](https://github.com/mbelinkie/vera-script-to-timeline/issues/422) on 2026-11-03. This document is a historical scope/result record, not permission for another call.

## Measured result

The delivered GitHub-to-Mac receiver ran one separately approved `deepseek-flash` request against source `1367f58e9440b173507b35237221c6dd070425de`. The returned isolated candidate changed only the allowed target. All 17 frozen test methods and their subcases passed, and Codex independently reran the check and assessed the exact diff before integration. The initial read-only hosted validator refused while canonical review was pending; its rerun passed after the exact approval record was complete. The Mac invocation then passed every current gate before the single provider call.

The controller reserved USD0.0109152 and recorded verified usage at a conservative peak-priced charge of **USD0.0006042**, below the unchanged USD0.25 task/campaign ceilings. All earlier ledger rows, original receipts/manifests and #411's full uncertain hold remained unchanged. Temporary operator flags expired with the one poll; persistent activation is disabled. Private provider output and account evidence stay local.

This proves one small, complete-context Python task through the real receiver/provider path. It does not establish general primary-agent qualification, approve another task or retry, or enable a persistent poller. Future jobs need their own bounded scope and applicable approval.

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

## Original proposal's approval and identity preparation

After implementation delivery, the exact immutable identity was finalized and verified before invocation:

| Identity field | State |
| --- | --- |
| Manifest SHA-256 | `7ff630e611bbfa7b0822fb312621cd997ad3f4f6a248141606356410499ca9dd` |
| Source SHA | `1367f58e9440b173507b35237221c6dd070425de` |
| Adapter/build SHA-256 | Bound and verified privately; public binding retained on #422 |
| Reconciliation/build SHA-256 | Bound and verified privately; original accounting history preserved |
| Attempt ID | `pilot-422-2026-11-03-one` |
| Campaign | `live-pilot-422-2026-11-03` |
| Pilot issue number | #422 |
| Owner event/comment ID | `6608420951` |
| Canonical approval record | [Verified record](https://github.com/mbelinkie/vera-script-to-timeline/issues/422#issuecomment-6608635699) |

The one authorized provider request is complete. No credential setup, new service, poller or automatic retry was added. Its consumed receipt cannot authorize another attempt.
