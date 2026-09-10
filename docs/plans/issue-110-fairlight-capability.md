# Issue 110 — Validate injected Resolve Fairlight capability boundary

## Bounded scope

Extend issue 107's accepted standard-library-only Python 3.14 injected-object
path with one synthetic stereo Fairlight probe in a fresh uniquely named
Resolve Studio project. Exercise documented public APIs through mutation and
readback for direct channel-1-to-mono mapping, Voice Isolation, Dialogue
Leveler, normalization, 48 kHz Linear PCM WAV render/import/exact-start
replacement, clip linking/enabling/removal, clean-original restoration, and
save/close/reopen. Retain a structured versioned report and an operator handoff
for issue 108.

## Exclusions

- No presenter source access, hashing, copying, listening, processing,
  rendering, upload, A/B comparison, or treatment choice.
- No production project reuse or mutation, issue 108 experiment, issue 92
  implementation, UI automation, private API, or enumerated-method claim.
- No frozen contract, generated type, fixture, golden, or accepted-test change.
- No rewrite of issue 6 or issue 107's installed launcher, config, started, or
  result files.

## Contracts, fixtures, and dependencies

No frozen product contract or fixture changes. The report is retained
investigation evidence, not a product contract. Issue 107 is the sole declared
dependency and is accepted/Done; this branch consumes its published commit.
No dependency is added: the injected path uses Python 3.14's standard library
and Resolve's documented objects.

## Safety and capability rules

- Require operator-attested External Scripting `None`, a project name beginning
  `VERA Issue 110 Fairlight Probe `, and a new output directory before adapter
  construction or mutation.
- Generate only a one-second 48 kHz synthetic stereo sine probe. Channel 1 is
  440 Hz and channel 2 is 880 Hz so the channel exclusion is unambiguous.
- A `supported-api` result requires a real changed value and matching readback;
  the prior state is restored where a documented setter exists.
- An exact named Fairlight preset may be catalogued, but EQ/dynamics remains
  `operator-only` because the public API exposes no preset/EQ/dynamics state
  getter or safe preset reset. The automated probe does not alter the clean
  timeline merely because a preset name exists.
- Any unsupported or failed path retains the synthetic source bytes and clean
  timeline item when possible, records the failed restoration if not, and
  never weakens the external-scripting setting.

## Automated checks

- Stable report schema/serialization and complete status vocabulary.
- Refusal before adapter/file creation for unsafe settings and non-unique
  targets; absent/unknown preset refusal without mutation.
- High-level failure and restoration-failure evidence.
- A strict fake of the documented Resolve 21.1 API verifies the full mutation,
  readback, WAV header, replacement, removal, restoration, and reopen sequence.
- Python `-S` import and staged-launcher checks prove the injected path loads no
  external bridge, virtual environment, or Python 3.12 native dependency.
- Focused pytest, Ruff, strict mypy, full `npm run validate`, diff checks, and
  frozen contracts/fixtures/test-data audit.

## External acceptance

Follow the generated numbered operator handoff in the installed Workflow
Integration **VERA Issue 110 Fairlight Probe**, while External Scripting remains
`None`. Retain the exact Resolve/Python versions, installed API-document hashes,
report, handoff, unique project name, and observed Fairlight state. Move the
issue only to `In review`; External evidence, not an agent self-report, decides
acceptance.
