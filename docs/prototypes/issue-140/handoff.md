# Issue 140 — corrected S03 connector lanes handoff

Status: **Awaiting Producer acceptance**.

## Exact artifact

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `S03 v3 authoring artifact - issue 140 connector lanes.dc.html` | 3,505,885 | `08aca68edc5f1de6cbf180b2104a611d67561088fc3240972cd6e1f4108e7c0d` |

Claude source: <https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+v3+authoring+artifact+-+issue+140+connector+lanes.dc.html>

The accepted #135 baseline remains byte-identical at 3,943,452 bytes and SHA-256
`c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea`.

## What changed

1. Every numbered narration-to-card relationship now owns a dedicated nested
   lane. Lanes remain monotonic from the narration endpoints to the matching
   cards.
2. A nudged pin's short vertical stem begins below the pin above it and is
   omitted when no non-overlapping stem remains.
3. The fixed gutter is 50px at 1280 and 42px at 1024, replacing 38px and 32px.
   Cards therefore remain aligned across rows while starting 12px or 10px
   farther right and becoming that much narrower.

No row-specific gutter was introduced. Content, row order, wording, media,
anchors, audio, controls, saved state, typography, card grammar, and the review
harness are unchanged.

## Verification

- At exact 1280×800, row 8's four lane coordinates are 41, 33, 25, and 17px.
- At exact 1024×768, row 8 uses the same 41, 33, 25, and 17px lane coordinates.
  The measured spacing is therefore 8px at both sizes; Claude's completion note
  saying “about 5px” at 1024 was conservative and is not the measured result.
- The four row-8 routes occupy distinct horizontal and vertical coordinates,
  with no shared segment, crossing, overlap, or connector-to-connector touch.
- Representative one-, two-, and three-connector rows preserve the same fixed
  card alignment and one-to-one number, color, narration endpoint, and card
  endpoint relationships.
- Visual inspection at both target sizes found no connector collision with
  narration, cards, thumbnails, labels, controls, or audio rails, and no
  horizontal overflow.
- Pointer and keyboard inspection remain wired to the same relationship, with
  the existing visible 2px focus treatment retained.
- The export contains all 22 seed rows and seven embedded thumbnails, has no
  `assets/` dependency, and contains no Claude preview-only injection.

## Checks

```sh
rtk node docs/prototypes/issue-135/check.mjs
rtk node docs/prototypes/issue-140/check.mjs
rtk git diff --check
rtk npm run validate
```

## Producer acceptance

1. Open the exact retained issue-140 export identified above.
2. Select `1280 × 800`, inspect row 8, and confirm four separated nested routes.
3. Select `1024 × 768` and repeat the row-8 check.
4. Inspect representative one-, two-, and three-connector rows for correct
   numbers, colors, endpoints, and aligned card starts.
5. Hover and keyboard-focus narration endpoints and matching cards; confirm each
   direction exposes the same relationship and focus remains visible.
6. Confirm no connector touches readable or interactive content and no
   horizontal scrollbar appears.
7. Respond `Issue #140 corrected S03 connector lanes accepted`, or name the
   first failing connector and viewport.

Only the exact acceptance phrase authorizes closing #140.
