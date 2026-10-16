# D3 Console decode recovery review

- **Task ID:** `/root/discriminator_output_verify`
- **Verdict:** **GO** for the same Console action with a corrected wrapper.
- **Classification:** preexecution wrapper/harness failure; not a Resolve capability result.

The operator's Console command failed while the wrapper opened `console-render.py`, before the helper compiled or entered Resolve. The exact failure was:

```text
UnicodeDecodeError: 'ascii' codec can't decode byte 0xe2 in position 45: ordinal not in range(128)
```

Offline reproduction against the actual helper bytes produced the same ASCII failure at byte `0xe2` (the UTF-8 arrow in the opening documentation string). Reading the same unchanged helper explicitly as UTF-8 and compiling it succeeded. The helper SHA-256 remains `48f8d3e5499cc4073f5c25fe70dfc3a2d88a04bc459cbe5bbba3783aa6ad90bb`; the Console config SHA-256 remains `ee05f7d1033c9b64fefaa1cc970a5cf1a9478c598075f82ebc3e89fd0011326c`.

No Console dispatch receipt, progress file, result, render output, or new render job exists. The queue remains at seven. The corrected wrapper should use `open(helper_path, encoding="utf-8").read()` in the existing `exec(compile(...))` expression, preserve all existing pins and guardrails, and dispatch the same action exactly once. The helper itself must not be edited and hashes must not be repinned. This retry will produce the first actual Console observation; no output conclusion can be drawn from the failed attempt.

Evidence: [`d3-console-decode-recovery-review.json`](../../../../../out/issue149-workflow-discriminators-20261003-kit-02/recovery/d3-console-decode-recovery-review.json), `recovery/d3-console-manual-pending.json`, `params/d3-console-render.json`, and the unchanged helper at `docs/investigations/issue-149/workflow-discriminators/console-render.py`.
