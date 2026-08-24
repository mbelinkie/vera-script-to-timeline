# Slice 0.1 Tooling Workstream Plan

## Scope

- Establish an npm TypeScript workspace and an installable Python package.
- Pin tool versions and check in npm and uv lockfiles for reproducible installs.
- Add lint, typecheck, and test commands for both languages, composed behind one
  top-level validation command that later Slice 0.1 workstreams can extend.
- Add CI that installs from the lockfiles and runs that same validation command
  on Ubuntu while keeping all repository scripts macOS-compatible.
- Check in the standing agent guardrails, initial decision/capability records,
  and fresh-clone setup instructions.
- Add only the smallest package-import tests needed to prove both toolchains.

## Exclusions

- No `/contracts`, `/fixtures`, generated contract types, or golden files.
- No media generation or media assets.
- No OTIO/FCPXML writing, Resolve integration or automation, compiler behavior,
  web application behavior, or other product code.
- No changes to `docs/IMPLEMENTATION_PROGRESS.md`.
- No producer decisions about OS, Resolve versions, timeline settings, track
  names, or interchange fallback will be inferred.

## Owned files

- Root tooling: `package.json`, `package-lock.json`, `eslint.config.mjs`,
  `tsconfig.base.json`, `pyproject.toml`, `uv.lock`, `.nvmrc`,
  `.python-version`, and tooling-related `.gitignore` entries.
- Smoke scaffolds: `packages/tooling-smoke/**`,
  `python/vera_timeline_agent/**`, and `tests/test_tooling_smoke.py`.
- Automation: `.github/workflows/validate.yml`.
- Process/docs: `AGENTS.md`, `README.md`, `DECISIONS.md`, `CAPABILITIES.md`, and
  this plan.

## Dependency justifications

- TypeScript plus Node type declarations provide the workspace compiler and
  standard-library types.
- ESLint, `@eslint/js`, and `typescript-eslint` provide typed TypeScript linting
  without a custom lint framework.
- Vitest provides a small, TypeScript-native test runner that workspaces can
  reuse.
- uv supplies locked Python environment management; Hatchling supplies the
  minimal standards-based package build backend.
- Ruff supplies fast Python lint and format checks, mypy supplies static type
  checking, and pytest supplies the conventional Python test runner.
- GitHub's checkout/setup-node actions and Astral's setup-uv action are pinned
  to commits so CI can install the pinned runtimes and dependencies.

## Automated checks

1. `npm ci` accepts the checked-in npm lockfile.
2. `uv sync --frozen` accepts the checked-in uv lockfile and package metadata.
3. TypeScript lint, strict typecheck, and smoke test pass in every workspace
   that defines the corresponding scripts.
4. Python Ruff lint/format, strict mypy, and pytest smoke test pass.
5. `npm run validate` runs all of the above language checks and is the exact
   validation entry point used by CI.

The contract and fixture workstreams remain responsible for adding their
schema generation/currentness and fixture validation checks to this ratchet.

## Producer acceptance portion

For this bounded tooling portion of Slice 0.1, the producer should:

1. Start from a fresh clone with the documented Node, npm, uv, and Python
   prerequisites.
2. Run `npm ci` and `uv sync --frozen` without lockfile changes.
3. Run `npm run validate` and confirm the TypeScript and Python lint,
   typecheck, and test sections all pass.
4. Confirm the repository CI runs `npm run validate` and is green.

The full Slice 0.1 acceptance also requires generated contract types and
fixture schema/hash validation; those are explicit handoffs to the parallel
contract and fixture workstreams and are not claimed by this plan.
