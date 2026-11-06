# Companion setup/readiness/recovery — Q1 core (#158)

This command is a read-only local diagnostic, not a pairing service, installer,
Resolve preflight or build authorization. It inspects the installed versioned
Workflow Integration release, an operator-approved ready-package root and
operator observations, then publishes one immutable report whose `canBuild` and
`nativeVerified` are always `false`. The accepted native boundary is
[the injected delivery runbook](resolve-workflow-integration-v1.md) (#109):
its versioned release, independent verification, manual install, operator
request and explicit new nonproduction target are unchanged.

The command never calls Resolve, imports the shipped runtime, installs or
repairs scripts, edits preferences, starts a service, checks network health,
pairs credentials or writes inside the installed release/ready package. It
scans only `vera-delivery-v1/` or `vera-delivery-v2/` plus that version's
top-level launcher, exactly like the shipped launchers; other plugins sharing
the Workflow Integration Plugins root are not owned or reported.

## Inputs

Quit Resolve before manually installing or updating a release. Choose the
approved release version (1 or 2) and obtain its exact SHA-256 from the
prepared, trusted `release.json`, not from a newly found folder. Keep the
policy and observation files private; both contain local locators.

Policy JSON keys (no credentials or signatures):

```json
{
  "schemaVersion": "vera-companion-policy/v1",
  "releaseVersion": "1",
  "releaseSha256": "<64 lowercase hex>",
  "approvedRoots": ["/private/local/approved-root"],
  "approvedTools": ["resolve:injected"]
}
```

Observation JSON keys:

```json
{
  "packageRoot": "/private/local/approved-root/ready-package",
  "pairingState": "unknown",
  "serviceState": "unknown",
  "restartRequired": false
}
```

`pairingState` is `unknown`, `unpaired` or `paired`; `serviceState` is
`unknown`, `disconnected` or `connected`. `packageRoot` may be `null`. These
are untrusted operator observations, not an authenticated pairing or proof that
Resolve is open. Only the accepted real service's own evidence can establish
pairing once one is implemented; never paste credentials here. `unknown` is
treated as not paired/not connected.

## Record one report

Create the private evidence directory first; the command creates only the
report file, never parent directories. Create it outside the installed plugin
root and outside the ready package. From the repository with the locked Python
environment:

```sh
mkdir -p /private/local/evidence
uv run --frozen python -m vera_timeline_agent.companion_readiness_cli \
  --installed-root "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins" \
  --policy /private/local/policy.json \
  --observation /private/local/observation.json \
  --output /private/local/evidence/first-run.json
```

Use a new output filename for each check; an existing report is never
replaced. The report is written read-only and must stay outside the installed
release and the selected ready package. The output path must be absolute, must
not contain `..`, and must not be a symlink. The installed root must not
contain `..` and must not be reached through a symbolic link; pass its
canonical path. Do not publish policy or observation JSON; the report omits
their local locators. Its release hash is an operator-selected version hint,
not a signature or remote authentication.

Exit status is `0` for a retained report and `2` for a refusal (unsafe output,
malformed policy/observation, unsafe path). A validation refusal writes
nothing and creates no directory.

## States and operator recovery

- `first_run`: no versioned install was found. Quit Resolve, manually install
  the matching versioned release and restart Resolve.
- `incompatible_version`: another release version, including a newer
  `vera-delivery-vN/`, or an unknown release schema/source pin is installed.
  Retain the old version, manually install the approved compatible release as
  a complete unit and restart Resolve. Never merge source folders.
- `repair_required`: the trusted manifest digest, a declared source file,
  file inventory, directory inventory or symlink check failed, or the install
  is partial/malformed. Do not run the installed script. Preserve existing
  reports, quit Resolve and manually reinstall a clean approved release. No
  automatic repair is attempted.
- `approval_required`: the selected package root is missing, is a symlink, or
  is not inside an approved, non-symlinked absolute root. Choose an existing
  approved root and the supported `resolve:injected` tool; never broaden
  filesystem or tool access automatically.
- `restart_required`: restart Resolve after the operator's update, then rerun
  this diagnostic and its native preflight.
- `unpaired`: no trusted pairing observation exists. Use only a separately
  accepted authenticated pairing flow; this diagnostic does not implement one
  and cannot authenticate an observation.
- `disconnected`: the service is not observed as connected. Inspect the
  accepted service and reconnect manually, then recheck. Never replay a build
  whose effect is unknown.
- `native_preflight_required`: the installed release and approved package
  match. Launch the actual #109 injected preflight manually in a disposable
  current Resolve project, with the documented External Scripting `None`
  confirmation and a verified ready package. This state is not a build
  authorization.

## Native evidence remains #109's

This diagnostic intentionally does not read or bind `request.json`; the
launcher remains the authority for the operator request, so a missing or
stale request is refused at native launch even when this report reaches
`native_preflight_required`. Keep the native started-, result-, hashes- and
partial-target reports exactly where the #109 runbook specifies. A retained or
uncertain partial target is not success; do not delete it, overwrite it, retry
blindly, or infer that a browser/local action drove Resolve. A report from this
diagnostic is point-in-time operator guidance only; the shipped launcher
remains the authority for installed source bytes and the native request.

The actual-application walkthrough stays operator-owned and is not replaced by
these synthetic checks: first-run, update/version mismatch, roots/refusal,
restart, disconnection, pairing, native preflight, one explicitly authorized
fresh named nonproduction target, and inspection of a stopped partial build.
Record real versions and outcomes.

## Deferred Q2 scope

Q2 signed/notarized installers, the supported OS matrix, platform
qualification, auto-update and support packages require a separate platform
choice and are not authorized by this diagnostic. It also does not add a
companion daemon, speculative pairing endpoint, automatic reconnection,
package-manager operation or new desktop architecture.

Source references: #107 injected-runtime source
`c9614eaf7bf7aa88f4cf33e77180ff5a393377e4`; #109 accepted source
`8ef9f864acafbfa77ace5f3c699ef5cfb0e6ecb7`; #147 source
`75029de57baa594d3dfc7f509a09cfc21943e088`.
