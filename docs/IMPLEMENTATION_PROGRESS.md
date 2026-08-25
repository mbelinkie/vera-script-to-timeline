# Implementation Progress

This document is the orchestration record for implementing
`Script-to-Timeline Product Spec - Fable Rev2.md`. It tracks slice ownership,
contract boundaries, verification, producer acceptance, decisions, and
follow-up work. A slice is complete only after its automated checks pass **and**
the producer runs its acceptance script successfully.

Last updated: 2026-08-25

## Current milestone

- **Phase:** 0 gate closed; Phase 1 may proceed
- **Active slice:** 1.2 — planning and provider evaluation
- **Overall state:** Slices 0.1 through 0.4 are accepted. The producer accepted
  Slice 0.4 on 2026-08-25, including its documented V1 Text+ destination-track
  limitation. The limitation remains an open capability gap in
  `docs/resolve-text-plus-destination-track-limitation.md`; acceptance does not
  claim that it is solved. The producer explicitly accepted Slice 1.1 on
  2026-08-25, freezing its two canonical semantic inputs. Under D-0008,
  later automated-only slices may be accepted by the orchestrator after their
  bounded acceptance evidence and independent review pass; irreducibly manual
  acceptance remains with the producer. Slice 1.2 is active.
- **Source specification:** `docs/Script-to-Timeline Product Spec - Fable Rev2.md`

## Status legend

- `Queued` — bounded but not started
- `In progress` — assigned and actively being implemented
- `Agent complete` — implementation and automated checks reported complete;
  producer acceptance is still required
- `Accepted` — the producer explicitly accepted the slice, or the orchestrator
  accepted an automated-only slice under D-0008 after all required evidence
  passed
- `Paused` — authorized work is preserved but intentionally not active
- `Blocked` — cannot proceed without a recorded decision or external condition

## Slice tracker

| Slice | Status | Owner | Depends on | Verification / notes |
| --- | --- | --- | --- | --- |
| 0.1 Repository, contracts, and fixture scaffold | Accepted | Orchestrator + bounded implementation agents | — | Producer accepted on 2026-08-24 after clean detached-worktree validation and green GitHub Actions runs `32789057717` and `32789138346`. Contracts and fixtures are now frozen. |
| 0.2 Handcrafted manifest → OTIO package | Accepted | Orchestrator + bounded implementation and review agents | 0.1 accepted | Producer explicitly accepted on 2026-08-24 after package inspection, independent review, fresh-worktree verification, and green CI. `/contracts` and `/fixtures` remain frozen and unchanged. |
| 0.3 Resolve Free import trial | Accepted | Producer + agent preparer/recorder | 0.2 accepted | Producer accepted on 2026-08-24. OTIO retained the marker and linked all five items; FCPXML required a manual media redirect and omitted the marker. D-P005 parks FCPXML with no observed compensating advantage. |
| 0.4 Resolve Studio scripting spike | Accepted | Producer + bounded implementation, hardening, and review agents | 0.2 accepted | Producer explicitly accepted on 2026-08-25 after visual inspection and accepted the documented V1/120-frame Text+ public-API limitation as spike evidence. The limitation remains open in `docs/resolve-text-plus-destination-track-limitation.md`. |
| 1.1 ScriptDocument v1 and validator | Accepted | Orchestrator + bounded implementation/review agents | D-0006 semantic decisions; Phase 0 accepted | Producer explicitly accepted on 2026-08-25 after the pure TypeScript validator and CLI, two canonical inputs, exact row-level diagnostics, 59 contract/validator tests, clean pinned full gate, frozen-boundary audit, and final independent no-findings review passed. The canonical inputs are now frozen. |
| 1.2 Voice adapter and block asset cache | In progress | Orchestrator + bounded research/implementation/review agents | Slice 1.1 accepted | Provider comparison, bounded contract/cache design, and FFmpeg-normalization planning are active. Final acceptance remains manual because the specification requires the producer to hear generated files and observe cache behavior. |

## Slice 0.1 orchestration plan

### In scope

1. TypeScript workspace and Python package scaffolds.
2. CI that runs lint and tests for both languages.
3. Draft JSON Schemas for `ScriptDocument v1`, `TimelineManifest v1`, and
   `BuildReport v1`, plus reproducibly generated TypeScript and Python types.
