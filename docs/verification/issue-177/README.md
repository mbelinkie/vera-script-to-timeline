# Issue 177 evidence and adapter boundary

Status: implementation in progress; **not acceptance evidence yet**.
Accepted starting main: `7867fa4873429e799f748004896f7093d2ce625f`,
tree `397d31ab7c0ab6b4f03cf4af7bd5abcce45bf3af`.

## Versioned caller handoff

`v2_package.build_v2_package` consumes the frozen v2 document, dependencies,
manifest and report plus explicit media/preparation inputs. It retains their
bytes and identities in a new immutable package; it does not reinterpret them
as v1. `verify_v2_package` independently verifies the package and OTIO readback.
The accepted v1 APIs and their imports remain separate and unchanged.

The package includes `Builds/<buildId>/delivery-view.json`, version
`resolve-native-view/v2`. This view projects ranges into the accepted native
placement interface while retaining each complete v2 event, source mapping,
audio policy, picture treatment and composition evidence. It is an explicitly
versioned adapter view, not a replacement compiler manifest.

Using locked CPython 3.12.14, the caller prepares a unique external attestation:

```sh
rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_v2_cli \
  attest <verified-package-root> --output <new-attestation.json>
```

The attestation binds the complete package byte inventory, all seven build-file
hashes, independent verifier source/schema hashes, counts and a fresh target
name. It must be outside the package. A changed package requires independent
verification and a new attestation; a retry cannot replace an earlier receipt.

The repository-owned v2 injected release is prepared with:

```sh
rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_v2_cli \
  release --output <new-release-directory>
```

This copies the hash-inventoried standard-library runtime, including unchanged
accepted #109 native helpers, and `VERA Delivery v2.py`. It performs no installation,
connection or native action. A read-only request is prepared with:

```sh
rtk proxy ctx-wire run uv run --frozen python -m vera_timeline_agent.workflow_v2_cli \
  request <attestation.json> --release <release-directory> \
  --output <new-request.json> --evidence-dir <new-evidence-directory>
```

The operator-owned installation and native authorization remain the accepted
#109 boundary and later #178/#190 qualification flow. Build requests additionally
require `--action build --authorize-new-nonproduction --external-scripting-none`.
The runtime rechecks hash-pinned inputs before each mutation, rejects target
collisions, saves/reopens the created target and retains discrepancy/partial-target
evidence. No target is deleted or overwritten by recovery.

## Gates still required

Synthetic tests establish adapter readiness only. Full qualifying validation,
generated/frozen checks and adversarial Claude GO remain pending. Native
fractional rates must not inherit integer calibration, and actual Studio
source-audio/framing/save-reopen/render claims remain #178's External gate.
No private media/text/paths, provider operations, research changes, render,
upload, sharing or #145 legacy-proof changes belong to this issue.
