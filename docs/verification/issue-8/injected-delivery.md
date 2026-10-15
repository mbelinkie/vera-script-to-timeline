# Issue #8 — injected Studio graphics operator handoff

Status: reviewed candidate with complete full validation **exit0**, including
644Python tests. Durable exit/log evidence is retained in
[prepared artifact inventory](prepared-handoff.md). Seven attestations, a
source-equivalent release and preflight-only requests are prepared; actual
native/visual acceptance remains pending. #219 released its native/render
window and #8's heavy validation has now drained. No automated rerun is needed
for unchanged source. The last operator-reported External Scripting setting
was **Local**, not the required None confirmation for the injected build.
Do not install an unreviewed candidate or treat the existing #109 installed
release as #8. No agent installation or preference mutation is authorized.

## Audited boundary

Accepted #109 source8ef9f864 supplies the immutable handoff, source-hashed
launcher, injected API, per-stage rehash and new-project UID checks. #8 adds a
standard-library native graphics module and a full-envelope attestation;
external CPython3.12 alone performs schema, media and package verification.
Resolve's injected interpreter receives no .venv or site-packages. Native
readback must account for all regular media plus the exact separate VERA
template bin, rejecting other media. The setting and atlas remain unchanged.

Only exact Studio21.1.0/build14 or21.1.1/build10 enters the injected adapter.
For EV24,21.1.1/10 is a qualification candidate, not inherited proof from
#109. Actual controls, atlas pixels, graph/data persistence and64/120ranges
must pass; no mismatch is automatically normalized or accepted.

## Preparation (completed; do not overwrite retained artifacts)

Use the dedicated #8 worktree and locked Node24.19.0/npm11.17.0/CPython3.12
environment. Preserve existing prepared packages. For the seventh package use
the already retained `out/issue8/revision-inputs/revised-120` manifest/report/
materialization plan and that directory's sibling `registered-template`.
Never build an internal Transport package directly as graphics acceptance.

The following commands document preparation already completed for all seven
packages. Do not rerun them over the retained outputs:

```sh
rtk ctx-wire run uv run --frozen python -m vera_timeline_agent.studio_graphics_workflow_cli attest out/issue8/packages/standard-64 --output out/issue8/handoffs-cbb20b5/standard-64
rtk ctx-wire run uv run --frozen python -m vera_timeline_agent.studio_graphics_workflow_cli release --output out/issue8/graphics-release-cbb20b5
rtk ctx-wire run uv run --frozen python -m vera_timeline_agent.studio_graphics_workflow_cli request out/issue8/handoffs-cbb20b5/standard-64/graphic.json --release out/issue8/graphics-release-cbb20b5 --output out/issue8/requests-cbb20b5/standard-64-preflight.json --evidence-dir out/issue8/native-evidence/standard-64
```

The release was built once from the exact final reviewed source. Outputs are new
only; do not rerun these commands over retained files. `graphic.json` pins the
entire Studio envelope and the independently verified `transport.json`; both
share one unique build-derived target. A changed file/addition invalidates the
handoff. Keep reports outside packages; avoid Finder-added package metadata.
Record exact release/request/attestation hashes and requested target names.
The preparation above does not assert External Scripting None or authorize a
native build. It never invokes Resolve or installs a script.

## Installation and preflight (operator-owned)

1. Quit Resolve. Inspect the prepared `graphics-release`: `VERA Graphics v1.py`
   and `vera-graphics-v1/`, including `release.json` and only the declared
   Python sources. Record its release-manifest SHA-256.
2. In Finder open `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/`.
   Copy those two entries there. Do not overwrite/merge an older installation:
   archive any old **Graphics** script/folder together outside the plugin root
   first. Leave other plugins, including Delivery, untouched. macOS may ask for
   administrator authorization. The Resolve user must be able to read the
   sources and its private request; do not expose private locators to others.
3. Copy the selected preflight request into installed `vera-graphics-v1/` as
   `request.json`. Open Studio, confirm Preferences > System > General >
   External scripting is **None**, retain Allow safe automatic scripted actions
   and restart if required. Record the actual version/build and None setting.
4. Open a saved disposable current project/timeline on Edit. Record its name
   and timeline list/count. Save it manually before launch. Launch Workspace >
   Workflow Integrations > **VERA Graphics v1** once. Do not interact with the
   app while it runs. Require a new `result-<id>.json`: `preflight_passed`,
   connected Studio21.1.1/build10 and the requested fresh target. The disposable
   current project must remain selected, with no new target created.

## Authorized build and qualification (operator-owned)

1. Read `graphic.json` and confirm the exact target is nonproduction. With
   External Scripting None actually confirmed, prepare the explicit request:

   ```sh
   rtk ctx-wire run uv run --frozen python -m vera_timeline_agent.studio_graphics_workflow_cli request out/issue8/handoffs-cbb20b5/standard-64/graphic.json --release out/issue8/graphics-release-cbb20b5 --output out/issue8/requests-cbb20b5/standard-64-build.json --evidence-dir out/issue8/native-evidence/standard-64 --action build --authorize-new-nonproduction --external-scripting-none
   ```

   These flags are the operator's audited statement, not agent defaults.
2. Quit Resolve. Archive the prior request outside the plugin root and copy
   this build request as installed `request.json`. Restart, open the same saved
   disposable project/timeline on Edit, and launch **VERA Graphics v1** once.
3. Require `status: verified`, `verified: true`, no discrepancies and actual
   `graphicObservations` covering the requested occurrence. Inspect the saved/
   reopened new target and retain result/request/attestation/release hashes.
   First establish64/120exact ranges and actual trusted control descriptors;
   any failure stops qualification. Do not change compensation or type checks
   to make a report green without retained evidence and review.
4. Repeat fresh request/install/restart/launch for the other matrix targets,
   then complete the [visual and changed-build isolation checklist](operator-checklist.md).
   Do not relaunch an interpreter already holding VERA code. Do not reuse,
   edit, delete or promote a failed partial target; preserve it for inspection.

No native result or visual/render acceptance is currently claimed. Synthetic
unit attestations and fake Resolve objects are test inputs, never operator
handoffs or qualification evidence. Full terminal access does not supply the
operator's settings confirmation, installation or visual judgment.
