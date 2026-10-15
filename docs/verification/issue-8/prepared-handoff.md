# Issue #8 — prepared operator artifact inventory

Prepared from reviewed code at `cbb20b5cfd3df997f1c5ae46259462ef212cfa7f`.
Complete final gate passed with retained **exit0** on clean commit
`f20681fd6e0dda4f2d4f6666169e9208adb49537`, tree
`0d96f3c23f4fadee91b7e19c12656cba85000aa3`; its source/tests/config/locks/
contracts/fixtures/integrations are byte-identical to reviewedcbb20b5. Only
non-consumed issue8handoff documentation changed. No source/test changes
during full validation, artifact preparation or post-run audit.

Command: `VITEST_MAX_WORKERS=1 PYTEST_ADDOPTS=--durations=25 npm run validate`,
Node24.19.0/npm11.17.0/uv0.12.5/lockedCPython3.12.14 on IntelmacOS15.1.
All644Python cases passed in3442.71s (57:22), including slow cases and no
skips/deselections, alongside439contracts in23files,1tooling/
6progress/23roadmap/32cloud cases, lint, mypy131files and generated-currentness.
Ruff checked425formatted files, including newly prepared release copies.

- Full log: `out/issue8/validate-full-durable.log`, SHA256
  `83ff16e2b192a552163aa6ec13f174ecc0994face63d0ce7e4bb5162a3b09adc`.
- Actual exit receipt: `out/issue8/validate-full-durable-exit.json`, value
  `{"exitCode":0}`, SHA256
  `3edd82d4e49f89c30270dee752ac018539f4dc6848d7a33b1553404e6f8b58af`.
- Claude receipt delta review: GO, no blocking findings; retained log
  `out/issue8/claude-review-receipt-delta.txt` SHA256
  `936ec18d2b56e049d9fd3a855466689c142dc7754377254cd33447c50721ca17`.

Original failed full (47failed593passed) and intermediate passing-suite log
with unknown exit status remain retained, not relabeled. The durable run
supplies that missing exit record; no further unchanged rerun is needed.
The check-in timer is disabled and #8's heavy host slot is released.

## Exact artifacts

Worktree: `/Users/matthewbelinkie/.codex/worktrees/46d4/VERA Script to Timeline`.
Paths below are relative to it.

- Release: `out/issue8/graphics-release-cbb20b5`.
- Manifest: `out/issue8/graphics-release-cbb20b5/vera-graphics-v1/release.json`.
- Release-manifest SHA256: `f955e0f46993028a951d3331f9ce6aaba0bd510134590b73e2e9c481c3956614`.
- Handoffs: `out/issue8/handoffs-cbb20b5/<case>/graphic.json` plus pinned `transport.json`.
- Preflight requests: `out/issue8/requests-cbb20b5/<case>-preflight.json`.
- Native output destinations: `out/issue8/native-evidence/<case>` (not evidence of a run).
- Complete attestation/request hashes: `out/issue8/operator-preparation-cbb20b5.log`.

The release's exact declared inventory and all11bundled source files were
hashed and byte-compared with the reviewed checkout, exit0. Its hash equals
the prior reviewed5d316be runtime release: the receipt repair is outside the
injected runtime. The exact new bundle imports under CPython3.14.7 `-B -S`,
exit0, without site-packages. This does not qualify real Resolve behavior.
Independent full-envelope and Transport attestation plus request preparation
for all seven cases completed exit0. No original package was modified.

## Exact new project and timeline targets

Each project and timeline share the name below, authenticated in its handoff.
Do not simplify names or reuse a failed target.

| Case | Project and timeline name |
| --- | --- |
| standard-64 | VERA Delivery 88000000-0000-4000-8000-000000000001 6066118d9c7d |
| overrides-64 | VERA Delivery 88000000-0000-4000-8000-000000000002 d859f645132f |
| otis-64 | VERA Delivery 88000000-0000-4000-8000-000000000003 eaa44a62260b |
| standard-120 | VERA Delivery 88000000-0000-4000-8000-000000000004 9b1c80470847 |
| overrides-120 | VERA Delivery 88000000-0000-4000-8000-000000000005 6e9651e4b3b2 |
| otis-120 | VERA Delivery 88000000-0000-4000-8000-000000000006 5f43e21ff89a |
| revised-120 | VERA Delivery 88000000-0000-4000-8000-000000000007 12ae4f507537 |

Every prepared request is `action: preflight`, `authorizeNewNonproduction:
false`, `externalScripting: null`. There are no build requests or operator
settings confirmations. The subsequent Producer-authorized file installation
is recorded below; no native project/composition/render, visual judgment,
deployment, merge or issue closure is claimed.

## Next operator sequence (automated evidence complete; #219 released)

1. File installation is **complete**, under the Producer's subsequent request
   for the agent to put these files in place. Resolve was closed; no existing
   Graphics installation required archiving. Only `VERA Graphics v1.py` and
   `vera-graphics-v1/` were copied into the documented Workflow Integration
   Plugins directory; Delivery and other plugins were untouched. All11declared
   files and release manifest compare byte-identical to the reviewed release.
2. The exact `standard-64-preflight.json` is already installed as
   `vera-graphics-v1/request.json` (mode0400; SHA256
   `6473916bf6102d3cf1448c2f2cb41a0425482cb603b3d16fc8f8656b2623addf`).
   Open Resolve. Confirm the actual None setting, save a
   disposable current project/timeline on Edit, then launch VERA Graphics v1
   once. Expect `preflight_passed` and the exact standard-64 target above,
   with no new project created. Retain the result or first refusal.
3. Report the preflight result and settings confirmation. Only explicit
   operator authorization of the exact nonproduction target permits a build
   request. Complete the seven-target [visual checklist](operator-checklist.md)
   after native verification. Never infer consent from preflight preparation.

The last operator-reported setting was External Scripting **Local** from #219.
No agent changed it or asserted None. File installation alone is authorized
and completed; settings confirmation and menu launch remain operator-owned.
Private installation receipt: `out/issue8/installation-receipt.json`.
Leave #219's disposable project unchanged;
save a separate disposable current project/timeline before preflight. The
preflight must report `preflight_passed` with the exact standard-64 target,
not `verified` or a newly created project. Return the actual result file or
first refusal before any authorized native build.
