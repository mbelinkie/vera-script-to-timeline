# #208 operator gate — prepared, real-app gate held

This is a checklist for the operator, not an installation or Resolve grant.
The [prepared handoff](operator/README.md) supplies the reviewed commit, new
release manifest SHA256, complete inventory, and concrete private paths.
The coordinator must supply the exact installation/runtime grant. No real
authority has been issued and no real target names have been supplied. #204's old prepared
release `d4ec949a...` is stale after these runtime changes.

1. Open the coordinator's exact reviewed handoff and compare its source and
   release inventory hashes. Use locked CPython 3.12.14 host preparation.
   Confirm the installation/runtime grant is for this exact release and #208.
   Keep existing plugins and the research/production projects untouched.
   Authority/request/evidence parent directories must be private 0700 and owned
   by the operator. Keep the installed request copy regular, single-link and
   mode 0400. Use repository/evidence locations that Resolve can access without
   TCC prompts. `--installed-root` must exactly spell the script's parent path;
   when Resolve omits `__file__`, use the bootstrap's declared plugin root.
   The installed request must be owned by the user who runs Resolve; root-owned
   mode-0400 copies are unreadable by that user. Release files must also be
   readable by that user. Preserve those permissions through the manual copy.
2. Personally select an already-saved disposable NONproduction current project
   and timeline in Studio 21.1.1 build 10. Supply their two exact visible names;
   invisible UIDs are not inputs. Confirm read-only operation and External
   Scripting None, with no concurrent UI/jobs during the attended capture.
3. Personally run `workflow_v2_cli identity-authorize` using the coordinator's
   exact release, intended installed root, retained CN-207-ID1 approval, private
   authority/evidence paths, names and three explicit confirmation flags.
   Prepare its separate `identity-request`. Retain both raw hashes and the
   original host request/authority and `prepared-<UUID>.json` lineage.
4. Follow #109's manual quit/archive/copy/restart flow for the complete reviewed
   plugin and immutable request. Independently compare actual installed hashes.
   Reopen the same saved target, confirm the names and None preference, and
   launch **VERA Delivery v2** once. No console/MCP/UI scripting fallback.
5. Inspect `bootstrap-started-<UUID>.json`, `controller-started-<UUID>.json`,
   `result-<UUID>.json` and `hashes-<UUID>.json` in the original private evidence
   root. Console prints, including the early failure print with `finishedAt:null`,
   are not consumable receipts. A successful result plus its complete retained
   hash lineage is required. Inspect the saved JSON files themselves.
   Expected: `identity_observed`, two agreeing complete name/UID reads,
   actual runtime/build, and all qualification/verification/effects flags false.
   A stopped result or missing hash lineage supplies no usable identity.
6. Personally compare the displayed names and UID pair with the selected target.
   In a separate host invocation, use `capability-authorize-from-identity` with
   the exact result/hash, retained CN-178-Q1 approval, new private capability
   paths, hash acknowledgement and fresh confirmation flags. The command
   displays all four identifiers and requires typing `CONFIRM`; it derives the
   target from the receipt. It reserves `consumed-<result SHA256>.json` before
   issuing one capability authority/v2. Request preparation cannot make this
   decision. Prepare the separate capability request only afterward.
   The flags, hash acknowledgement and typed `CONFIRM` are procedural operator
   provenance, not authentication; piping `CONFIRM` cannot prove human identity.
7. Within the attended 30-minute window, follow the required #109
   quit/archive/request/restart transition. Preserve the original identity host
   request and all evidence; archive the installed old request outside the
   installed inventory. Reopen the same saved target and personally confirm it
   again. Launch once. #204 must independently match all four live identifiers
   before general capability reads; no control/render effect is authorized.
8. Retain the actual capability report/hash and unsupported/ambiguous gaps, or
   the precise refusal. Confirm unchanged visible target/timeline/settings and
   no production target involved. Saved/nonproduction/None remain operator
   attestations, never API-proven facts. Adjacent reads cannot exclude every
   intervening UI switch or edit preserving UIDs.
9. Return actual identity and capability artifact paths/raw hashes, installation
   inventory, runtime/build, independent confirmations, and unchanged-target
   evidence to the coordinator. Runtime fixes require delta review and fresh
   applicable checks; final complete validation follows on delivered source.
   External acceptance stays open until these required gates pass.

Any expiry, mismatch, unexpected restart, failed/partial attempt, missing
lineage, collision or uncertain publication requires new authority, invocation,
request and evidence root plus fresh capture/confirmation. Preserve old files;
never delete/reset a reservation or consumption marker to retry.
