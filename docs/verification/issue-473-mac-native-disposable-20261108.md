# Issue #473 — real Mac Studio native disposable-project smoke (2026-11-08)

**Scope:** bounded test of the *official installed Resolve Studio 21.1.1.10 SDK*,
fresh synthetic target provisioning, actual native project/timeline save and
subsequent load/UID readback. This is **not** the M4 edited roll, movie/PCM,
or #312 final acceptance. Producer's latest instruction in the #473 context:
"Do the native tests". No historical native operation was retried.

## Exact source and admission

- New dedicated Mac code worktree `/tmp/vera473-native-20261108`, checked out
  from the original draft PR #474 at `5409145f`. The user's main checkout,
  dashboard edits, and earlier #473 worktree were not changed.
- Real application started via `open -a`; installed bundle
  `CFBundleShortVersionString=21.1.1`, `CFBundleVersion=21.1.10010`.
  Installed `DaVinciResolveScript.scriptapp("Resolve")` returned an authenticated
  connection with `GetVersionString() == "21.1.1.10"`. Resolve started at
  `Project Manager` with no selected project, not on an earlier #312/#473 target.
- Fixed a narrow fresh-disposable preflight refusal for this safe Project
  Manager case in `resolve_native_owner.py` (`5409145f`); current-project
  rendering, target-name collisions and selection races continue to fail closed.
  **95 focused tests passed** (owner + provision), strict mypy and Ruff green.
- Separate private one-use root:
  `~/.local/state/vera/issue-473-native-20261108-2319/provision`.
  Exact plan SHA-256:
  `d1bf148f4c5315698ab43047b2120e5eee6176c10caea83d20e9b4cdf2aa1612`.
  This root was fresh, distinct from the prior expired #473 campaign.

## Native calls and independently retained identities

| Stage | Fresh project/timeline name suffix | Native project UID | Native timeline UID | Result |
| --- | --- | --- | --- | --- |
| initial | `8137fcd2-ceed-45d8-bbd2-c74aefd4cf4a f5ee01d06340` | `0fddcda6-8643-43a7-9672-4ac9714c803d` | `486a2660-877a-4ee0-ace7-32c77a6a9fc1` | `stage_verified` |
| fresh | `ae42811f-abfb-494a-88b0-deebac87776c da60daadab48` | `e138ca28-746f-4767-a3bc-8899fadcdaf4` | `191712b8-322d-4c60-a3cc-cf7722b64e08` | `stage_verified` |

Each project was created only after its own write-once pre-effect journal,
had a native empty timeline at 23.976 fps, and was genuinely saved. The
completion receipts are retained privately and are distinct:

- `complete-initial.json` SHA-256:
  `5f4f2b2f6bce6347457c64bcfc07e73419888867f1029e613b130cd5eed29efd`
- `complete-fresh.json` SHA-256:
  `7d3d28a9fbb0ab5e04ac0a34ad2779f2c30275008021698a5486764665045bfa`
- `intent-initial.json` SHA-256:
  `1365475d77dd31c575e137d179b49a982ec0259bfffd8f678e6eb54591bf03a7`
- `intent-fresh.json` SHA-256:
  `bb292700335259e34752d1843e9b4049094b3c89f622c5acdfe6a09a11073094`

Post-save `status` returned `targets_provisioned`. Both separate load/UID
checks returned `selected_verified` (`select-initial`, `select-fresh`,
`select-initial`), ending with the initial target selected. A further
`advance` returned `{"state":"targets_provisioned","created":false}`,
demonstrating no third native creation or reenrollment.

Read-only System Events preflight: frontmost Resolve window matched the exact
initial synthetic target; `Roll`, `Auto Select/Deselect V1`, and
`One Frame Right` menu entries were enabled; no modal sheet was present.
This does **not** prove the fixed keyboard preset or grant a GUI-operation
receipt. No 24-frame GUI roll, edit, render, PCM, inferred revision, or
original M4 receipt was attempted or fabricated.

## What this test does not unblock

- The new targets are **empty**, not the accepted eleven-item/six-track
  pristine fixture. The #473 one-start runner still returns a code-only
  F1/edited-stage blocked status; it has not generated genuine signed pristine
  evidence and cannot safely dispatch the GUI actuator on these empty targets.
- The old campaign remains an expired 3/4 M4 receipt state with missing
  rebuild acceptance. It was never used here; its project/operation/deadline
  must not be replayed.
- Complete trusted SDK inventory + exact macOS TCC/window/preset/F1 integration,
  original M4 signed receipts and save/reopen + official SDK UID evidence, real
  decoded MOV/PCM, independent review and green CI remain necessary.
- Therefore **PR #474 remains draft; #473 stays open and #312/#313 remain
  blocked**. The two new immutable disposable test journals are preserved
  for future read-only inspection, not a license to restart or invent effects.
