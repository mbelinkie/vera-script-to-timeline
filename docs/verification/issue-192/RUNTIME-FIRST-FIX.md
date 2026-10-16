# #192 runtime checkpoint and selected-audio fixture fix

Producer resumed this chat on 2026-10-13. Usage was 29% five-hour / 51%
weekly, below the stop threshold. The retained coordinator grant permits
own-scope runtime fixes and affected serial reruns, without weakening existing
package, source, assertion or timeout checks.

## Retained first runtime result

`runtime-1` tested exact commit
22f7ba4f8d0b082ce3b7a40934b09fb0a8f2a2a2 on Node24.19.0/Python3.12.14.
Serial `pytest -x --durations=25` collected34 tests. Ten new transport,
currentness, reject, reopen and read-only recovery checks passed. The actual
public B1/B3/core/package path failed while preparing its initial synthetic
package. The four selected #190 regression functions were not reached.
Exit1, no signal, duration59.32s; no partial result supplies acceptance.

Immutable evidence remains in `out/issue192/runtime-1/`: `start.json`,
`complete.json`, `check.log`; log SHA256
ff7d37d59007a3adac62cec4eb0f1fc650d7898af3dae5cc35cdc5703d89087e.
The start receipt lists selected nodes and why, input hashes, source identity,
process, tool binaries/versions/hashes and environment.

## Diagnosed mismatch and bounded correction

The unchanged package validator refused `prep192:prep:30` because its audio
coordinates did not bind to P2 geometry. The retained fixture receipt's
package range covers200 frames, but its audio record and sidecar cover the
whole250-frame source (500500 samples instead of400400).

Only the newly authored `tests/issue192_public_case.py` changes. The fixture
retains full source PCM separately and creates each prepared sidecar from
the requested exact rational package interval. First/exclusive source and
resampled sample coordinates, decoded sample count, first-sample time,
boundary offset and sidecar content hash bind those actual selected bytes.
Revised preparations select from the retained full source, so a new measured
duration can shorten or extend within actual handles. Prior sources/sidecars
remain intact. No package validator, accepted fixture/test, inference result,
provider report, contract or assertion is modified.

Focused Ruff and format pass; strict mypy failed initially on declaration
placement and passes after moving the typed source-audio inventory into the
constructor. All attempts are retained in `out/issue192/focused-22` through
`focused-27` named directories. This fixture correction still requires its
actual public-path rerun; static checks do not prove it works.

## Rerun and remaining gates

Run only the affected public-path test file and the unchanged #190 nodes not
yet reached: original delivery/read-only recovery, drifted delivery ancestry,
fractional refusal before adapter creation, and capture currentness refusal.
The ten already-passing transport checks do not import the changed public
fixture; their production source, fixture imports, config and tools are
unchanged. Reuse them only as transport evidence, never as combined B1/B3
acceptance. The next receipt binds new current source/fixture hashes and
creates all packages/bindings in fresh temporary directories.

No global fast/full validation, adversarial/Claude review, real Resolve,
provider call, FFmpeg conversion, original-media operation, PR or closure
has occurred. Actual #202 Closed/Done and all final gates remain required.
