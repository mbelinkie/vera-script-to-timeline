# Issue 127 controlled-pilot evidence

Status: **corrected bounded successor accepted by the Producer on 25 September 2026**

## Exact artifacts

| Artifact | SHA-256 |
| --- | --- |
| `pilot.html` | `c8489d762795c232dbda0d3bbaf250ebed15b56c14ccb1e178644c557dbe4ee8` |
| `check.mjs` | `cf1987e2c4ab3b2c0ac5b575f456e5620f09b296b22b804c526bd66eccb8f5f9` |
| `adopt-adapt-defer.md` | `889093ffda6047c903b503cfbf97720714530fcbfcfd868048dde7a028f30514` |
| `claude-read-only-consultation.md` | `bf34f74765e61c2ed6bf592c34227a71bc657daff090623e931245549ccab4da` |
| `../../plans/issue-127-successor-s03-canonical-row-system.md` | `d9d5ffc62fac1c7db206a0172fe8f48032f52a860e34d808e8bd9cde37187318` |

These hashes identify the current retained planning/comparison checkpoint.

## Preserved boundaries

- Accepted S03 v2, unaccepted v3, #123, S05, contracts, fixtures, goldens,
  generated types, and production code were not edited.
- The four explicitly supplied #123/design-guidance paths were read in place
  only and remain outside this worktree.
- The pilot uses no reconciliation red/green, Added in Resolve language, or
  Accept/Reject/Defer product controls.
- This artifact is an interaction/hierarchy study, not a source-fidelity claim
  or accepted successor.

## Automated result

Command:

```sh
rtk node docs/prototypes/issue-127/check.mjs
```

Result: **pass** — four states at two viewports; eight screenshots retained.

| State | 1280×800 | 1024×768 |
| --- | --- | --- |
| Minimal, default text/thumbnails, unresolved intent | `evidence/minimal-default-1280x800.png` | `evidence/minimal-default-1024x768.png` |
| Numbered, default text/thumbnails, unresolved intent | `evidence/numbered-default-1280x800.png` | `evidence/numbered-default-1024x768.png` |
| Minimal, small text, 0% thumbnails, replacements | `evidence/minimal-compact-1280x800.png` | `evidence/minimal-compact-1024x768.png` |
| Numbered, small text, 0% thumbnails, replacements | `evidence/numbered-compact-1280x800.png` | `evidence/numbered-compact-1024x768.png` |

The check rejects horizontal document overflow and card/visual-column width
overflow. It also asserts all seven stable range IDs link at least two
inspectable surfaces, endpoint groups use non-wrapping anatomy, source
bookkeeping remains in Details, all three sound states exist, and the product
frame excludes reconciliation actions and provenance language. It also checks
the retained comparison: Minimal hides only the two linked ordinal surfaces for
the one-non-OC-card row, while Numbered hides none. Both modes mark that
singleton ordinal as quiet so Numbered can preserve identity without restoring
full visual emphasis.

`rtk git diff --check` also passed.

The repository-wide `rtk npm run validate` command did not reach repository
validation. This worktree has no installed npm dependencies, so contract
generation stopped on missing `json-schema-to-typescript`; the active runtime
was Node `26.5.0` while `.nvmrc` and `package.json` require Node `24.19.x`.
No dependency or toolchain installation was performed for this design-only
checkpoint. This environment block remains to be cleared before a later
successor implementation claims full validation.

## Manual judgment still required

Claude's hostile case established that Minimal makes an untouched event gain or
lose its visible name when a neighboring card changes or row presentation
reflows. The Producer chose persistent numbers, then clarified that visual
ordinals reset in every semantic row. The corrected successor therefore uses
row-plus-ordinal human references and stable IDs for machine identity. The
Producer must still judge the straight Graphic ticks, M1/M2 rails, focus
quality, and exact singleton emphasis using the ordered checklist in the issue
plan.

The Claude response was relayed by the Producer and retained verbatim in
`claude-read-only-consultation.md`; it is design evidence, not acceptance. The
Producer then selected **Numbered with quieter singleton ordinals** and
authorized the bounded successor. That decision does not accept or promote the
successor.

## Bounded successor checkpoint

Exact files:

- `s03-successor-pilot.dc.html` — `edb83bae6086eaeb72c0ca827ffe0a309f4461fd5d7a23c07975a77f2169c86a`
- `check-successor.mjs` — `f86729c546021c28aa7eb213a2839de6eb204fe7ab1301ac4a7af0903438d71e`
- `successor-handoff.md` — `a0338b71f75d9c114692c37d28a3b43c3192513ed5d161084fab099c7c000d40`
- `claude-successor-critique.md` — `790f2cb737691d3451e63d7ab412794a4814728634211bca5d99b3b9a27d334b`
- `source-v2/` — immutable local copy of accepted v2 and the runtime, shared
  CSS, and seven thumbnail assets bundled into the self-contained successor

The accepted v2 HTML still hashes to
`632cfce2b9fea8832b7c13387811d5739518f1247d10bb81ae605671b2005535`.
The successor alone was edited.

Command:

```sh
rtk node docs/prototypes/issue-127/check-successor.mjs
```

Result: **pass** — four review states and five screenshots retained.

| State | Evidence |
| --- | --- |
| 1280×800, default text/thumbnails plus pointer/keyboard interaction | `successor-evidence/default-1280x800.png` |
| 1280×800, Row 3 cross-clip Graphic and lower rows | `successor-evidence/default-lower-1280x800.png` |
| 1024×768, default text/thumbnails | `successor-evidence/compact-1024x768.png` |
| 1280×800, small text and 0% thumbnails | `successor-evidence/small-zero-1280x800.png` |
| 1024×768, small text, 0% thumbnails, and music popover | `successor-evidence/compact-small-zero-1024x768.png` |

The check verifies source immutability, five independent authoring rows, no
horizontal/card overflow, row-local visual ordinals, quieter singleton versus
standard multi-visual emphasis, sixteen non-wrapping endpoint groups, clip
brackets versus straight Graphic ticks, the unindented Graphic spanning both
Row 3 clips, correct first/resumed On Camera labels, three M1 rail segments and
one contained M2 segment, exact music anchors with no music glyphs in prose,
pointer/keyboard inspection, trim/fade controls, and Need to Find replacement
with ordinal `1` plus both exact anchors unchanged. It also rejects any local
`source-v2` dependency in the handoff HTML.

Visual inspection confirmed one primary type pill per card, dashed unindented
Graphic cards, compact No/Quiet-sound B-roll, M1/M2 rails, and the music popover
at both densities. The remaining questions are the bounded qualitative
judgments in `claude-successor-critique.md` and `successor-handoff.md`.

## Claude and Producer acceptance

The self-contained artifact was imported into Claude as **Script to Timeline -
S03 Successor Pilot - Issue 127**. The Producer reported that Claude liked the
artifact and requested no bounded revision. The Producer then recorded the
exact acceptance response `Issue #127 successor accepted` on 25 September
2026.

Relative font-size calibration remains deliberately deferred to the later
complete combined S03 v3 artifact; it is not a defect in this bounded design
decision. No #123, S05, contract, fixture, golden, generated-type, or production
code change was made.

Final verification reran the successor check successfully, passed
`git diff --check`, and passed the complete `npm run validate` gate with Node
24.19.0/npm 11.17.0 after installing the existing locked dependencies. No
manifest or lockfile changed.

The repository-wide validation limitation is unchanged: npm dependencies are
absent and the active Node runtime is 26.5.0 while the repository requires
24.19.x. No dependency or toolchain installation was performed.