4. Deterministic fixture media: three clips, two stills, one audio bed, with
   recorded content hashes.
5. `DECISIONS.md`, `CAPABILITIES.md`, checked-in agent guardrails, and one
   documented validation command.

### Explicitly out of scope

- OTIO/FCPXML writing or Resolve automation (Slices 0.2–0.4).
- Script semantic validation and compilation (Phase 1).
- Web application, persistence, collaboration, or deployment.
- Real production media or credentials.

### Contract and fixture policy

Contracts and fixtures may be created during Slice 0.1. Once producer
acceptance passes, they are frozen between slices. Any later modification must
be accompanied by a contract-change or fixture-change note describing what
changes, why, compatibility impact, regenerated outputs, and acceptance impact.

### Acceptance script, restated

1. Start from a fresh clone with the documented tool prerequisites.
2. Run the single documented validation command.
3. Confirm TypeScript lint/tests pass.
4. Confirm Python lint/tests pass.
5. Confirm generated types are current with the three schemas.
6. Confirm every fixture descriptor validates and every media hash matches.
7. Confirm CI executes the same checks and is green.

## Agent work log

| Date | Agent/workstream | Assignment | State | Result |
| --- | --- | --- | --- | --- |
| 2026-08-24 | Orchestrator | Locate authoritative repository/spec; initialize assigned workspace from `origin/main`; establish progress record | Complete | Spec and slice ritual reviewed; workspace now tracks the product repository |
| 2026-08-24 | Tooling workstream | Monorepo, CI, developer commands, guardrails, decision/capability document scaffolds | Agent complete | Integrated as `178b668`; clean npm/uv installs and the pinned-toolchain `npm run validate` pass independently. Remote CI and producer acceptance remain pending. |
| 2026-08-24 | Contracts workstream | Three JSON Schemas, generated types, schema/type tests | Agent complete | Integrated as `3d9c3c4`; three Draft 2020-12 schemas, generated TypeScript/Python models, positive/negative tests, and byte-currentness checks. |
| 2026-08-24 | Fixtures workstream | Deterministic media kit, descriptors/hashes, validation tests | Agent complete | Integrated as `83b7b74`; exactly three clips, two stills, and one audio bed with strict inventory, SHA-256, FFprobe metadata, regeneration, and verifier tests. |
| 2026-08-24 | Integration/review workstream | Merge audit, fresh-clone simulation, acceptance script verification | Agent complete | Integrated as `5028ed8`; removed premature fixed track-name/count constraints, proved configurable delivery settings, tightened fixture verification, and passed a clean detached-worktree bootstrap. |
| 2026-08-24 | Producer | Run/confirm Slice 0.1 acceptance | Accepted | Producer explicitly accepted Slice 0.1 after local clean-worktree validation and GitHub Actions passed. Contracts and fixtures are frozen from this point. |
| 2026-08-24 | Slice 0.2 implementation workstream | Build a deterministic, self-contained OTIO import package from a handcrafted manifest without modifying frozen inputs | Agent complete | Integrated as `ceae4fc`; added the exact-pinned Python OTIO package API/CLI, schema and semantic validation, atomic/idempotent publication, relative packaged media, import instructions, build report, and adjustable delivery/track-map coverage. |
| 2026-08-24 | Slice 0.2 independent review workstream | Audit implementation, package boundaries, OTIO fidelity, determinism, and acceptance coverage | Agent complete | Integrated as `27e47d3`; rejected symlink/hard-link escapes, tightened hard-cut and identity semantics, added adversarial OTIO timing checks, and independently reproduced the full validation/package workflow in a fresh detached worktree. No unresolved code findings. |
| 2026-08-24 | Producer | Open and inspect the Slice 0.2 self-contained package, instructions, and event report | Accepted | Producer explicitly accepted Slice 0.2. Slices 0.3 and 0.4 are now unblocked; Resolve import fidelity remains a Slice 0.3 concern. |
| 2026-08-24 | Slice 0.3 preparation workstream | Prepare deterministic OTIO/FCPXML inputs and the producer evidence workflow without launching Resolve | Agent complete | Added a stdlib-only FCPXML evidence spike, dual-input command, semantic/self-containment checks, alternate-setting/track-map coverage, and manual worksheet. Detected local installation facts are explicitly untested; producer imports and D-P005 remain pending. |
| 2026-08-24 | Slice 0.4 implementation workstream | Add a supported-API Studio spike over the accepted Slice 0.2 package with fail-closed edition/install/scripting gates | Agent complete | Added local detection, nonmutating preflight, injected Resolve adapter, exact manifest assembly/reopen/verification flow, CLI, safety/order tests, and honest Fusion public-API gap reporting. No real Resolve connection or UI action was performed; producer acceptance remains pending. |
| 2026-08-24 | Slices 0.3/0.4 independent integration review | Audit FCPXML portability/security, Resolve API semantics, preflight/mutation boundaries, and verification completeness | Agent complete | Corrected the Resolve sample-rate key and timeline start handling; removed invented OS/minimum-version decisions; added partial-project reporting, source/lane and symlink-tree checks, project-name preflight, media-identity/settings/bins/title/marker verification, and explicit nonmutating-probe limitations. Frozen Slice 0.1/0.2 boundaries remain unchanged. |
| 2026-08-24 | Slices 0.3/0.4 boundary-hardening workstreams | Close successive independent findings without changing accepted contracts, fixtures, generated types, or Slice 0.2 evidence | Agent complete | Integrated `6199288`, `c316194`, `76ef9c1`, and `51166da`: corrected public Resolve API semantics, exact topology verification, documented-path media mapping, timeline-page gating, transition rejection, and fail-closed preflight/mutation boundaries. |
| 2026-08-24 | Final bounded fixer and fresh read-only review | Close cross-kind FCPXML resource-ID and Resolve install/connected-identity findings, then independently rereview the final commit | Agent complete | Integrated `f972afa`: all direct FCPXML resource IDs must be nonempty and globally unique; package-receipt classification requires the canonical app path, Blackmagic bundle ID, parseable matching version/build, and matching receipt; connected identity validates and compares all documented `GetVersion()` fields. Fresh review reported no findings. |
| 2026-08-24 | Orchestrator integration and CI | Integrate Slices 0.3/0.4 commits, rerun the full repository gate, audit frozen boundaries, push, and monitor CI | Complete | Main includes `447c08b` through `f972afa`; local validation passed with 82 Python tests, 16 contract tests, and 1 tooling test. Frozen-boundary diff is empty. GitHub Actions `32801825210` passed. |
| 2026-08-24 | Producer | Import both Slice 0.3 trial formats in actual Resolve Free and record observed behavior | Accepted | OTIO imported all five expected linked items and retained the marker. FCPXML imported the five items after a manual redirect to packaged media but omitted the marker. No other difference was observed. Producer approved D-P005 to park FCPXML and accepted Slice 0.3. |
| 2026-08-24 | Slice 1.1 read-only planning workstreams | Independently bound the validator slice and audit `ScriptDocument v1` against the exact Phase 1 requirements while Slice 0.4 awaits Studio | Complete | Both audits found the named structures already present and generated types current. The missing surface is the pure TypeScript semantic validator, CLI, semantic tests, and two canonical script inputs. No files in the frozen contract/fixture boundaries were changed. |
| 2026-08-24 | Orchestrator | Synthesize Slice 1.1 scope, semantic recommendations, test matrix, contract-change trigger, and acceptance path | Complete | Added `docs/plans/slice-1.1-script-validator.md`. Slice 1.1 remains queued pending producer approval of the semantic decisions and either Slice 0.4 acceptance or an explicit provisional sequencing exception. |
| 2026-08-24 | Producer | Decide Slice 1.1 semantics and whether implementation may proceed before Slice 0.4 acceptance | Accepted | Approved all seven semantic recommendations and provisional implementation. Recorded as D-0006 and D-0007; the exception does not close the Phase 0 gate or alter Slice 0.4's acceptance requirement. |
| 2026-08-25 | Producer + Slice 0.4 fixer | Exercise the real nonmutating Studio preflight and correct the vendor bridge loader without crossing the mutation boundary | Complete | The first correctly located run stopped safely with no discrepancies or mutation because Blackmagic's Python wrapper replaced itself in `sys.modules` and the loader retained the stale wrapper object. Commit `94bdd53` now consumes the vendor's replacement module and restores prior module state on failure; 43 focused Studio tests, the full 84-test Python/16-contract/1-tooling gate, frozen-boundary audit, and GitHub Actions run `32808424418` passed. |
| 2026-08-25 | Producer | Rerun the Slice 0.4 connected preflight against actual Resolve Studio | Complete | Connected to DaVinci Resolve Studio 21.0.4 build 5 through the supported external scripting API. Local bundle 21.0.4/build 21.0.40005 and connected identity agreed, `scripting_available` was true, discrepancies were empty, status was `preflight_passed`, and the command reported no project mutation. The one-time build remains pending. |
| 2026-08-25 | Producer | Pause all non-Slice-0.4 work | Active | Slice 1.1 implementation was interrupted and preserved in its isolated worktree. It will not resume until the producer finishes Slice 0.4 or explicitly changes this instruction. |
| 2026-08-25 | Producer + Slice 0.4 bounded fixer | Run the one-time real Studio build, investigate only observed discrepancies, and retry with unique projects | Agent complete | Initial retained projects exposed Resolve 21's default 120-frame still insertion and a 17-frame mark/clip-info intersection. A retained supported-API probe established the exact range rule. The final unique project `VERA Slice 0.4 Producer Acceptance 20260825-021704` saved, closed, reopened, and returned `verified` with no discrepancy. Focused validation passes with 44 Studio tests, Ruff, and strict mypy; clean locked installs and the pinned Node 24.19.0 full gate pass with 85 Python tests, and the frozen-boundary audit is empty. Producer visual acceptance remains. |
| 2026-08-25 | Producer | Visually inspect and accept Slice 0.4 | Accepted | Producer explicitly accepted Slice 0.4, including the documented V1/120-frame Text+ limitation. Phase 0 is closed; the limitation remains an open capability gap in `docs/resolve-text-plus-destination-track-limitation.md`, and Slice 1.1 may resume. |
| 2026-08-25 | Slice 1.1 implementation and review workstreams | Implement and independently harden the pure ScriptDocument validator, CLI, canonical inputs, and producer acceptance path | Agent complete | Commit `4fe34ab` adds deterministic structural/semantic validation and exact row/entity/token diagnostics without changing frozen contracts or fixtures. Successive reviews closed affinity, fixture-shape, CLI-output, schema-noise, and ID-scope ratchet gaps; the final review reported no findings. |
| 2026-08-25 | Producer | Accept Slice 1.1 and delegate later automated-only acceptance | Accepted | Producer explicitly accepted Slice 1.1. Its canonical semantic inputs are frozen. D-0008 records that the orchestrator may accept later slices whose full done condition is objectively automated, while manual listening, visual inspection, credentials/authorization, and irreducible human judgment remain producer gates. |
| 2026-08-25 | Slice 1.2 orchestration | Bound provider research, cache/contract design, and deterministic FFmpeg normalization before implementation | In progress | Slice 1.2 begins from the accepted Slice 1.1 inputs. No frozen contract, fixture, generated type, accepted test/data, or lockfile change is authorized without a separate approved change note. |

