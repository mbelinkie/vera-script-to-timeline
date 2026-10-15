# Issue #8 — prepared operator artifact inventory

Prepared from reviewed code at `cbb20b5cfd3df997f1c5ae46259462ef212cfa7f`.
No source/test changes during full validation or artifact preparation.
All644Python cases passed in4318.87s, alongside439contracts/1tooling/
6progress/23roadmap/32cloud cases and lint/types/generated-currentness.
The original execution handle expired before terminal exit retrieval; no
direct exit-zero record is claimed. Preserve the passing log, but obtain
the verification policy's required durable exit-zero evidence before launch.

Full log: `out/issue8/validate-full-receipt-reviewed.log`, SHA256
`f2d26dffd627cd03b45da6615a5a5c5425ebd4bf1991ef3a53ffdde151ac930b`.
Original failed full log remains retained (47failed593passed), not relabeled.

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
settings confirmations. No installation, native project/composition/render,
visual judgment, deployment, merge or issue closure is claimed.

## Operator sequence after automated evidence and #219 release

1. Follow [injected delivery](injected-delivery.md): quit Resolve, manually
   install the two entries from the exact release above, leaving Delivery and
   other plugins untouched. This remains an operator-owned action.
2. Start with `standard-64-preflight.json`, copied as installed
   `vera-graphics-v1/request.json`. Confirm the actual None setting, save a
   disposable current project/timeline on Edit, then launch VERA Graphics v1
   once. Expect `preflight_passed` and the exact standard-64 target above,
   with no new project created. Retain the result or first refusal.
3. Report the preflight result and settings confirmation. Only explicit
   operator authorization of the exact nonproduction target permits a build
   request. Complete the seven-target [visual checklist](operator-checklist.md)
   after native verification. Never infer consent from preflight preparation.
