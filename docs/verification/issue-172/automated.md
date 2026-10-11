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

Results: 20/20 authoring-v2 tests passed; contracts ESLint passed with zero
warnings; contracts TypeScript typecheck passed. `git diff --check` passed.
The synthetic suite covers ordered continuous roots, reversed B-roll parent
coverage, returns/resume state, independent crossing overlays and primary-first
ties, exact token anchors, insert/convert/flatten/swap/delete/cross-row repair,
complete-clip modes and fallback estimates, linked complete-clip chain
mode-out using exact caller words, successful cross-row source repair with
payload/evidence/version preservation, equal/crossed boundary refusal,
Unplaced identity/lineage, and exact two-of-three placement resolution/refusal.

## Additional package-suite observation

An extra `npm run test --workspace @vera/contracts` run on the initial
implementation commit `80bbedd74035ca0fcffad713f25fda2c51e506d3` ran 284 tests:
282 passed, while two existing #144 CLI/omission-bridge tests exceeded their
default five-second per-test timeout during package-wide concurrency. No #144
test or timeout was changed. This is retained as an observed package-suite
failure, not a passing acceptance command. The parent owns repository-wide
validation and any targeted rerun of those existing tests.

## Full repository acceptance

Final implementation source: `7e419da788e28688fff4c32c4baabad23238e5a5`.
The clean source tree passed `VITEST_MAX_WORKERS=1 npm run validate` with
Node 24.19.0, npm 11.17.0, Python 3.12.14 and uv 0.12.5. The environment
limits Vitest concurrency without changing test timeouts, assertions or scope.
All lint, typecheck, generated-contract checks and tests passed: 288 contracts
tests, one tooling test, and 371 Python tests. Exit code: 0; elapsed: 5378.49
seconds (Python tests: 5185.97 seconds). Complete retained log SHA-256:
`eb2aa53f0a32a351eb7f19f2be7b450ee9861755b0d53b303a4982ad1354e281`.

The unchanged two-file #144 CLI/omission suite also passed 21/21 tests with
`--no-file-parallelism` and its existing five-second timeout. Earlier concurrent
failures above remain recorded; the full passing profile is explicitly serial.
Independent final review found no remaining concrete defect. A comparison to
the worktree base confirmed every existing file unchanged except the single
additive package export; all frozen schemas, generated types, fixtures, goldens,
accepted tests and #144 caller source pins retain their baseline bytes.
Acceptance is Automated. Native application, persistence and Producer
qualification are outside this authoring slice.

## Exact source hashes

SHA-256 at the focused passing check:

| File | SHA-256 |
| --- | --- |
| `packages/contracts/package.json` | `3bccf26b478f38cfa844a66b1cffeecb7ef8bfd09e88e5cd973af7a36ebf06a3` |
| `packages/contracts/src/authoring-v2.ts` | `2f1f6ff480ee94ae329b4467250be646fd5a143acb42ce28444636c403d3d208` |
| `packages/contracts/src/authoring-v2-validation.ts` | `e201fedb07c299966bb363c034bf941466832b263644e25a6fbed318a3880cd5` |
| `packages/contracts/src/authoring-v2-projection.ts` | `567ed6116aadc98aaa3dfbf548bb5eba10baec8bbe880a80e638d53153be648d` |
| `packages/contracts/src/authoring-v2-placement.ts` | `d6e666424e49bbd7f30b86806ac54850aabd2cd95889bb9c497adbd02e9b5161` |
| `packages/contracts/src/authoring-v2-edits.ts` | `b982369025b97324dc64301195c36b621a858a3bd1b72c1f2c2d29b54e8b2940` |
| `packages/contracts/test/authoring-v2.test.ts` | `3c70f7ef220bbf0509a97f8bcd3c4e1b2ed0c3f1a6e9ad06b3230ca34b158154` |

No new dependency, schema, generated type, existing fixture/golden, UI,
persistence, compiler, media, native-application, or external-service change
was included. The P3 edit result is a local canonical revision with operation
evidence; application/persistence callers own acknowledgement and advancement
of the live collaboration snapshot fields.