## Producer decisions and external checks

The following Phase 0 worksheet items must be recorded in `DECISIONS.md`
before their dependent slices close:

- Primary local-agent OS.
- Exact Resolve Free and Studio versions/installations to test.
- Timeline frame rate, resolution, and audio sample rate: **resolved by D-0004**
  as configurable settings with defaults of 23.976 fps, 1920×1080, and 48 kHz.
- Track naming convention: **resolved by D-0005**; use the specification's
  section 9.2 map as the adjustable default rather than a contract invariant.
- Slice 0.3 OTIO-versus-FCPXML fallback decision: **resolved by D-P005**; park
  FCPXML and maintain OTIO for the tested Free workflow.

## Risks / blockers

- The assigned workspace began as an empty Git repository; it has been
  initialized from the authoritative GitHub repository without modifying the
  separate desktop checkout.
- The producer's real Resolve Studio 21.0.4 connection, nonmutating preflight,
  and final unique build passed. The project saved, reopened, and passed all
  public-API-observable checks. The producer visually inspected it and accepted
  Slice 0.4, including the separately documented Text+ limitation.
- Slice 1.1 is accepted and its two canonical semantic inputs are frozen.
- Slice 1.2 is active. Its cloud synthesis path may require provider
  credentials and its done condition requires the producer to hear generated
  files and observe cache reuse/regeneration; implementation should proceed to
  that manual gate without pausing for ordinary design choices.
