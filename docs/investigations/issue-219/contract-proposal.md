# #219 — provisional Table target contract

Producer-accepted per-revision proposal; see producer-acceptance.md.
Studio readback, save/reopen and rendered boundary/repeat
checks have passed for the subset below. This document adds no shared wire schema or
production behavior. The issue-owned machine-readable target manifest is
[`target-manifest.json`](target-manifest.json), exact file SHA-256
`dc21391f032d35cadab909e590302bc7ed8a46567703da93b4f82846d7948424`.

## Bounded inventory

Three supplied concrete revisions were inspected read-only; inventory is closed.

| Candidate | Bytes | SHA-256 | Disposition |
| --- | ---: | --- | --- |
| EV24 Table, installed | 194782 | `869bffd705ac949a58bcb25d6bc80de5027219792336f0d599be81162447440a` | Selected; actual Studio proof for the fixed subset below. Producer contract acceptance pending. |
| EV24 Quote Box, installed | 36597 | `b089282e6ccab68426eb5f0b39168cb11c051e6798cbe08230b41bf640ff3754` | Not selected; published italic range is not proof of independent semantic highlight targets. No live probe. |
| EV24 Table, newer uninstalled source build | 224627 | `1fc770b580cb205824a693dee592d7e044764b25e1d58a407fc8d2eb294cb274` | Excluded from live selection. Different bytes; no rebuild, installation or source merging. |

Whole-setting SHA-256 is the conservative graph fingerprint. Exact imported
bytes, live graph/control identity and type must all match the selected revision.
Installed titles and existing clip instances are not interchangeable by name.
No proprietary bytes or private paths are included here.

## Synthetic dataset and identity proposal

Freeze the exact UTF-8 text below, tabs between cells, LF between lines, no final
newline. It is a probe-owned dataset, not a production fixture or a claim that the
template supplies durable row IDs.

```text
ITEM\tVALUE
Alpha\t18
Beta\t27
Gamma\t9
```

The notation `\t` above means one actual tab. Exact dataset SHA-256:
`1aec6e192c64748a6102507e45c59bb5d193bb8ae5e43e3e5e2469672d220d64`.
A manually assigned manifest revision owns these
IDs; neither display text nor Fusion node names generate them.

| Stable target ID | Human label | Kind | Frozen binding | Proposed states |
| --- | --- | --- | --- | --- |
| `target-a` | Alpha row | row | global body position 1 | `base`, `emphasis` |
| `target-b` | Beta row | row | global body position 2 | `base`, `emphasis` |

Only these two IDs are addressable. Gamma is a base-state visual control.
Any dataset edit, reorder, row addition/removal or label change invalidates this
entire mapping; reject before mutation until a separately reviewed manifest
revision explicitly binds the new dataset. Never repair identity by label match
or silently move a target. Target rename/removal, unsupported ID/state or wrong
template/data/manifest digest refuses before disposable setup. A live imported
graph/control/type mismatch refuses before any control/state write; disposable
timeline/clip/import/MediaOut setup has already occurred and remains as a refused
scratch timeline. This deliberately conservative scope proves no
general data-reorder identity system.

The pinned manifest's shorthand “before mutation” means before semantic control
assignment for live-discovered graph/type mismatches, not before import/setup.
Its historical status string still says awaiting render; current evidence is
recorded here without changing the tested manifest pin. The unit tests exercise
pure refusal flags, not mocked versions of the actual live graph inspector.
Actual live graph inspection has positive runtime coverage, but no injected
live mismatch test; do not present the flags as that stronger proof.

## Trusted binding proposal

The pinned macro publishes `HighlightRows` through its internal `Controls`
Background. Static declaration: Text / TextEditControl, default empty string.
For this two-target profile the complete allowed serialized values are `""`,
`"1"`, `"2"`, `"1,2"`, in increasing numeric order. Base means target absent;
emphasis means target present. Both targets share one set-valued control, so the
probe must write the aggregate state rather than clobber another active target.
Multiple static values are evidence of candidate suitability only. The exact
static declaration subset (TableData/LayoutMode/HighlightRows, stripped lines
in source order separated by LF without a final LF) has SHA-256
`4884b85a9e3d93af3be86fb836b63ed98cf0664e128e6e21e5f0453141fd343c`.

Authored emphasis is the template's existing red band treatment; no authored
color, layout, font or animation is changed. No muted/custom state is proposed.
No continuous interpolation or transition is supported by this proposal.
Discrete changes require actual boundary/readback/render proof. Actual Studio
21.1.1 build 10 readback shows that explicit-time `SetInput` alone overwrites a
constant. `AddModifier("HighlightRows", "BezierSpline")` creates the native
Text-output modifier `ControlsHighlightRows`; subsequent timed writes preserve
stepped values. This is native keyframing of the imported unchanged template,
not source redesign or expression injection. Fusion resolves the macro's
published output to its pinned internal `DiagnosticOver` Merge. The probe checks
all 127 source processing nodes plus exactly one MediaOut and one native modifier.

