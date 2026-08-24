# VERA Script to Timeline

VERA Script to Timeline is the authoring and timeline-compilation companion to
[VERA Research Video Clips](https://github.com/mbelinkie/vera-research-video-clips).
It owns structured script authoring, narrative order, per-video media usage,
voiceover and graphics intent, deterministic timeline compilation, build
history, and DaVinci Resolve delivery.

The two products remain independently deployable. They integrate through
versioned, authorized APIs and verified artifact descriptors rather than shared
databases or UI dependencies.

## Current status

The repository is in Phase 0 foundation work. The current build sequence and
acceptance ladder are documented in
[`docs/Script-to-Timeline Product Spec - Fable Rev2.md`](./docs/Script-to-Timeline%20Product%20Spec%20-%20Fable%20Rev2.md).

Earlier product specifications are retained under [`docs/archive`](./docs/archive)
for decision history. Revision 2 is authoritative when those documents differ.

## Prerequisites

The checked-in version files and CI use:

- Node.js `24.19.0` (see `.nvmrc`)
- npm `11.17.0` (also pinned by `packageManager`)
- [uv](https://docs.astral.sh/uv/) `0.12.5`
- CPython `3.12.14` (managed by uv from `.python-version`)

Git and a POSIX-compatible terminal are also required. Repository scripts use
portable npm/Node/Python commands and run on macOS as well as the Ubuntu CI
runner.

With `nvm` and uv installed, prepare the pinned runtimes:

```sh
nvm install
nvm use
npm install --global npm@11.17.0
uv python install 3.12.14
```

## Fresh-clone bootstrap

Install exactly the dependency graphs recorded in both lockfiles:

```sh
npm ci
uv sync --frozen
```

Use `npm install` only when intentionally changing JavaScript dependencies and
`uv lock` only when intentionally changing Python dependencies. Commit the
corresponding lockfile change with the dependency change.

## Validation

The single top-level validation command is:

```sh
npm run validate
```

It runs TypeScript lint, strict typechecking, and tests in every npm workspace
that provides those scripts, followed by Python Ruff lint/format checks, strict
mypy, and pytest. CI installs from both lockfiles and invokes this exact
command. Contract and fixture workstreams should extend this command rather
than creating a separate acceptance path.

### Contract schemas and generated types

The JSON Schema Draft 2020-12 files in [`contracts/`](./contracts) are the
single source of truth for the first-draft `ScriptDocument v1`,
`TimelineManifest v1`, and `BuildReport v1` contracts. Their checked-in,
schema-derived language types live at:

- `packages/contracts/src/generated/contracts.ts`
- `python/vera_timeline_agent/generated/contracts/`

Regenerate both language outputs with the pinned npm and uv dependency graphs:

```sh
npm run generate:contracts
```

Do not edit generated files by hand. To verify that checked-in output is an
exact byte-for-byte regeneration without changing the worktree, run:

```sh
npm run check:contracts-generated
```

The currentness check runs first in `npm run validate`. The contract test
workspace also compiles all three schemas together, resolves their explicit
cross-schema references offline, accepts representative Phase 1 instances,
and rejects focused invalid instances. Cross-record semantics such as complete
OC/VO token coverage and VO visual coverage intentionally remain the Slice 1.1
semantic validator's responsibility; JSON Schema validates structure rather
than pretending to enforce those comparisons.

Individual groups are available for diagnosis:

```sh
npm run check:typescript
npm run check:python
npm run lint:typescript
npm run typecheck:typescript
npm run test:typescript
npm run lint:python
npm run typecheck:python
npm run test:python
```

## Slice workflow

Agent guardrails live in [`AGENTS.md`](./AGENTS.md). Decisions and unresolved
producer choices are tracked in [`DECISIONS.md`](./DECISIONS.md); only observed,
version-stamped Resolve behavior belongs in
[`CAPABILITIES.md`](./CAPABILITIES.md).
