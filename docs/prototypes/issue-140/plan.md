# Issue 140 plan — canonical S03 connector lanes

## Scope

Use Claude Design to produce a separate successor to the exact accepted #135
export, changing only numbered narration-to-card connector routing. Every
relationship gets a dedicated nested lane with no shared route segment,
crossing, overlap, or connector-to-connector intersection.

## Exclusions

No Codex-authored visual approximation; no change to S01–S03 content,
authoring behavior, controls, typography, card grammar, media, audio, or saved
state; no #137 foundation, #123/S05 successor, production renderer, Resolve
integration, or unrelated redesign.

## Frozen boundaries

`contracts/`, `fixtures/`, accepted tests, goldens, generated types, and the
accepted #135 export are untouched. No dependency is added. #135 is the sole
dependency because it supplies the closed, Producer-accepted source; the live
roadmap confirms it is closed and Done.

## Retained identity and evidence

- Accepted source:
  `docs/prototypes/issue-135/S03 v3 authoring artifact - issue 135 export v2.dc.html`
  (`3,943,452` bytes; SHA-256
  `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea`).
- Producer reference image: `904 × 1080`, `350,825` bytes; SHA-256
  `f408090f78509e522a79a8930bd4f9f43948091a66d66ed43826c995b20f2590`.
- Retained Claude export:
  `S03 v3 authoring artifact - issue 140 connector lanes.dc.html`
  (`3,505,885` bytes; SHA-256
  `08aca68edc5f1de6cbf180b2104a611d67561088fc3240972cd6e1f4108e7c0d`).

## Checks

1. Re-run the accepted #135 check and prove its export remains byte-identical.
2. Hash and retain the exact Claude source/export.
3. At exact `1280 × 800` and `1024 × 768`, inspect the dense four-connector
   row 8 plus representative ordinary rows.
4. Measure or inspect for unique lanes, connector intersections, content
   collisions, horizontal overflow, one-to-one number/color/endpoints,
   pointer/keyboard correspondence, and visible focus.
5. Compare accepted and proposed artifacts so every non-routing difference is
   explicitly identified.
6. Run the focused check, `git diff --check`, and the repository validation
   gate where the pinned local toolchain permits it.

## Producer acceptance

Leave #140 `In review`. The Producer opens the exact retained export, repeats
the two target viewport checks, inspects row 8 and ordinary rows, exercises
pointer and keyboard relationship inspection, and either responds
`Issue #140 corrected S03 connector lanes accepted` or names the first failing
connector and viewport. Only the former authorizes closing the issue.
