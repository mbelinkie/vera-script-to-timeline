# #248 confirmed render retry

Status: implementation procedure only. No DaVinci Resolve retry has been run
or accepted as Studio evidence.

This is a narrow exception to the earlier #209 no-relaunch guidance: VERA
permits one visible retry after it authenticates a terminal `Failed` or
`Cancelled` result from the original render poll and ingests that exact result
into the host attempt journal. It preserves the failed attempt and its poll
result. An uncertain, refused, incomplete, or otherwise unverified result does
not qualify. If the retry also fails, the binding is terminal.

The retry proposal pins the existing session and target and gives the retry a
new output path ending in `-retry-1.mov`. Keep the original output and all
retained records. Review the retry plan's target UIDs, release, inputs, output
path, and finite action list before issuing fresh authority.

From the repository root, ingest the original failed poll result using the
result path and raw SHA256 printed by the installed script:

```sh
uv run --frozen python -m vera_timeline_agent.workflow_v2_cli output-ingest \
  --session "$SESSION" \
  --session-sha256 "$SESSION_SHA256" \
  --result "$FAILED_POLL_RESULT" \
  --result-sha256 "$FAILED_POLL_SHA256"
```

Prepare a fresh retry proposal, then issue its approval in an attended
terminal. The approval command displays the exact proposal and asks the local
operator to type its hash challenge; an agent must not answer that challenge.

```sh
uv run --frozen python -m vera_timeline_agent.workflow_v2_cli output-retry-plan \
  --session "$SESSION" \
  --session-sha256 "$SESSION_SHA256" \
  --output "$SESSION/retry-plan.json"

uv run --frozen python -m vera_timeline_agent.workflow_v2_cli output-authorize \
  --plan "$SESSION/retry-plan.json" \
  --output "$SESSION/retry-approval.json"
```

Prepare the read-only `retry_capture` request with the fresh approval:

```sh
uv run --frozen python -m vera_timeline_agent.workflow_v2_cli output-retry \
  --session "$SESSION" \
  --session-sha256 "$SESSION_SHA256" \
  --approval "$SESSION/retry-approval.json"
```

Use the printed request and handoff with the existing [manual install and
request-copy procedure](../issue-209/OPERATOR_STAGES.md). Keep the same saved
project and timeline open. Run the request once, then ingest its result with
`output-ingest` and the exact result path and hash. The retry capture checks the
same target before VERA creates the new prediction commitment and reservation.

```sh
uv run --frozen python -m vera_timeline_agent.workflow_v2_cli output-ingest \
  --session "$SESSION" \
  --session-sha256 "$SESSION_SHA256" \
  --result "$RETRY_CAPTURE_RESULT" \
  --result-sha256 "$RETRY_CAPTURE_SHA256"
```

After the retry capture succeeds, prepare the remaining fixed stages with
`output-next`, in this order: queue, start, poll, then post-render capture. For
each stage, install the exact printed request as directed by its handoff, run
it once, wait for the integration to return, and ingest the result before
requesting the next stage:

```sh
uv run --frozen python -m vera_timeline_agent.workflow_v2_cli output-next \
  --session "$SESSION" \
  --session-sha256 "$SESSION_SHA256" \
  --approval "$SESSION/retry-approval.json"

uv run --frozen python -m vera_timeline_agent.workflow_v2_cli output-ingest \
  --session "$SESSION" \
  --session-sha256 "$SESSION_SHA256" \
  --result "$NATIVE_RESULT" \
  --result-sha256 "$NATIVE_RESULT_SHA256"
```

Repeat that pair for each remaining stage. Keep Resolve running across queue,
start, poll, and post-render capture. Do not change targets, replace the
reviewed source, delete the first failed output, or reuse the original
authority. If any stage is refused or uncertain, stop and use `output-recover`
for read-only inspection.

After a complete retry poll and post-render capture, finalize the captured
result:

```sh
uv run --frozen python -m vera_timeline_agent.workflow_v2_cli output-finalize \
  --session "$SESSION" \
  --session-sha256 "$SESSION_SHA256" \
  --result "$POST_CAPTURE_RESULT" \
  --result-sha256 "$POST_CAPTURE_SHA256"
```

A successful residual comparison supports only
`bounded_output_residual_consistency`. Internal controls remain unverified;
continuous state stability and causal exclusivity remain unclaimed. Actual
Studio execution and its evidence are still required.
