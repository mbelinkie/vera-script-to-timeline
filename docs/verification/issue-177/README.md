# Issue 177 evidence and adapter boundary

Adapter readiness evidence: **Claude R3 GO and complete local validation PASS**.
Acceptance authority: Automated. [PR #201](https://github.com/mbelinkie/vera-script-to-timeline/pull/201)
records CI and merge; [issue #177](https://github.com/mbelinkie/vera-script-to-timeline/issues/177)
records the final roadmap acceptance state.
Accepted starting main: `7867fa4873429e799f748004896f7093d2ce625f`,
tree `397d31ab7c0ab6b4f03cf4af7bd5abcce45bf3af`.

## Versioned caller handoff

`v2_package.build_v2_package` consumes the frozen v2 document, dependencies,
manifest and report plus explicit media/preparation inputs. It retains their
bytes and identities in a new immutable package; it does not reinterpret them
as v1. `verify_v2_package` independently verifies the package and OTIO readback.
The accepted v1 APIs and their imports remain separate and unchanged.

The saved document must use the accepted #189/#144 canonical-revision content
hash convention (compiler canonical JSON with only root `liveContentHash`
removed). Pure, unacknowledged authoring edits and the synthetic #173 sentinel
hash inputs are not eligible saved snapshots. This adapter does not qualify an
application snapshot writer; #157/#160 retain that integration boundary.
Temporary presenter stills with diagnostics, recovery or manual completion also
remain ineligible even when a report's status envelope says ready.

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

## Retained gates and external boundary

Synthetic tests establish adapter readiness only. `claude-r3-review.md` retains
the actual GO and its limits. `full-r1-summary.json`, `full-r1-input-audit.json`
and `full-r1-pass.txt` retain the complete pinned local validation: 794 Python,
430 Vitest and 61 Node tests, no skips or deselections, passing lint/types,
generator currentness and byte-identical accepted frozen boundaries. The tested
commit is `05256dca620e1e22d21d95281dc1436f630e4927`; subsequent changes retain
evidence and update this documentation, with fresh formatter/diff checks.
`r2-adjudication.md` and `r3-adjudication.md` preserve the saved-writer,
synthetic-fixture and compiler/runtime qualification limits. Required CI and
exact reviewed/tested-source correspondence still govern merge and closure. Native
fractional rates must not inherit integer calibration, and actual Studio
source-audio/framing/save-reopen/render claims remain #178's External gate.
No private media/text/paths, provider operations, research changes, render,
upload, sharing or #145 legacy-proof changes belong to this issue.
