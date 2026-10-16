# #209 operator stage handoff

Status: implementation and Claude review completed. Actual Studio construction,
save/reopen, render, adjacent geometry and same-MOV comparison passed on
2026-10-16; see [the smoke result](STUDIO_SMOKE.md). This document grants no
installation or app action.

Prepare a saved empty disposable project at 23.976 fps, 1920×1080 and 48 kHz.
Set the project frame rate before creating its empty timeline: Studio can refuse
the rate change once the timeline exists. The synthetic input needs audio
headroom; an exactly full-scale sample correctly blocks prediction before render.
Use authored quiet audio where needed rather than weakening the clipping check.

When the Producer authorizes agent operation, the agent handles reversible file
copies, app restarts and menu launches through the same installed flow. Retain
the actual chat authorization with the exact target and finite plan; never claim
that an agent entered a human terminal challenge. Ask the Producer only for a
step the available tooling cannot perform.

The source CLI has separate preparation, human authority, request and result
stages. `output-prepare` writes an immutable session and operator plan without
connecting to Resolve. `output-authorize` is the human-only terminal challenge
for that exact plan. An agent must never answer that challenge. `output-next`
prepares one canonical request extending the authenticated native operation
chain. `output-ingest` authenticates the actual result and retains the required
prediction/reservation/lineage artifacts. `output-finalize` consumes the actual
post-render capture, decodes the same delivered MOV and records comparison.
The first app exercise uses the ordinary verified synthetic profile.
`output-replan` prepares a fresh review-only proposal for the same pinned,
unfinished session when a new human grant is needed. It neither issues approval
nor resets a prepared, started, failed or uncertain native operation.
`output-recover` only lists retained status, reasons and artifact hashes.

Each prepared host request must enter the installed script through the accepted
[#109 manual installation/update flow](../../resolve-workflow-integration-v1.md#manual-installation-and-update),
as used by [#208's operator steps](../issue-208/operator/README.md). The operator
archives any prior installed request outside the installed inventory, then copies
the exact new host request as `vera-delivery-v2/request.json` beside the reviewed
installed `release.json`. Every actual installed source hash and both request
copies must match the stage handoff before launch. The new lane neither installs
files automatically nor offers a raw scripting or console fallback.

Quit/install/restart applies to the initial reviewed code installation. For
later request-only copies, wait for the previous script invocation to return
and keep the same saved target open. Keep Resolve running across queue, start,
poll and post-render capture; quitting would interrupt the render. Do not
replace installed source during the operation chain.

The fixed operation order is construction, save/reopen, pre-render capture,
queue, start, bounded status polling, and post-render capture. Each launch uses
the same injected audited script and exact saved target UIDs. New effects require
live authority. Polling and post-render capture may use the original expired
grant only after authenticating the completed start and reservation lineage;
post-reservation host comparison also preserves that historical evidence.
After each actual result, use the result path and raw hash for host ingestion
before preparing the next stage. Pre-render capture produces the authenticated
prediction before the corresponding output exists; queueing consumes its exclusive
reservation. A partial, uncertain or failed attempt remains in the chain and
must not be hidden by relaunching or choosing a successful retry.

Retain the actual installed/runtime/source inventories, operation and per-effect
records, exact native job/settings/output hash, save/reopen geometry, adjacent
pre/post geometry and host same-MOV decode/comparison evidence. The operator
checks picture, cadence and listening observations separately. A consistent
residual result claims only `bounded_output_residual_consistency`; internal
controls remain unverified and continuous state stability/causal exclusivity
remain unclaimed. This synthetic exercise does not close #178 or Sweden's
creative acceptance.
