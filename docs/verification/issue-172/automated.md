# Issue #172 automated verification

## Scope and pins

- Worktree base: `3464c35deb652c1bdabd252917f85ecca9c83904`.
- Accepted design: #156 plan `e32727f0c0e65dc5a8561e0f470ed28e59bd1809`;
  #56 ordered visual contract `9e2b8817ffe97fbc9d6fcf31099aca578c5022bb`;
  #127 successor handoff `cdaa3106da91fb5a040c8bbde22e2c61c0d3e162`.
- Runtime: Node `v24.19.0`, npm `11.17.0`; package manager and dependency
  graph are pinned by `package.json` and `package-lock.json`.
- Locked Node binary SHA-256:
  `f7413632aa5c8cfc985a96fbc963a7a9e76204ea4e61970927dfb78ae6c9f365`.
- `package-lock.json` SHA-256:
  `553e3c49edca2f76c784b6f6199cc86997f0ee9d2c14fdb26d73064232d997a0`.
- Frozen schema/type inputs were not edited. Their SHA-256 pins at verification:
  `script-document-v2.schema.json`
  `1b490aece5f9e99743035935a503b966c00bf1a415b8ae530184f8f87b34d2d1`,
  `compiler-dependencies-v2.schema.json`
  `886c8bbc1b2666bbb35dfc764b33160d9daf4c8b4f31fba466cc0ff84069d3d3`, and
  `contracts-v2.ts`
  `2d2c0cec6734cad5d73d862047afd1723a84ac6fa4bd918b8be8ab5efee6bde8`.

## Passing focused commands

Each command ran from the repository root with the locked runtime directory
prepended to `PATH` and through the repository `ctx-wire`/`rtk` command path:

```sh
npm run test --workspace @vera/contracts -- test/authoring-v2.test.ts
npm run lint --workspace @vera/contracts
npm run typecheck --workspace @vera/contracts
```

Results: 17/17 authoring-v2 tests passed; contracts ESLint passed with zero
warnings; contracts TypeScript typecheck passed. `git diff --check` passed.
The synthetic suite covers ordered continuous roots, reversed B-roll parent
coverage, returns/resume state, independent crossing overlays and primary-first
ties, exact token anchors, insert/convert/flatten/swap/delete/cross-row repair,
complete-clip modes and fallback estimates, Unplaced identity/lineage, and
exact two-of-three placement resolution/refusal.

## Additional package-suite observation

The extra command `npm run test --workspace @vera/contracts` ran 284 tests:
282 passed, while two existing #144 CLI/omission-bridge tests exceeded their
default five-second per-test timeout during the package-wide run. No #144 test
or timeout was changed. This is retained as an observed package-suite failure,
not a passing acceptance command. The parent task owns the repository-wide
validation and any targeted rerun of those existing tests.

## Exact source hashes

SHA-256 at the focused passing check:

| File | SHA-256 |
| --- | --- |
| `packages/contracts/package.json` | `3bccf26b478f38cfa844a66b1cffeecb7ef8bfd09e88e5cd973af7a36ebf06a3` |
| `packages/contracts/src/authoring-v2.ts` | `2f1f6ff480ee94ae329b4467250be646fd5a143acb42ce28444636c403d3d208` |
| `packages/contracts/src/authoring-v2-validation.ts` | `e201fedb07c299966bb363c034bf941466832b263644e25a6fbed318a3880cd5` |
| `packages/contracts/src/authoring-v2-projection.ts` | `567ed6116aadc98aaa3dfbf548bb5eba10baec8bbe880a80e638d53153be648d` |
| `packages/contracts/src/authoring-v2-placement.ts` | `d6e666424e49bbd7f30b86806ac54850aabd2cd95889bb9c497adbd02e9b5161` |
| `packages/contracts/src/authoring-v2-edits.ts` | `ee1a8b5cec9d2a9130b1f79017dcad85c74b519938ce624c0703d12289dd9722` |
| `packages/contracts/test/authoring-v2.test.ts` | `66b8bf667ec2db2add85bff98c872feabf511de79b37ba8cc4d3f1d0abefca46` |

No new dependency, schema, generated type, existing fixture/golden, UI,
persistence, compiler, media, native-application, or external-service change
was included. The P3 edit result is a local canonical revision with operation
evidence; application/persistence callers own acknowledgement and advancement
of the live collaboration snapshot fields.