- Contract workstreams must not independently invent incompatible event or
  block shapes; the spec's canonical model and Phase 0/1 boundaries govern.

## Slice 0.1 verification result

- Clean locked installs: `npm ci` and `uv sync --frozen` pass.
- Pinned Node 24.19.0 `npm run validate` passes:
  - 16 contract tests and 1 TypeScript tooling test.
  - Ruff and strict mypy.
  - 11 Python tests, including fixture and generated-model checks.
- Generated TypeScript/Python contract output is byte-current and its
  post-bootstrap currentness check passes offline.
- Required FFprobe verification passes for exactly three clips, two stills,
  and one audio bed; all recorded hashes and metadata match.
- The full sequence was reproduced in a clean detached worktree without
  lockfile changes.
- GitHub Actions `Validate` run
  [32789057717](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/32789057717)
  passed on `main` at `4893c40`, including locked installs, the same top-level
  validation command, and the lockfile-diff guard.

## Slice 0.2 verification result

- Locked dependency installation passes with exact pins for
  `opentimelineio==0.18.1` and `jsonschema==4.25.1`.
- Pinned Node 24.19.0 full validation passes:
  - 16 contract tests and 1 TypeScript tooling test.
  - 31 Python tests.
  - Ruff, formatting, strict mypy, and generated-contract currentness.
