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
- FFmpeg and FFprobe `8.1.2` for canonical fixture regeneration and the
  producer's required media-metadata acceptance check

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

It first proves that checked-in contract types are byte-current, then runs
TypeScript lint, strict typechecking, and tests in every npm workspace, followed
by Python Ruff lint/format checks, strict mypy, and pytest. Pytest validates the
fixture descriptor, exact media inventory, sizes, hashes, and (when FFprobe is
available) metadata. CI installs from both lockfiles and invokes this exact
command.

An environment without FFprobe does **not** claim metadata verification: the
FFprobe-specific pytest checks are reported as skipped, and the standalone
verifier prints `FFprobe unavailable; metadata skipped`. The producer
acceptance path must require metadata rather than permit that skip:

```sh
uv run --frozen python fixtures/validate_fixtures.py --require-ffprobe
```

Canonical fixture regeneration additionally requires FFmpeg. The generator
fails explicitly if either executable is absent or if FFmpeg/FFprobe is not the
recorded `8.1.2` version; see [`fixtures/README.md`](./fixtures/README.md) for
the byte-reproduction caveat.

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

`TimelineManifest v1` track IDs are bounded opaque identities. Track media kind
and positive ordering index are separate structural fields; consumers must not
infer either from names such as `V1` or `A1`. The section 9.2 track labels are
representative sample/default values only while D-P004 remains pending.
D-0004's 24000/1001 rate, 1920x1080 dimensions, and 48 kHz sample rate are
schema defaults, not constants; explicit positive alternatives are valid.

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
npm run test:otio-package
npm run test:free-trial
```

The full Python test discovery used by `npm run validate` includes the Slice
0.2 OTIO package tests; `test:otio-package` is only the faster focused form.

## Slice 0.2 producer package

Slice 0.2 consumes the handcrafted schema-valid manifest under
`tests/data/slice_0_2/` and the frozen synthetic fixture bytes. From a locked
install at the repository root, generate and parse-verify the producer package
with:

```sh
uv run --frozen python -m vera_timeline_agent.otio_package \
  tests/data/slice_0_2/timeline-manifest.json \
  --media-root fixtures \
  --output out/slice-0.2-package
```

The exact output location is `out/slice-0.2-package/`. Repeating the
command safely re-verifies and reuses an identical package; it refuses to
replace an unrelated, invalid, or different-manifest path. A successful
command has already verified the canonical manifest, schema-valid build
report, exact package inventory, copied-media hashes, OTIO parseability, event
and source/record ranges, track metadata, one marker, and the absence of OTIO
transition objects.

Open `IMPORT_INSTRUCTIONS.md` in the output folder first. It explains how to
inspect `build-report.json`, keep the project-relative media paths intact, and
manually import `timeline.otio` in DaVinci Resolve. V3 contains three trimmed
synthetic video clips followed by one still; A1 contains the frozen ambient WAV
used explicitly as **synthetic test narration**; and the timeline has one blue
producer marker and hard cuts only. The command proves package consistency,
not Resolve behavior—actual Resolve Free import fidelity is the producer-run
Slice 0.3 trial.

## Slice 0.3 Resolve Free dual-input trial

Generate deterministic, independently self-contained OTIO and FCPXML inputs
from the exact accepted Slice 0.2 manifest/media with:

```sh
uv run --frozen python -m vera_timeline_agent.free_trial \
  tests/data/slice_0_2/timeline-manifest.json \
  --media-root fixtures \
  --output out/slice-0.3-free-trial
```

The command schema/semantic-verifies both formats against the manifest, checks
media hashes and self-containment, and refuses to replace different output.
It does not launch Resolve or prove import behavior. Follow
[`docs/slice-0.3-resolve-free-trial.md`](docs/slice-0.3-resolve-free-trial.md)
to manually import both files into separate fresh Resolve Free projects and
record the comparison. FCPXML remains a trial artifact unless that evidence
supports and the producer records a maintained-fallback decision.

## Slice 0.4 Studio scripting spike

The Slice 0.4 CLI always consumes and re-verifies the accepted Slice 0.2
package. First inspect local facts without importing or connecting to Resolve:

```sh
uv run --frozen python -m vera_timeline_agent.studio_spike_cli detect
```

Prove the Free safety boundary (this never imports, connects to, or invokes
the Resolve API):

```sh
uv run --frozen python -m vera_timeline_agent.studio_spike_cli run \
  out/slice-0.2-package --mode free
```

For producer acceptance only, manually start the supported standard desktop
Resolve Studio installation and enable local external scripting in Resolve
preferences. Run the nonmutating connected preflight:

```sh
uv run --frozen python -m vera_timeline_agent.studio_spike_cli run \
  out/slice-0.2-package --mode studio --action preflight
```

After reviewing its detected and connected facts, authorize one uniquely
named spike project build (replace the name for each attempt; existing projects
are never reused or overwritten):

```sh
uv run --frozen python -m vera_timeline_agent.studio_spike_cli run \
  out/slice-0.2-package --mode studio --action build \
  --project-name "VERA Slice 0.4 Producer Acceptance 2026-08-24"
```

The build path creates bins/tracks from the adjustable manifest, imports and
places its three trimmed videos, still, and synthetic narration at exact
record/source frames, requests the named `Text+` Fusion title, adds marker
custom data, saves, closes/reopens, and verifies public-API-observable project,
timeline, setting, bin, track, media-identity, item-range, title-presence, and
marker data. This bounded spike rejects nonzero timeline starts before loading
the Resolve bridge. The public API cannot enumerate stock Fusion titles or
select/prove the title's destination track, and nonmutating preflight cannot
prove mutation-only calls, so the CLI reports those bounded manual-completion
items. Do not record a Studio capability
until the producer performs and inspects this real run; automated doubles are
not Resolve evidence. A failure after the build is authorized can leave a
partial project; the CLI reports `mutation_failed` and the project must be
inspected manually rather than treated as a nonmutating safety stop.

## Slice workflow

Agent guardrails live in [`AGENTS.md`](./AGENTS.md). Decisions and unresolved
producer choices are tracked in [`DECISIONS.md`](./DECISIONS.md); only observed,
version-stamped Resolve behavior belongs in
[`CAPABILITIES.md`](./CAPABILITIES.md).
