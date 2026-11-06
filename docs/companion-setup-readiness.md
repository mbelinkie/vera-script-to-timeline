# Companion setup, readiness, and bounded recovery (Q1 diagnostic)

Issue [#158](https://github.com/mbelinkie/vera-script-to-timeline/issues/158).
This is a **local read-only diagnostic**, not an installer, background companion,
pairing service, job runner, or authorization to operate Resolve. It inspects
the installed, versioned [#109 injected Workflow Integration](resolve-workflow-integration-v1.md)
and an operator-selected package directory, then publishes one immutable,
path-sanitized JSON report and a suggested next action. No Resolve process,
network connection, package-manager command, project, or media file is opened
by this diagnostic. A report **never** proves an authenticated connection,
native preflight, build, or recovered timeline.

## Boundary and prerequisites

- Use the repository's locked CPython 3.12 environment
  (`uv run --frozen`). You must already have a separately prepared and
  authorized **v1 or v2** injected release. This diagnostic does not copy
  files into Resolve or produce an attestation. The release builder is
  `vera_timeline_agent.workflow_delivery_cli release` for v1, or
  `vera_timeline_agent.workflow_v2_cli release` for v2. The v2 output,
  precision, and import variants have distinct manifests; use the exact
  variant's prepared `release.json` SHA-256.
- The operator, not this CLI, selects the installed Workflow Integration
  Plugins root, the exact expected `releaseVersion` (`"1"` or `"2"`),
  and the **SHA-256 of that prepared release's `release.json`**. The hash
  pins the chosen release inventory; a digest placed in a local policy is
  **not** a signature, authentication, or independent approval.
- The operator also selects approved local package parent directory/directories
  and the only supported tool `resolve:injected`. This selection is a
  diagnostic constraint, **not** permission to import from the package or
  execute code. The ready package's own attestation and authorization remain
  mandatory in the native #109 flow.
- Installed release source, request, ready package, attestation and native
  result/hashes records must be kept separately. The diagnostic only reads
  the installed release's manifest and declared source bytes; it does not
  inspect media contents. Unrelated plugins in the same installed root are
  outside its inspection boundary. The selected release's undeclared files,
  empty directories, and symlinks are refused.

## 1. Prepare a private local observation

First quit Resolve before any **manual** installation or replacement. Follow
[#109's installation/update instructions](resolve-workflow-integration-v1.md#manual-installation-and-update):
archive the two old versioned entries together **outside** the plugin root,
copy the prepared versioned launcher and folder, and restart Resolve.
Never merge old/new source folders, delete other plugins, reuse old bytecode
caches, or place a report within the installation.

For macOS, the installed root normally is:

```text
/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins
```

Hash the prepared `vera-delivery-v1/release.json` (or v2 equivalent) with
`shasum -a 256`, and compare it with the installed manifest. Record the
approved expected digest in a private `policy.json` (absolute paths, not
tilde abbreviations); replace all example paths/digest before running:

```json
{
  "schemaVersion": "vera-companion-policy/v1",
  "releaseVersion": "1",
  "releaseSha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "approvedRoots": ["/Users/operator/VERA/ready-packages"],
  "approvedTools": ["resolve:injected"]
}
```

Create a separate private `observation.json`. **These fields are operator
assertions, not proof of a secure pairing or live service.** Use `"unknown"`
when not verified; do not invent a pairing session, service endpoint, token,
or credential. A selected package root must be an existing, non-symlinked
directory inside one of the approved roots.

```json
{
  "packageRoot": "/Users/operator/VERA/ready-packages/sample",
  "pairingState": "unknown",
  "serviceState": "unknown",
  "restartRequired": false
}
```

Allowed pairing states: `unknown`, `unpaired`, `paired`. Allowed service
states: `unknown`, `disconnected`, `connected`. `restartRequired` is a
JSON boolean. `packageRoot` may be `null` when none has been selected;
this yields `approval_required` after a valid installed release is found.
The observed `paired` and `connected` strings do **not** imply an
authenticated protocol. No credential should go into these JSON files.

## 2. Run the diagnostic and retain its evidence

Run the following from the repository root, pointing to the installed
**plugins root** (not its `vera-delivery-v1` child). Select a new, private
report filename outside both the installed plugins root and the ready
package every time. The command will not overwrite an existing report.

```sh
uv run --frozen python -m vera_timeline_agent.companion_readiness_cli \
  --installed-root "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins" \
  --policy "/Users/operator/VERA/private/policy.json" \
  --observation "/Users/operator/VERA/private/observation.json" \
  --output "/Users/operator/VERA/private/readiness-001.json"
```

On success, stdout prints the report path and `sha256:<digest>`. Record
the report's hash, chosen release digest, UTC collection time, and the
operator's installation/version observations in a **private operator log**.
The report itself contains only `schemaVersion`, `state`,
`deliveryVersion`, `releaseSha256`, `nextAction`, `canBuild: false`,
`nativeVerified: false`, and
`evidenceKind: read_only_local_diagnostic_operator_observations_untrusted`.
It intentionally omits approved roots, package paths, pairing identifiers,
secrets, media locators, and raw native evidence. The file is published
read-only (owner-read) and without overwriting prior evidence. Protect the
containing directory too; do not publish local policy, observation, raw
report, or native result files.

An invalid schema, malformed policy/observation, unsafe report destination,
or existing output returns a refusal (CLI exit code `2`), not an
authoritative readiness state. Keep the original file intact and use a new
report path only after correcting the input. Never rewrite an earlier report.

## 3. Classify and act — no automatic repair

The diagnostic prioritizes release absence/version/source integrity before
package-root/tool approval, restart, pairing, and service observations. In
every row `canBuild` and `nativeVerified` remain **false**.

| Report state | Example / required human recovery |
| --- | --- |
| `first_run` | No installed selected release. Quit Resolve; manually install the prepared injected launcher and folder; restart, then collect a new report. |
| `incompatible_version` | Only the other release version is installed, or the installed release declares an incompatible version/source pin. Quit Resolve; archive and replace the selected version as a pair using the approved prepared release. Do not silently downgrade or merge folders. |
| `repair_required` | Wrong manifest digest, edited/missing/undeclared source file, symlinked installed path, empty directory or cache in selected release. **Do not launch it.** Preserve current evidence; quit Resolve; manually replace the entire selected release and rerun the hash check. Never auto-clean or patch one file. |
| `approval_required` | Selected package missing, outside an approved root, or root/tool not approved. Select a real local directory under an explicitly approved non-symlinked root with only `resolve:injected`; do not grant shell or wider access. |
| `restart_required` | Operator observed a changed install/settings that still needs restart. Restart Resolve manually, set `restartRequired` to `false` only after doing so, and capture a new report. |
| `unpaired` | Pairing state is unknown or unpaired. Use only a separately accepted **real** service-pairing procedure, if available; otherwise leave unpaired and escalate to its interface owner. Do not copy credentials into observations or pretend this diagnostic pairs. |
| `disconnected` | Pairing was claimed paired but service is unknown/offline. Check the separately accepted companion service manually; if none exists, do not claim connected. Reconnect using its own approved interface and recheck. Never replay a possibly partial build. |
| `native_preflight_required` | Installed source, selected root/tool and *operator-observed* restart/pair/service checks passed. This is **not Ready**, native success, or build authorization. Proceed only to the separately attested, explicitly selected **#109 native preflight** flow. |

For a first-run walkthrough: with no installed selected release, collect
`first_run`; after a manually installed wrong version, collect
`incompatible_version`; after a correct install but without an approved
package/root, collect `approval_required`; after selecting the package,
record `restart_required` until Resolve is restarted, then `unpaired`
or `disconnected` until a real accepted protocol provides evidence. A
claimed `paired/connected` observation leads **only** to
`native_preflight_required`. For any corrected state, run a **new**
diagnostic to retain the transition instead of overwriting a prior report.

## 4. Separately verify native preflight and partial outcomes

Only the accepted #109 native adapter handles actual preflight and any
operator-authorized nonproduction build. Follow
[the v1 preflight/request/runbook](resolve-workflow-integration-v1.md#preflight-and-exact-producer-authorization)
or the appropriate v2 accepted release/request flow. In the injected route:

1. Independently verify the **ready-package attestation** and the chosen
   installed release; prepare a **preflight** request under the corresponding
   `vera-delivery-v<version>/request.json`. Check the exact source digest,
   version, current disposable project and scripting setting using the
   native workflow's rules. Do not derive native authority from this report.
2. With Resolve in the required supported configuration, open a **disposable
   nonproduction** project/timeline and launch the installed
   `VERA Delivery v<version>` Workflow Integration once. Preserve
   `started-<run-id>.json`, `result-<run-id>.json`, and
   `hashes-<run-id>.json` in its separate private evidence directory.
   Confirm actual version/build, preflight status, request/release digest,
   unchanged current target, and native timestamps; never infer them here.
3. If the native operation refuses, the result is missing, or the target
   might be partially created, **stop** and inspect the retained native
   result, bootstrap refusal/console, request and started/hash records
   together. Preserve the named partial project for inspection. Never
   auto-delete, overwrite, promote, or replay a possibly applied build.
   Recheck the package, prepare a fresh attestation and *new* named
   nonproduction target before any separately approved retry.

The optional v2 guarded parent workflow and its `live`/`unknown`/`failed`
states have separate rules in [v2 parent delivery](resolve-parent-delivery-v2.md).
This companion diagnostic neither starts nor resumes that worker.

## Deferred and unverified

This phase proves deterministic state classification on **actual v1/v2
release-builder outputs** plus synthetic adverse observations. It does
**not** provide or claim a real Resolve installation/restart/pairing
walkthrough, authenticated service observations, native preflight evidence,
or Producer acceptance. Capture those only in a separate operator-run
native acceptance activity. No automatic OS installer, signed/notarized Q2
bundle, updater, uninstaller, support bundle, Electron service, or
background reconnect is included. Those require separate product/platform
selection and evidence; #116 retains UI design, #157 build-stage composition.
