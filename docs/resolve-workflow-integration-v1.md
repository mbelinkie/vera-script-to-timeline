# Resolve Workflow Integration delivery v1

Issue [#109](https://github.com/mbelinkie/vera-script-to-timeline/issues/109).
This is the file-driven injected delivery adapter. It accepts one independently
verified ready package and creates one fresh nonproduction project/timeline.
Installation, preferences, launch and final acceptance are operator actions.
No browser or companion lifecycle is included; #116/#157/#158 own those seams.

## Versions and accepted sources

The release format and menu script are v1; **the SHA-256 of `release.json` is
the exact installed source version**, not the mutable repository checkout.
The launcher checks every bundled source file against that hash-bound release
before importing it. It refuses extra Python source, bytecode caches and another
already-loaded VERA runtime. It never adds `.venv` or `site-packages` to Resolve.

Source pins: #34 `2586dded4d3566e944d7938604b20bded6fc36fb`, #107
`c9614eaf7bf7aa88f4cf33e77180ff5a393377e4`, #147
`75029de57baa594d3dfc7f509a09cfc21943e088`. The original #34 Studio-only
exception still applies: Free parity was skipped. #107 accepted only injected
startup with an empty timeline, not full assembly.

The v1 adapter permits exact Studio **21.1.0 build 14** (accepted #34 assembly
baseline) and **21.1.1 build 10** (installed calibration candidate). Other
versions, suffixes and Free are refused. The latter becomes accepted delivery
evidence only when the real #109 producer run below passes. A successful mocked
test or import under the shipped ResolvePython interpreter is not native
assembly evidence. The real report stamps its actual interpreter and Resolve
version/build; it does not infer either from old acceptance.

## Public API and manual boundary

The installed Blackmagic Workflow Integration README documents copying Python
scripts to the Workflow Integration Plugins root and launching them through
Workspace > Workflow Integrations. Resolve injects the `resolve` variable.
The adapter uses the documented project-manager/media-pool/timeline APIs for
new project creation, settings, bins, media, tracks, item ranges, markers,
save/close/reopen and readback. It never calls the external `scriptapp` bridge.
No public API is used to install a script, change preferences or infer the
External Scripting preference; that setting is separate operator evidence.

Preflight reads the current disposable project/timeline only. Build calls
operate on a newly created build-derived target; existing targets are never
selected for assembly or overwritten. Any failure preserves the ready package
and retains the named partial target for inspection. No deletion/rollback is
performed. Every mutating adapter stage rechecks the entire attested package;
changes between verification and any later stage stop the build. Readback checks
project/timeline identity/settings, bins, all package media (including unused
sources), event source IDs and ranges, all track counts/names, timeline extent,
and exact marker inventory/fields/provenance.

Attestations are local trusted-verifier handoffs, not remote signed credentials.
Only the locked CPython 3.12 verifier command below creates one. Hashes pin its
complete inventory and the operator request; the injected runtime rechecks the
receipt, build and counts without importing native verifier dependencies. A
package's freshness is its unchanged bytes/build, not elapsed wall time. An old
unchanged package remains valid; edited/replaced/added/missing files are stale.
Keep preparation files and reports in a private local directory: they contain
local locators and media identity. Do not publish raw reports with private paths.

## Prepare the concrete acceptance artifact

Run from the delivered repository root with Node 24.19.0/npm 11.17.0 and the
locked Python environment. These commands prepare files; they do not install
anything or invoke Resolve. The retained synthetic #34 helper consumes frozen
inputs read-only. Use a new output directory for a different acceptance run.

```sh
rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.studio_assembly_acceptance_cli --output out/issue109/acceptance-package
rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_delivery_cli attest out/issue109/acceptance-package --output out/issue109/attestation.json
rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_delivery_cli release --output out/issue109/release
rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_delivery_cli request out/issue109/attestation.json --release out/issue109/release --output out/issue109/preflight-request.json --evidence-dir out/issue109/native-evidence --action preflight --external-scripting-none
```

The preparation command independently reruns ready-package verification, checks
that the entire inventory stayed identical during verification, and publishes
an immutable attestation outside the package. Its `projectName`/`timelineName`
are `VERA Delivery <build UUID> <unique suffix>`. Output files are exclusive:
an existing attestation/release/request is refused, not replaced. For the
prepared handoff these files already exist; inspect/reuse them rather than
rerunning their creation commands. The release command is reproducible from
the delivered source; two releases have identical manifest bytes/hashes.

## Manual installation and update

1. Quit Resolve. In Finder open the prepared `out/issue109/release` folder.
   It contains `VERA Delivery v1.py` and `vera-delivery-v1/` with `release.json`
   and a small `python/` runtime. Inspect the retained release SHA-256.
2. In Finder choose Go > Go to Folder and open
   `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/`.
   Copy those two prepared entries there. macOS may require administrator
   authorization. Copy `preflight-request.json` into the installed
   `vera-delivery-v1/` directory, naming it `request.json`.
   In Finder > Get Info > Sharing & Permissions, confirm the Resolve user's
   account can read `request.json`; keep other accounts from reading its private
   locators. The public source inventory is readable after an administrator copy.
3. An update requires quitting Resolve and archiving both old installed entries
   together outside the plugin root before copying the two new entries. Retain
   old release/request/report hashes. Never merge source folders or reuse a
   bytecode cache; restart Resolve after every update. Do not remove other
   plugins, ready packages or generated targets. No agent installer/updater or
   third-party Electron package is required.
4. Open Resolve Studio. Set Preferences > System > General > External scripting
   to **None**, retain **Allow safe** automatic scripted actions, and restart
   if preferences require it. Retain a screenshot/version note showing None.
5. Open a disposable nonproduction current project with a timeline on Edit.
   Record its name and timeline names/counts before the run. Save that project
   yourself before launch; the adapter does not save or modify it.

## Preflight and exact producer authorization

1. Launch **Workspace > Workflow Integrations > VERA Delivery v1** once.
   Expected: a new `native-evidence/result-<run-id>.json` reports
   `preflight_passed`, the exact connected version/build and requested target.
   The current disposable project remains selected. No target was created.
   Every launch creates new `started-`, `result-` and `hashes-` files.
2. Review `attestation.json`: confirm `ready_to_import`, counts and the exact
   fresh target name. Confirm the chosen build is nonproduction and authorize
   **that named target** with the following operator command. This flag is an
   explicit audited authorization, not an agent default:

```sh
rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_delivery_cli request out/issue109/attestation.json --release out/issue109/release --output out/issue109/build-request.json --evidence-dir out/issue109/native-evidence --action build --authorize-new-nonproduction --external-scripting-none
```

3. Quit Resolve. Archive the installed preflight `request.json` outside the
   plugin root; copy `build-request.json` there as `request.json`. Restart
   Resolve and open the same disposable current project/timeline on Edit.
4. Launch **VERA Delivery v1** once. Expected: the unique target is created,
   media/events/tracks/markers assembled, saved, closed, reopened and compared
   to the canonical manifest. `result-<run-id>.json` reports `verified: true`,
   `status: verified`, zero discrepancies and the actual runtime/version.
   `hashes-<run-id>.json` pins the result/request/release/attestation.
5. Inspect the reopened new timeline in Resolve and compare the manifest at
   `acceptance-package/Builds/13000000-0000-4000-8000-000000000036/timeline-manifest.json`.
   Confirm media identities, every event/source/record range, track names/counts,
   timeline length and every marker. This manifest does not authorize extra
   graphics, audio treatment, render or upload.
6. Open the previous disposable project manually and confirm its recorded
   timelines are intact. Return to the new target if desired. Retain the None
   screenshot, installed release SHA, actual version, native result and hashes.
   Reply **`Accepted #109 injected delivery v1, target <exact projectName>,
   result <result filename/hash>. Existing timelines unchanged.`** Or report
   the first mismatch/status and attach the local report reference.

## Refusal and recovery

A missing/mismatched/unverified/stale attestation, unsupported object/version,
collision or absent authorization stops before target creation. Bootstrap
integrity failures retain `bootstrap-refusal-<run-id>.json` when the private
evidence directory is available; otherwise retain the printed Console error.
A save/reopen/verification failure retains the named partial project and a
discrepancy report. A started record names the intended target even if Resolve
or disk fails before a final report can be written. Inspect partial targets
manually; never promote one to native success or auto-delete/reuse it.

Before another build, verify the package again into a **new attestation**, which
selects a new unique target, and prepare a new authorized request. Do not weaken
version gates, enable external scripting as a fallback, overwrite evidence or
rerun the same build request expecting target reuse. Evidence directories must
be outside the ready package. Full-file rehashing is intentional; keep the
package stable and avoid editing it during a run.

The prepared deliverable and automated checks are agent work. Manual
installation, the specifically authorized native run, version calibration and
Producer acceptance remain outstanding until retained real evidence exists.