- A fresh detached-worktree bootstrap and full validation pass without
  lockfile changes.
- The frozen `/contracts` and `/fixtures` boundaries remain unchanged; the
  Slice 0.2 manifest lives under `tests/data/slice_0_2/` and treats the
  accepted fixture media as read-only input.
- The generated producer package is available at
  `out/slice-0.2-package/` and is self-contained: one manifest, one OTIO
  timeline, one build report, import instructions, and five packaged media
  files referenced only by relative paths.
- Independent verification confirms event-for-event OTIO fidelity for three
  trimmed video clips, one still, one audio placement, one marker, explicit
  hard cuts, source ranges, record ranges, track assignments, media hashes,
  nonzero start frames, and alternate 1280×720 / 44.1 kHz delivery settings.
- Adversarial checks reject external/symlinked/hard-linked package media and
  reject OTIO source-timing tampering even when duplicated VERA metadata is
  left unchanged.
- Deterministic generation produces byte-identical packages, and rerunning an
  unchanged build reuses the existing package idempotently.
- GitHub Actions `Validate` run
  [32792300917](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/32792300917)
  passed on `main` at `c8f2862`, including locked installs, the full repository
  validation command, and the lockfile-diff guard.
- The producer explicitly accepted Slice 0.2 on 2026-08-24 after opening and
  inspecting the package, instructions, and event report. Actual Resolve
  import fidelity remains the separate Slice 0.3 acceptance gate.

## Slice 0.3 automated preparation result

- No dependency was added and both lockfiles remain unchanged.
- The dual-input command emits separate self-contained OTIO and FCPXML inputs
  from the exact accepted Slice 0.2 manifest/media and verifies both against
  five events, one marker, five sources, all tracks, three hard cuts, timeline
  settings, relative paths, hashes, and exact inventory.
- Repeated builds are byte-identical; alternate 24 fps, 1280×720, 44.1 kHz,
  reordered/custom track IDs/names/indices are covered.
- Locked `npm ci` and `uv sync --frozen` pass. Integrated validation passes
  with 82 Python tests, 16 contract tests, 1 TypeScript tooling test, Ruff,
  formatting, strict mypy, and generated-contract currentness.
- `/contracts`, `/fixtures`, generated contract outputs, the accepted Slice
  0.2 manifest, and accepted Slice 0.2 tests remain unchanged.
- Repository detection facts remain distinct from producer observation. The
  producer manually tested both formats in Resolve Free 21 and accepted the
  recorded OTIO baseline.
- Producer evidence showed FCPXML omitted the marker and required a manual
  media redirect without closing an OTIO gap. D-P005 parks FCPXML, and the
  producer accepted Slice 0.3 on 2026-08-24.

