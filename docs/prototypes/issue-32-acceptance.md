# Issue 32 — design-system transfer acceptance

**Status: accepted by Matthew Belinkie on 2026-09-04, including the B11 evidence
exception.** The shared design system is wired, exported as v1.0.0 and imported
into the separate adoption specimen.

## Producer acceptance record

Matthew explicitly accepted in task `01a06506-8498-71b0-9fdc-52cd759ab9d4`:

> I accept the B11 evidence exception: use the retained Batch 5 native screenshots and Batch 7 matched measurements instead of new final-version card screenshots. Accepted issue #32 design-system wiring and transfer.

The exception accepts the named retained evidence; it does not claim the absent
final-version images exist or increase the 65 direct comparison passes. #32's
dependency on #14 is cleared when #32 is closed and Done. The exact v1.0.0
deliverables below are approved for #14 to consume. Starting #14 is separate.
The original review sheet remains unchanged as the artifact reviewed; its
pending-decision wording is superseded by this acceptance record.

## Retained review checklist

Open [**Issue 32 acceptance review**](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=Issue+32+acceptance+review.dc.html).
The sheet collects the retained card, focus and adoption images.
All ten images loaded in Codex's browser inspection. The sheet is 17,292 bytes,
Claude-retained SHA-256
`90cced74c86879b6b836df0280411d2a54b3633736857fe7e3bbd4940d3889db`.

1. **Decide the card evidence exception.** Inspect the Batch 5 before/after
   logged-comment card images at both widths. The shadow change is the approved
   decision 16: `0 16px 40px / 60%` to `0 18px 44px / 55%`.
   Those native pairs are valid. Batch 7 later replaced the card's literal
   width with an equal-valued token and retained matching open-card computed
   measurements, but its native screenshots did not show the open card.
   No final-version open-card image is retained. Accepting this exception means
   relying on the earlier native images, later matched measurements and checked
   source changes instead of obtaining two new final-version card images.
   The B5 and B7 witnesses describe different open scenes; their images are
   not interchangeable.
2. **Inspect the imported system.** Select **Script-to-Timeline Shared System
   Adoption** in the same project's file picker. Inspect its 1280 and 1024
   authored modes: typography, colors, spacing and control appearance should
   match the reviewed shared system. Tab through **Focusable one**, **Focusable
   two**, and **Focusable link**, then Shift+Tab back; the gold focus ring and
   order should be consistent. The specimen uses synthetic content and does
   not design #14's application screens.
3. **Confirm the handoff boundary.** #14 may import the exact v1.0.0 stylesheet
   below and compose the Script-to-Timeline prototype. It must preserve the
   approved token meanings and recorded exceptions. Its required Claude
   working guide is already linked from issue #14.

The producer's response to this checklist is recorded above.

## Evidence and judgment

- **65 direct original-to-final native comparison pairs pass.** The separate
  historical B5/B6/B7/A40 evidence is not added to that count.
- **Eleven popup computed comparisons pass:** 184,552 cells across 46 CSS
  properties; the only five differing cells are approved shadows. Counts,
  geometry, state witnesses and overflow match; no unresolved variables or
  console errors were reported.
- **Focus wiring is covered by retained B6 evidence:** four native zero-diff
  button/segment pairs and Codex's real forward/reverse keyboard traversal of
  both versions at both widths. Later source changes leave the rules, controls
  and keyboard order unchanged. The later F3/F4 requests duplicated coverage
  or illustrated preserved defects; they are not additional token work.
- **Adoption is verified:** the specimen imports the exact CSS, declares no
  local replacement token system, and passed computed checks and real keyboard
  checks at both authored widths. Its images are content-height captures
  (1280×875 and 1024×874), not Research's 1280×802/1024×770 app-frame images.
- The applicability review checked the actual retained image dimensions and
  contiguous B5 → B6 → B7 → A40 source history. It is retained in Claude as
  `_32-closure-applicability-review.json`, SHA-256
  `f95dd4ead2a585914b869cf98c55bcd5205fb68df368171d3d05c9c0bc3026fc`.

These are retained Claude-workspace results, with separate Codex keyboard
observations; the remote source/image hashes were not measured from local
copies. The computed report retains counts, every mismatch and file identities;
the complete identical-value matrices were not saved as raw files. Failed
checker and clipped-screenshot attempts are recorded as tool limitations.

## Frozen deliverables

| Artifact in Claude | SHA-256 |
| --- | --- |
| `VERA Redesign.dc.html` | `22d5e1ce03b7fc7a03dbc12b4e4b266185270affb109ad8a458e82e5f738012d` |
| `issue32-shared-system-v1.0.0.css` | `7c086633b9a5be03c9bcd16f6f8fa909bea216f10019ddcb706c71e5e7370248` |
| `issue32-shared-system-v1.0.0.manifest.json` | `0f33457dd0141440b566fcb8641b59689948049c96fae0bfbd2f5797c6c4787a` |
| `Script-to-Timeline Shared System Adoption.dc.html` | `38a411195bfeddb172e230646aef104f4a2a89a07b73ec0ca230f85d4b335921` |

The manifest and accepted #21 decision record retain literal-preservation and
deferred dispositions, including row 13a and the approved A40 15px/9px values.
The compact who-logged clipping issue (#54) and two existing focus defects stay
separate follow-ups. This acceptance does not claim those defects were fixed.

Detailed history: [issue-32-checkpoint.md](../issue-32-checkpoint.md).
