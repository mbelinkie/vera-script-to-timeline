# Issue 109 — Claude antagonist review and disposition

The required Claude CLI review ran read-only, with tools and MCP disabled,
against tested commit `8afb26e0af4c22b6fe382b003a847e6abde118b3`, baseline
`5d59b2ad560aa18f96554b71fe34ee5b7f30dfed`. It received the authoritative
issue, exact diff, connected adapter/verifier source and retained check outputs.
CLI completed successfully and returned **changes required**, not acceptance.
The full findings are retained in [claude-8afb26e.md](claude-8afb26e.md).

Raw local evidence in `out/issue109/`:

| File | SHA-256 |
|---|---|
| `claude-review-8afb26e.json` | `d88d50a00b08da6d446da680841643447bae8a85646c2e5aa7eb23ebb56a0b21` |
| `claude-context-8afb26e.md` | `bcf52480e1e933d1284019398a313b20fd959fd05b203a7be2774059b64faa32` |
| `validate-full.log` (530 passed, 46m59s) | `38354a960c7940826896a0c20e296eb5b2731ffc1c8de6c2894643fba472109c` |
| `validate-fast.log` | `f670080b35b006d1738fa4e12f7581a19fd936514ff5eb8eace6629ee19f6533` |

## Disposition

| Finding | Correction and regression evidence |
|---|---|
| F1, P2: current project drift can save an existing project | Capture created project/timeline unique IDs; require those current IDs before each stage and immediately before save/close. Reopen requires the original IDs and exactly one timeline. Tests refuse an unrelated current project, a switch after save, a wrong reopened project and extra timelines; the runbook forbids interaction until the result appears. |
| F2, P2: extension modules / prefix bytecode can bypass the source inventory | Require the complete installed file and directory inventory, rejecting undeclared files, extension modules, symlinks and empty cache directories. Reset `sys.pycache_prefix` and disable bytecode writes before import. Tests include `.so`, non-Python files, empty directories and an external prefix-cache payload. |
| F3, P2: cached same-path runtime can falsely stamp an updated release | Refuse every already-loaded `vera_timeline_agent` module. Tests relaunch in the same interpreter and require a restart refusal; the documented update and preflight/build flow already requires restarting. |
| F4, P3: request names are not bound to authorized target | Require exact verified project/timeline/root identity and literal action/boolean types before delivery. Tests cover mismatched names, invalid action and non-boolean authorization. |
| F5, P3: hash/read split can parse different bytes | Read attestation and release once, hash and parse the same bytes. Also pin request bytes across bootstrap/runtime and hash/parse them once. Tests replace attestation bytes after the read and alter a request after bootstrap. |
| F6, P3: storage failure can hide the native outcome | Print the complete result before final result/hash storage. Tests fail the final write and retain the named partial-target discrepancy result in Console output; started evidence remains. |
| F7, P3: raw path comparison can produce false discrepancies | Resolve both paths using the same normalization as the accepted import adapter. Tests verify a normalized path and preserve wrong-source detection. |
| F8, P3: extra timelines/media outside expected locations can escape readback | Require one reopened timeline and walk every media-pool folder, rejecting non-timeline media outside the expected package folder. Tests cover extra timelines and out-of-folder media. |

Additional review gaps have focused coverage for package drift after import,
event placement and the first marker; adjacent unsupported builds; the six-file
shipped runtime under Python `-S`; and the installed launcher with a verified
attestation and fake injected API. These are automated evidence only.

These dispositions require passing final checks and a new Claude review of the
fixed commit. Final outputs are retained locally as
`validate-fast-review-fixes.log`, `validate-full-review-fixes.log` and
`claude-review-<commit>.json`; the roadmap acceptance handoff records the exact
revision, hashes and outcome. No native walkthrough proceeds until that review
passes. No source changes follow that review without renewed checks/review.

## Remaining Producer evidence

The second Claude review of `981c00322ce502a6b6dff36646c3383963a9ab8c`
confirmed F1–F8 resolved and required one narrow operator-flow fix (N1).
Its full findings are retained in [claude-981c003.md](claude-981c003.md).
N1 now ignores only regular `.DS_Store` files in the installed release after
rejecting symlinks/nonregular entries; a regression test covers metadata in
both the release root and Python package. Ready-package inventory remains
strict, and the runbook warns against browsing it in Finder before building.
N2 also has a fix/test: skip missing tracks in the subclass's additional source
end readback, preserving the accepted base adapter's discrepancies.

N3 stays at the documented one-launch-per-authorized-request operator boundary;
durable replay/job ownership remains outside #109. N4's retained-partial flag is
conservative after entering the mutating creation stage; a collision can leave
no target, and the error detail must be inspected. Neither finding permits
reuse, overwrite or deletion. A full fake native build was not added: isolated
adapter/sequence tests and the shipped preflight cover agent-run behavior,
while actual assembly/save/reopen is the required native Producer gate.

Claude's Q1–Q7 remain native/operator questions. The run must retain the actual
runtime/version, External Scripting None screenshot, exact installed release
hash, new target identity, save/reopen/readback result and report hashes. The
Producer inspects the reopened target and confirms existing timelines unchanged.
Studio 21.1.1/10 remains a calibration candidate until this passes; Free parity
remains explicitly skipped under the accepted #34 exception. No installation
or native mutation has occurred during implementation or review.