## Slices 0.3 and 0.4 integrated verification result

- Main contains the bounded implementation and hardening sequence
  `447c08b`, `3c1f1a6`, `6199288`, `c316194`, `76ef9c1`, `51166da`, and
  `f972afa`.
- Full local `npm run validate` passes:
  - generated contract output is current;
  - 16 contract tests and 1 TypeScript tooling test pass;
  - Ruff lint and format checks pass;
  - strict mypy passes for 19 source/test files; and
  - all 82 Python tests pass.
- GitHub Actions `Validate` run
  [32801825210](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/32801825210)
  passed on `main` at `f972afa`, including locked installs, the repository
  validation command, and the lockfile-diff guard.
- The diff from accepted Slice 0.2 commit `c4a093c` is empty for
  `/contracts`, `/fixtures`, generated TypeScript/Python contract output,
  `tests/test_otio_package.py`, and `tests/data/slice_0_2/`. Dependency and
  lock entries are unchanged; `package.json` adds only the focused
  `test:free-trial` script.
- FCPXML verification rejects transitions and requires every direct resource
  (`format` and all `asset` elements) to have a nonempty, globally unique ID.
- Resolve package-receipt classification now requires the exact canonical
  application path, expected Blackmagic bundle identifier, parseable matching
  bundle marketing/build encoding, and matching `ManifestLite` receipt.
  Custom or copied configured bundles fail closed before importing the API.
- Connected Resolve identity requires the documented five-field
  `[major, minor, patch, build, suffix]` response. Version, build, and suffix
  must match the local bundle identity before mutation; malformed or differing
  values stop safely. The public API still cannot prove the connected
  executable path, and that limitation is reported explicitly.
- A final fresh read-only review reran 51 focused Slice 0.3/0.4 tests plus
  Ruff and mypy and reported no actionable findings.
- No agent launched Resolve or automated its UI. With explicit producer
  authorization, the supported API connected to the producer-opened Studio
  instance and created only uniquely named generated Slice 0.4 projects. The
  final project passed save/reopen verification; failed generated projects and
  the capability probe were retained rather than overwritten or deleted.

## Slice 0.4 producer preflight evidence

- On 2026-08-25 the producer ran the connected preflight from outside the
  repository using `uv --directory`, proving the documented workflow does not
  depend on the caller's current directory.
- The initial real connection attempt stopped safely before mutation with
  `module 'DaVinciResolveScript' has no attribute 'scriptapp'`. Inspection
  showed that Blackmagic's installed wrapper replaces its own canonical
  `sys.modules` entry with the native `fusionscript` extension while executing;
  the repository loader had retained the stale wrapper object.
- Commit `94bdd53` registers the wrapper under its canonical name during
  execution, consumes the vendor-provided replacement module, and restores the
  previous entry when execution fails. Focused and full local validation,
  frozen-boundary review, and GitHub Actions run
  [32808424418](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/32808424418)
  passed.
- The producer's post-fix preflight connected through the supported API to
  `DaVinci Resolve Studio` 21.0.4 build 5 with external scripting available.
  The connected five-field identity agreed with the detected default-path
  bundle 21.0.4/build 21.0.40005 and matching `ManifestLite` receipt. The
  result had status `preflight_passed`, no discrepancies, and explicitly made
  no project mutation.
- The public API and preflight limitations reported by the command remain in
  force: no stock Fusion-title enumeration or title destination-track proof,
  no connected executable-path report, and no nonmutating proof of the calls
  that create/configure/import/assemble/insert.
- The first producer-authorized build retained the still at Resolve's default
  120-frame duration. The next attempts established that a documented
  MediaPoolItem mark range controls a still but interacts with
  `clipInfo.endFrame` differently from ordinary media. A retained probe matrix
  proved that mark out 18 plus clip end 19 creates the required 18-frame still.
- Final project `VERA Slice 0.4 Producer Acceptance 20260825-021704`, timeline
  `VERA build 00000000-0000-4000-8000-000000000103`, returned status
  `verified` after save/close/reopen with no discrepancies. The producer
  visually inspected the result and explicitly accepted Slice 0.4 on
  2026-08-25, including the documented V1/120-frame Text+ limitation.

## Slice 0.4 final automated verification