## Hardcoded schedule to probe

Proposed coordinates: 24 fps, 1920×1080, 240 frames, occurrence-local integer
frames `[0,240)`, half-open intervals. Record timeline start and actual comp
range and prove their mapping; do not assume comp frame zero. Keep the authored
entrance and exit. Probe boundaries below lie in the hold except the explicit
until-Graphic-end state, whose visibility remains subject to authored exit.

| Case | Ordered cue inputs | Expected aggregate values |
| --- | --- | --- |
| sequential | A emphasis `[48,72)`; B emphasis `[72,96)` | 47:`""`; 48/71:`"1"`; 72/95:`"2"`; 96:`""` |
| start-only | A emphasis start 48, explicit until next cue at 72; B emphasis start 72, explicit until Graphic end 240 | 47:`""`; 48/71:`"1"`; 72/239:`"2"`; no frame 240 inside clip |
| disjoint overlap | A emphasis `[48,96)`; B emphasis `[72,120)` | 47:`""`; 48/71:`"1"`; 72/95:`"1,2"`; 96/119:`"2"`; 120:`""` |
| continuation | A emphasis `[48,72)`; A emphasis `[72,96)` | 47:`""`; 48/71/72/95:`"1"`; 96:`""`; no base flash at 72 |

Here A/B abbreviate `target-a`/`target-b`. The start-only example uses the very
next ordered cue and never requires a choice between global-next and
same-target-next behavior. General resolution belongs to #167.

Refuse the entire schedule before mutation for missing/unknown target or state,
empty target list, unspecified start-only end policy, out-of-range/reversed time,
unordered cues, or overlapping `base` and `emphasis` on the same target. Negative
checks must assert zero application writes. Repeating equal emphasis over a
touching boundary is continuation, not contradiction.

## Support and refusal matrix

| Capability | Current evidence/status |
| --- | --- |
| Exact selected bytes and static declared control | Inspected; hashes above |
| Static independent targets and aggregate overlap | Actual Studio readback and rendered row-band checks passed |
| Discrete timed changes and exact frame boundaries | Native modifier readback and rendered samples passed at listed boundaries |
| Deterministic reset and continuation | Rendered base restoration at 96/120; continuation has no base flash at 72 |
| Save/reopen and identical repeat | Separate imports in the same project/session retain all four schedules after reopen and one render batch; 36/36 matching decoded RGB frame pairs identical |
| Studio baseline | Actual DaVinci Resolve Studio 21.1.1 build 10 on macOS |
| Free | Untested/unavailable; explicit manual completion or blocked use. No substitute or baking claim. |
| Rights/fonts | Producer-supplied authored asset; exact Table use/font assumptions need final Producer confirmation; no distribution approval inferred from #12 |
| Private receipt/render index | Retained; local operator entry point in README |
| Interpolation/transitions | Unsupported; only stepped states tested |
| Other datasets, rows, durations, frame rates, versions | Unqualified; fail closed for this fixed profile |
| Review and final validation | Initial/delta Claude GO; final local full gate exit0 on 5ae5e34; see final-validation.json |
| Producer judgment | Explicit target/rights/frame-review approval; retained render-format difference accepted; see producer-acceptance.md |

72/72 Deliver PNG jobs completed. All 28 hold-frame samples per run have expected
red-band presence/absence for Alpha/Beta/Gamma; eight authored endpoints per
paired set are black at frame 0 or 239. Matching PNG file bytes differ only in
the ICC profile creation timestamp; decompressed pixel bytes are identical.
The start-only state remains `2` at frame 239 in control readback while authored
exit makes that frame black. State lifetime does not override authored visibility.

Run A was prepared by the earlier four-case batch version of `prepare`; Run B
used the later single-case-call version. Both used the same hardcoded `CASES`
and state-write sequence. The exact pre-refactor Run A script hash was not
retained. Current-code readbacks before/after reopen and after render independently
confirm both resulting instances, and the rendered comparison is over those
instances. This is a repeat over identical inputs, not independent projects,
fresh application launches or identical preparer binaries.

This is exact sampled-frame evidence, not a claim to have inspected every frame,
played a continuous movie, or proved subframe interpolation. All raw images,
composition exports, native attributes and source pointers remain private.

The eventual contract must retain the exact manifest/control hashes, tested
state/timing subset and support/refusal evidence. #167 still owns narration
timing compilation, production validation, runtime mutation, reports and fallback.
This probe alone cannot qualify that runtime or any broader template family.
