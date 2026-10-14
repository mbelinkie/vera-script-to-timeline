# #208 prepared operator handoff

Status: code review GO; installation, operator authority, real identity capture,
#204 capability preflight and final full validation remain held. No helper has
been executed. No real authority/request exists. This handoff is not a grant.

Reviewed behavior: `1b49081fe40271695a91e9136f3f6106332f8da4`.
Actual Opus 5.5/high result SHA256:
`24eecea00521cab681e2daa0506b7c7abd97d473233c2bfbeed7ef188005b67b`.
The two subsequent runtime comment edits have identical reviewed ASTs;
[handoff.json](handoff.json) records their raw hashes and the complete source
and installed inventories. Added tests change no runtime behavior.

Prepared release:
`/Users/matthewbelinkie/.codex/worktrees/3754/VERA Script to Timeline/out/issue208/release-r2`.
Its `vera-delivery-v2/release.json` SHA256 is
`221b5060fe704a04bd28d76f789850c500f32b837b2c7b27b8bfbb445e102695`.
The release contains `VERA Delivery v2.py` and `vera-delivery-v2/`.
The old #204 release is stale. Do not merge these folders with an old release.

Private attempt root, not yet created:
`/Users/matthewbelinkie/Library/Application Support/VERA/private-preparation/issue-208/operator-attempt-01`.
Host authority/request files will be under `host/`; results will be under
`identity-evidence/` and later `capability-evidence/`. Keep these files private.

1. The coordinator grants installation/runtime use of this exact release on
   Studio 21.1.1 build 10. The operator personally opens an already-saved,
   disposable NONproduction project and timeline, supplies their exact visible
   names, and confirms read-only operation with External Scripting **None**.
   Existing research/production targets and neighboring plugins stay untouched.
2. Personally run [01-prepare-identity.command](01-prepare-identity.command)
   from this folder. It verifies pinned source/release bytes, prompts for the
   two names, operator name and confirmations, then prepares separate immutable
   identity authority/request files. It neither installs nor invokes Resolve.
   Record both raw SHA256 values. Keep the host originals and prepared lineage.
3. Quit Resolve. Follow the accepted [#109 manual installation flow](../../../resolve-workflow-integration-v1.md#manual-installation-and-update),
   substituting only this v2 launcher/subtree and identity request. Archive old
   v2 entries together outside the plugin root before copying the new complete
   release. Install under
   `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins`.
   Copy `host/identity-request.json` as `vera-delivery-v2/request.json`.
   Compare every actual installed source hash with `handoff.json`, plus the
   release-manifest hash above and the installed request against its host hash.
4. Authority/request/evidence parents must be private mode 0700. The installed
   request must be regular, single-link, mode 0400 and owned by the user running
   Resolve. A root-owned 0400 copy cannot be read by that user. Release files
   and retained repository/evidence locations must be readable by Resolve
   without an unattended macOS permission prompt.
5. Restart Resolve, reopen the same saved target and independently confirm its
   visible names and the None preference. Launch **Workspace > Workflow
   Integrations > VERA Delivery v2** once, with no concurrent UI/jobs.
   Inspect the original private `bootstrap-started-<UUID>.json`,
   `controller-started-<UUID>.json`, `result-<UUID>.json` and
   `hashes-<UUID>.json`. Expect `identity_observed`, two agreeing complete
   name/UID reads, actual runtime/build and all qualification/effect flags
   false. Console prints or a stopped/partial result supply no usable receipt.
6. Independently inspect all four returned identifiers and the saved result
   hash. In a separate host invocation, personally run
   [02-confirm-identity.command](02-confirm-identity.command). It verifies pins,
   derives the receipt paths/hash, asks for fresh confirmations and runs the
   CLI that displays all four identifiers and requires typing `CONFIRM`.
   The CLI validates the original lineage and reserves a one-use consumption
   marker before issuing capability authority v2 and its separate request.
   These confirmations are procedural provenance, not human authentication.
7. Within the receipt's 30-minute window, quit Resolve and archive the installed
   identity request outside the inventory. Preserve its host original and all
   identity evidence. Copy `host/capability-request.json` as installed
   `vera-delivery-v2/request.json`, retaining the required ownership/permissions
   and comparing raw hashes. Restart and personally reopen/confirm the SAME
   saved target. Launch v2 once. #204 independently matches all four live
   identifiers before capability reads; no build or render is authorized.
8. Return actual identity and capability result/hash paths, installed inventory,
   runtime/build, independent confirmations and unchanged-target evidence to
   the coordinator. Report the first refusal or unsupported/ambiguous fact.
   These results enable the remaining runtime assessment and final full gate;
   the issue stays open until all External criteria pass.

Expiry, mismatch, clock uncertainty, collision, crash or partial publication
requires a fresh attempt with new authority/invocation/request/evidence paths.
Preserve old files and markers. Never reset a reservation/consumption marker.
The helper paths are pinned for attempt 01 and must be freshly prepared for a
later attempt; do not edit/reuse them to defeat an exclusive-output refusal.

The detailed [operator checklist](../operator-checklist.md) retains the exact
acceptance limits. Saved/nonproduction/None are operator attestations. Adjacent
getter reads cannot exclude every intervening edit or switch preserving UIDs.
