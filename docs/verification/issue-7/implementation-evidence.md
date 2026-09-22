# Issue #7 — implementation evidence and Producer acceptance

## Scope and judgment calls

The Producer approved the explicit contract boundary on 2026-09-22 in claimed
task `01a0c960-9289-7373-9840-a2a5c0ab2deb`; the approval is recorded in
the issue and `docs/plans/issue-7-fusion-graphics-contract-change.md`.

The compiler now accepts only a hash-pinned EV24 Lower Third project revision
and stable semantic values. A selected project badge contributes its verified
content hash to the resolved snapshot. The manifest contains one
`fusion_graphic` event per occurrence, with its original narration anchor,
exact frame range, video track, provenance, template identity, and semantic
snapshot hash. The Normal and Otis fixture examples target V4 for 120 frames;
Otis has no Year, and null text overrides stay null.

The same manifest bytes serve Studio and Free. The build report labels the
Studio result **planned live** and the Free result **placeholder with linked
manual completion**. `baked` is a valid future report type but no baked asset
is generated or selected in #7. Existing package writers reject
`fusion_graphic` before materialization; neither report claims verified Resolve
placement. This follows the approved GF-1 boundary and leaves package/Studio
placement to later work.

## Automated evidence

- Toolchain: Node 24.19.0, npm 11.17.0, Python 3.12.14, pytest 9.1.1.
- `rtk proxy env PATH=/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm ci`
  and `rtk uv sync --frozen` completed with the checked-in locks.
- `rtk proxy env PATH=/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run validate`
  passed:
  generated contracts current, TypeScript lint/typecheck, 177 contract tests,
  1 tooling test, 6 progress tests, 23 roadmap tests, Python Ruff/format,
  strict mypy over 57 source files, and all 187 Python tests.
- The issue-owned graphic test ran twice consecutively with no golden update:
  9/9 passed on each run; every manifest/report compared byte for byte with
  the retained goldens. Python also validates both edition variants against
  the JSON Schemas and proves both package writers reject unsupported graphics.
- `rtk git diff --cached --check` passed. `rtk git diff --cached --exit-code
  cc39f29 -- package.json package-lock.json pyproject.toml uv.lock fixtures
  tests/data/slice_1_1 tests/data/slice_1_3
  packages/contracts/test/compiler-core.test.ts
  packages/contracts/test/schema-validation.test.ts` was empty and passed.
  The staged change inventory under `fixtures`, `tests/data`, and accepted
  tests contains only new `issue_7` data, the new graphic test, and the new
  Python test. No dependency or lock entry was added.

## Issue-owned golden hashes (SHA-256)

| Artifact under `tests/data/issue_7/` | SHA-256 |
| --- | --- |
| `normal.studio.manifest.golden.json` | `16bca7d7f81a1ce276d391f4e187fe525a6e91bb8401f987bc677a6a8638a77c` |
| `normal.free.manifest.golden.json` | `16bca7d7f81a1ce276d391f4e187fe525a6e91bb8401f987bc677a6a8638a77c` |
| `normal.studio.report.golden.json` | `c82e176cc2772d436eca0fc1e29c15f391722968e321a8b722259d024881fa00` |
| `normal.free.report.golden.json` | `da215c2e42eb2b08af9ea7fd4941aa6105240175448b4ed1e72220e719c50217` |
| `otis.studio.manifest.golden.json` | `3a5a0f2d3af0fc1c1c109d8e22ef3d60922d385aaba984a5d078eab10ca95dd0` |
| `otis.studio.report.golden.json` | `d1b2287d068d8ad77b8ca025b2189c31ddc2f5938661e1712666a08aeeb39d3e` |

## Producer checklist

1. Open `docs/plans/issue-7-fusion-graphics-contract-change.md` and
   `contracts/script-document-v1.schema.json`. Confirm the approved EV24-only
   source has pinned revision/hash, stable country, Year except for Otis,
   nullable text overrides, and project badge ID. There must be no author
   field for script, expression, Fusion control, or file path.
2. Open `tests/data/issue_7/normal.studio.manifest.golden.json` and
   `otis.studio.manifest.golden.json`. Find the `fusion_graphic` event. Confirm
   V4 (`video-4`), 120 frames, the original narration anchor/provenance, exact
   pinned source, and badge hash. Confirm Otis has no Year and no invented
   auto-filled text.
3. Compare `normal.studio.report.golden.json` and
   `normal.free.report.golden.json` with the same manifest hash. Confirm
   planned live Studio versus Free placeholder plus a linked
   `COMPLETE_FUSION_GRAPHIC` item. Confirm neither says Resolve was verified or
   a baked graphic was rendered.
4. Review the automated evidence and golden hashes above. No Resolve project
   action is needed for this contract/compiler slice. Reply on issue #7 with
   `ACCEPT #7 — I checked steps 1–4 and approve the contract/compiler output`
   or `FAIL #7 — step <number>: <observed mismatch and requested correction>`.

Keep #7 In review until the explicit acceptance reply. Do not self-close it.
