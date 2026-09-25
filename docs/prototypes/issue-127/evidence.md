# Issue 127 controlled-pilot evidence

Status: **controlled pilot and Claude consultation complete; Producer direction pending**

## Exact artifacts

| Artifact | SHA-256 |
| --- | --- |
| `pilot.html` | `c8489d762795c232dbda0d3bbaf250ebed15b56c14ccb1e178644c557dbe4ee8` |
| `check.mjs` | `cf1987e2c4ab3b2c0ac5b575f456e5620f09b296b22b804c526bd66eccb8f5f9` |
| `adopt-adapt-defer.md` | `1408c5dc5619764b95f7f81ed56ed60662a354ac0d66142606150cb4b1ee4e46` |
| `claude-read-only-consultation.md` | `bf34f74765e61c2ed6bf592c34227a71bc657daff090623e931245549ccab4da` |
| `../../plans/issue-127-successor-s03-canonical-row-system.md` | `412e5cb36adcb6c2150e004ae61d58de778fec1c5af1acb8721ae4e3ce9ddf28` |

Recompute hashes after any correction; the values above identify the first
rendered checkpoint only.

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
reflows. Sol therefore recommends Numbered with quieter singleton ordinals.
The Producer must still exercise pointer and keyboard inspection, the music
popover controls, and both replacement toggles using the ordered checklist in
the issue plan. Visible-focus quality and the exact singleton emphasis remain
human judgments.

The Claude response was relayed by the Producer and retained verbatim in
`claude-read-only-consultation.md`; it is design evidence, not acceptance. No
claim is made that the Producer has selected the recommended direction.
