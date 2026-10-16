# Task ID #149 — pending operator W2/W5 run order

Status: **offline only / dispatch blocked**

This package is bound to project `VERA Issue 149 Workflow Reruns 20261002-kit-01` (UID `1a05ff3a-8b04-43e3-95ab-c970b93b6415`), the latest
owned state (13 timelines, 64 items, 23 media-pool items), harness SHA
`a19a79d684f8dbaed6d36bda0d493eed964d37888bddf7749e3bbdf601f59ab5`, launcher SHA `e4f58381c398bc0ce13130fddb25c956876f7754dc877346fe389dfb826c2450`, and External Scripting `None`.
The exact operator-dependent timelines are:

- W2-X-mute: `abdd2270-7155-4fba-850c-82201a38f4c2`; A2 mute on, A2 solo off, every other M/S control off.
- W2-Y-solo: `bec69cf7-c76e-4820-9e1f-9b425449614f`; A2 solo on, A2 mute off, every other M/S control off.

No parameter in this directory carries a completed operator attestation. Do
not stage or dispatch until the operator replies that both manual states are
set and Y is left current. API track getters are not a substitute for manual
M/S state.

## Required order after the operator reply

1. Select X on the Edit page using `01-select-w2-x-mute-edit-pending.json`.
2. Run `02-w5-context-x-current-y-inactive-pending.json`. It must read X as
   current, read Y while Y is inactive, then restore X. Hold if the observed
   active-X A2 enabled getter is not the required `false`; retain the raw
   `xCurrent`, `yCurrent`, and `xWhileYCurrent` rows.
3. Dispatch X OTIO export (`03`) once. Before any output inference, inspect the
   OTIO for A2 mute true, A2 solo false, and all other M/S fields off; retain
   the operator reply separately.
4. Stage X render (`04`) once, then fill the exact returned job ID into the
   bounded 45-second poll (`05`). Never guess a job ID or relaunch a render.
5. Select Y on the Edit page (`06`), leaving Y current. Dispatch Y OTIO export
   (`07`) once and require A2 solo true, A2 mute false, and all other M/S
   fields off in the OTIO before interpreting the render.
6. Stage Y render (`08`) once and fill its exact job ID into poll (`09`), with
   the same bounded read-only rule.

## Restoration requests

After the primary X/Y evidence is retained, request and record a fresh manual
reply before each restoration. For Y, turn A2 Solo off with all other M/S off,
then use configs `10`–`13` for the export, restored render, and bounded poll.
For X, turn A2 Mute off with all other M/S off, then use configs `14`–`17`.
These are separate requests; their attestation fields intentionally remain
`pending` until the operator confirms the actual Edit-page controls.

Any mismatch, missing OTIO flag, unexpected current timeline, failed bounded
poll, or missing operator reply is a hold condition. Preserve the first
receipt/result and do not retry or infer M/S from API enabled getters.

## Current both-set handoff clarification — 2026-10-02

The producer has now replied `both set`. The fresh observe receipt is
`19-observe-operator-both-set-02.json`; it binds Y as the current timeline and
uses the authoritative launcher path
`/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/VERA Issue 149 Workflow Reruns.py`
with launcher SHA
`e4f58381c398bc0ce13130fddb25c956876f7754dc877346fe389dfb826c2450`.
The earlier `18-observe-operator-ready-pending.json` is consumed and must not
be reused. The older `01`–`18` pending files also carry the nonexistent
`.../Blackmagic Design/Resolve/...` launcher path; use only fresh `02` files
with the `DaVinci Resolve` path.

For the fresh operator-ready chain, the authorized order is:

1. Keep Y current and export Y OTIO; require A2 Solo true, A2 Mute false,
   and every other M/S field off before interpreting output.
2. Stage Y render once and poll only with the exact returned job ID.
3. Select X, run the W5 context read, require X current/Y inactive and the
   observed active-X A2 enabled getter false, then restore X.
4. Export X OTIO; require A2 Mute true, A2 Solo false, and every other M/S
   field off before staging the X render. Poll only with its exact returned
   job ID.
5. After the primary outputs, obtain a fresh manual restoration attestation
   before Y Solo-off restoration, then X Mute-off restoration. Each restored
   export/render/poll remains a separate chain.

The W2/W5 owned inventory remains exactly 13 timelines, 64 items, and 23
media-pool items under project UID
`1a05ff3a-8b04-43e3-95ab-c970b93b6415`; W2-X is
`abdd2270-7155-4fba-850c-82201a38f4c2`, W2-Y is
`bec69cf7-c76e-4820-9e1f-9b425449614f`, and the harness probe SHA remains
`a19a79d684f8dbaed6d36bda0d493eed964d37888bddf7749e3bbdf601f59ab5`.
