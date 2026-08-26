# Text+ pinned-template validation and integration follow-up

## Bounded scope

Validate the producer-authored `text_plus_template.drb` against Resolve Studio
21.0.4 using documented scripting APIs, then—only if that retained validation
project passes—replace Slice 0.4's nondeterministic stock-title insertion with
the validated media-pool-generator/`AppendToTimeline` path. The integrated
default places `Text+` at the manifest timeline start for the manifest timeline
duration on the adjustable `video-graphics` track.

The validation project and any partial project are retained for audit. A
successful run must compare the stock and pinned-template Fusion tool graphs,
measure the generator end-frame rule at 24 and 72 frames, place the canonical
72-frame item on V4, save, reopen, and reverify identity, track, start, and
duration before integration is enabled.

## Exclusions

- No modification of frozen contracts, fixtures, generated contract output,
  accepted tests/data, or golden files.
- No arbitrary Fusion-title support, stock-title catalog enumeration, UI
  automation, Resolve launch/quit, rendering, upload, project reuse, overwrite,
  or deletion.
- No execution or modification of the pre-existing untracked Resolve probe
  scripts.
- No claim that a preflight proves mutation-only Resolve calls.

## Asset, contracts, and dependencies

- The producer manually authored and visually approved a one-bin/one-generator
  export from Resolve 21.0.4 build 5. The exported bin is
  `VERA Text+ Template`; the archive XML serializes its single generator as
  `Fusion Title`, while the supported runtime API exposes the imported clip as
  `Text+`.
- The versioned `.drb` is paired with a JSON provenance sidecar containing its
  SHA-256, authoring version, expected archive/bin/clip names, and expected
  single-generator/Fusion topology. Both files must ship in the Python wheel.
- The frozen `TimelineManifest v1` remains unchanged. Title placement is an
  internal Studio-adapter request derived from existing timeline and track-map
  data, with optional CLI overrides.
- No dependency or lockfile change is authorized. ZIP/XML/hash validation uses
  the Python standard library and the Resolve/Fusion surfaces are vendor APIs.

## Automated checks

- Reject missing, symlinked, oversized, hash-mismatched, malformed, encrypted,
  path-traversing, over-expanded, or structurally unexpected assets before any
  Resolve connection or project mutation.
- Prove Free mode never loads or invokes the template/Resolve path; prove
  invalid title, track, and duration values stop before project creation.
- With strict doubles, verify capability-probe order, unique-project protection,
  imported-bin cardinality, tool registration-ID fingerprints, measured
  end-frame selection, exact V4/start/duration placement, retained partial
  projects, save/reopen checks, negative other-track checks, CLI JSON, and
  backward-compatible result statuses.
- Run focused pytest, Ruff, strict mypy, the full repository validation gate,
  wheel-content inspection, `git diff --check`, and frozen-boundary/lockfile
  audits.

## Producer acceptance

1. Review the asset hash/provenance and authorize one uniquely named validation
   project after nonmutating preflight passes.
2. Confirm the validation CLI reports equivalent stock/template Fusion tool
   fingerprints, a proven duration rule at 24 and 72 frames, and a reopened
   72-frame Text+ on V4 with no discrepancy.
3. Visually inspect and accept the retained validation project.
4. Authorize one uniquely named integrated build, inspect the pinned-template
   bin and title, and confirm saved/reopened V4 placement and duration.
5. Accept the capability/decision/limitation updates. Producer observation is
   authoritative; automated evidence alone does not close this follow-up.

## Follow-up 1 validation evidence

- Producer acceptance: accepted on 2026-08-25 after visual inspection.
- Retained project: `VERA TextPlus Template Validation 20260825-230705`.
- Resolve identity: DaVinci Resolve Studio 21.0.4, API build 5.
- Asset SHA-256:
  `4a984512f1c7eba6f15a4ea8104a6bb4953e50e4f8aa816a53138daf818372ac`.
- Stock and imported-template fingerprints each contained one Fusion
  composition, exactly one `TextPlus`, and the sorted registration-ID multiset
  `MediaOut`, `TextPlus`.
- Observed generator rule: `endFrame = requested duration + 1`; candidate
  end frames 23, 24, and 25 produced 22, 23, and 24 frames respectively, and
  end frame 73 produced exactly 72 frames.
- Save/close/reopen verification passed with one `Text+` on V4 at timeline
  start for 72 frames and no item on V1 through V3.

This acceptance opens Follow-up 2. It does not by itself resolve the
production limitation; that requires a separately named integrated build and
producer inspection.

## Follow-up 2 integrated-run evidence

- Retained project: `VERA TextPlus Integrated Acceptance 20260825-234847`.
- Timeline: `VERA build 00000000-0000-4000-8000-000000000103`.
- Nonmutating preflight passed before project creation.
- The producer-authorized build saved, closed, reopened, and returned
  `verified` with no public-API-observable discrepancy.
- Structured placement evidence reports one `Text+` at absolute frame 0 for
  72 frames on manifest track `video-graphics`, resolved to V4, with asset hash
  `4a984512f1c7eba6f15a4ea8104a6bb4953e50e4f8aa816a53138daf818372ac`
  and registration IDs `MediaOut`, `TextPlus`.
- The producer visually inspected and accepted the integrated build on
  2026-08-25. This closes both follow-ups and resolves destination-track and
  duration control for the shipped pinned-template path. Stock-title catalog
  enumeration and arbitrary Fusion titles remain open.

## Final automated verification

- Sixty-three focused Text+ template, capability-validation, Studio-placement,
  safety-boundary, reopen, and CLI tests passed with Ruff formatting/lint and
  strict mypy over the eight touched source/test files.
- A clean isolated checkout with the complete intended tree passed locked
  installs and the full gate under Node 24.19.0/npm 11.17.0: generated
  contracts were current, 59 contract tests, 1 tooling-smoke test, 4 progress
  tests, strict mypy over 38 files, Ruff, and all 146 Python tests passed.
- A freshly built wheel contained the 8,875-byte `.drb` and JSON sidecar; the
  wheel-embedded asset hash matched the accepted SHA-256.
- `git diff --check` passed. Frozen contracts, fixtures, generated types,
  accepted Slice 0.2/1.1 data, accepted OTIO tests, and `package-lock.json`
  were unchanged. The Text+ work added no dependency or lockfile entry; the
  visible boto3/uv-lock delta belongs to the separately accepted Slice 1.2.
- Existing untracked destructive Resolve probe scripts were preserved,
  excluded from the isolated gate, and never executed.