- A clean detached worktree containing the intended Slice 0.4 tracked diff and
  orchestration evidence completed locked `npm ci` and `uv sync --frozen`
  installs successfully.
- With pinned Node 24.19.0, the top-level `npm run validate` gate passed:
  generated contract output was current; TypeScript lint and typecheck passed;
  16 contract tests and 1 tooling test passed; Ruff lint and format checks
  passed; strict mypy passed for 19 source/test files; and all **85 Python
  tests** passed, including 44 focused Studio spike tests.
- `git diff --check` passed. The diff from accepted Slice 0.2 commit `c4a093c`
  remained empty for `/contracts`, `/fixtures`, generated TypeScript/Python
  contract output, `tests/data/slice_0_2/`, `tests/test_otio_package.py`,
  `package-lock.json`, and `uv.lock`.
- Unrelated dashboard and probe-script changes in the producer's main checkout
  were excluded from the clean verification and left untouched.

## Slice 1.1 automated verification

- Clean detached `npm ci` and `uv sync --frozen` installs passed with pinned
  Node 24.19.0 and npm 11.17.0.
- The combined accepted Slice 0.4 + Slice 1.1 tree passed `npm run validate`:
  generated contracts current, TypeScript lint/typecheck, **59**
  contract/validator tests, **1** tooling test, Ruff, strict mypy, and **85**
  Python tests.
- Both canonical CLI inputs pass and print every row with type, order key, and
  ID. The documented broken copy exits nonzero with the exact Row 2
  `VOICEOVER_VISUAL_GAP` and frozen token range.
- `git diff --check` passed. No accepted contract, fixture, generated type,
  Slice 0.2 data/test, or lockfile changed.
- Final independent read-only review of `4fe34ab` against `9dfacb4` reported no
  findings. The producer explicitly accepted Slice 1.1 on 2026-08-25; its two
  canonical semantic inputs are frozen for Slice 1.3 reuse.

## Acceptance history

### Slice 1.1 — Accepted 2026-08-25

The producer explicitly accepted Slice 1.1 after implementation, clean locked
verification, frozen-boundary audit, the exact canonical CLI evidence, and a
final independent no-findings review passed. The minimal and torture
`ScriptDocument` inputs under `tests/data/slice_1_1/` are frozen as semantic
inputs for Slice 1.3; changing them requires an explicit change note and
producer approval.

### Slice 0.4 — Accepted 2026-08-25

The final uniquely named Resolve Studio 21.0.4 project was created through the
supported public scripting API, saved, closed, reopened, and verified with no
public-API-observable discrepancy. Clean locked installs, the full pinned
validation gate, 85 Python tests, and the frozen-boundary audit passed. The
producer visually inspected the project and explicitly accepted Slice 0.4,
including the observed behavior that `Text+` landed on V1 for 120 frames because
the installed public API does not expose destination-track or duration
arguments for title insertion. That behavior is accepted as bounded spike
evidence, not as a solved product capability; the focused open issue is in
`docs/resolve-text-plus-destination-track-limitation.md`. Phase 0 is closed.

### Slice 0.3 — Accepted 2026-08-24

The producer manually imported both generated trial formats in Resolve Free 21
on the detected Intel macOS environment. OTIO imported all five expected linked
items and retained the expected marker. FCPXML imported the five items only
after a manual redirect to packaged media and omitted the marker; no other
difference or compensating advantage was observed. The producer approved
D-P005 to park FCPXML and explicitly accepted Slice 0.3. The deterministic
FCPXML spike remains contingency evidence rather than a maintained product
path.

### Slice 0.2 — Accepted 2026-08-24

The producer explicitly accepted Slice 0.2 after inspecting the self-contained
package, its import instructions, and the build report. Automated checks parse
the OTIO back against the handcrafted manifest event-for-event, independent
review found no unresolved issues, and CI is green. Slices 0.3 and 0.4 are
unblocked; the accepted package remains the unchanged evidence input for both.

### Slice 0.1 — Accepted 2026-08-24

The producer explicitly accepted Slice 0.1. The documented one-command
validation passed in a clean detached worktree, and GitHub Actions validation
was green. The canonical contracts and deterministic fixture kit are frozen as
of this acceptance; any later modification requires an explicit change note
and producer approval.
