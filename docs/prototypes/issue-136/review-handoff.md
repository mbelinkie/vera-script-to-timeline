# Issue 136 — paired corpus and renderer grammar review handoff

Status: **ready for Producer review; not accepted and not Done**

## Bounded slice

- **Scope:** verify and present the exact 35-scenario paired corpus, named cases,
  direction rules, Harbor Lights allocation, controlled states, shared harness,
  Graphic inspection grammar and C12 connector-comparison protocol retained by
  issue #136.
- **Exclusions:** no renderer or harness construction; no #123 or S05 successor;
  no edits to accepted #123, S03, S05, #127, #135 or #128 pilot artifacts; no
  contract, fixture, golden, generated-type, production or Resolve change.
- **Touched contracts/fixtures:** none.
- **Dependency:** #135 is closed and Done. Its exact accepted export and
  Producer-acceptance handoff are verified below.
- **New dependency:** none.

The two planning documents remain the complete decision authority. This
handoff does not restate or replace their literal scenario definitions.

## Exact review authority and retained evidence

| Artifact | SHA-256 | Result |
| --- | --- | --- |
| `docs/prototypes/issue-128/paired-123-s05-scenario-corpus-recommendation.md` | `aa97fddbe25cb0870032c408c26d5634562bab7ed25030eb4c0070841d639344` | Matches checkpoint `db16cec` |
| `docs/prototypes/issue-128/paired-123-s05-scenario-content-spec.md` | `f355a8e9ee08326c09a78c929b848ea4c9681e2a86889bc1eac4b5c80016a6c0` | Matches checkpoint `db16cec` |
| `docs/prototypes/issue-135/S03 v3 authoring artifact - issue 135 export v2.dc.html` | `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea` | Matches the #135 handoff accepted by the Producer |

Run:

```sh
rtk node docs/prototypes/issue-136/check.mjs
```

Expected:

```text
PASS planning documents match checkpoint hashes
PASS accepted #135 source hash, Producer provenance, 22 rows and 18 narrated rows
PASS exact corpus: 17 shared + 8 inbound-only + 10 outbound-only = 35 scenarios
PASS allocation matrix: 43 named cases and controlled-state rows
PASS direction, harness, Graphic grammar, C07/O05 corrections and C12 comparison gates
```

The check verifies that the scenario headings are exactly `C01–C17`,
`I01–I08` and `O01–O10`; that the allocation matrix contains every named case
once; that every accepted narrated row is present word-for-word; and that the
settled direction, harness, Graphic, C07, O05, O09 and C12 rules remain in the
retained authority. `CR-I` and `CR-O` are compositions and are not counted as
scenarios.

`rtk git diff --check` and the retained #135 check also pass. Repository-wide
`rtk npm run validate` cannot start in this worktree because the existing
`json-schema-to-typescript` package is not installed. No dependency or
toolchain installation was performed for this documents-only decision slice.

## Audit result

- #123 consistently uses `SCRIPT = older` and `RESOLVE = newer`; S05 uses
  `RESOLVE v3 = older` and `SCRIPT = newer`. C17 additionally names its common
  ancestor and both current states.
- The accepted 22-row Harbor Lights bank supplies every allocation. No row was
  added and no narration was invented. The four explicitly provisional media
  identities remain visible for Producer judgment: C09
  `salt-crystal-cu_0915.mov`, I01 `gauge-screen-flatline_0814.mov`, I02
  `wake-overview_0918.mov` and I03 `housing-waterline_0911.mov`.
- C07 retains the corrected contiguous cut point: Footage 1 ends on
  `around the opening,`; Footage 2 starts on `which changes`.
- O05 places r21 once, after r18 and before `Closing the Loop`; both states omit
  its canonical post-r20 occurrence, so the fixture cannot duplicate r21.
- The neutral-gray frame is harness metadata outside the exact measured
  product shell. Its plain-text ID sits in the top-border gap; it is not a tab,
  fill, scroll container or consumer of the `1280 × 800` / `1024 × 768`
  viewport.
- Transparent Graphics use a dashed card and dashed inspection underline;
  full-frame Graphics keep their fill and use a solid inspection underline.
  Neither underlines at rest. Both keep the accepted shade and straight
  `│N` / `N│` marks. Dotted remains reserved for music beds and boundary
  editing; dashed and solid underlines may never appear together.
- C12 compares accepted #135 two-track routing with #128 nested connector lanes
  on the same maximum-density case at both target viewports. The comparison
  measures obstruction, traceability, gutter cost, overflow and pointer/
  keyboard correspondence. It deliberately does **not** choose a winner in
  prose; the Producer chooses after both are rendered in the shared-foundation
  issue.
- O09 retains document-order execution, stop-on-first-failure results,
  unchanged v3 authority, one frozen plan and same-plan Retry.

## Producer acceptance checklist

Deterministic hashes, counts and accepted-source comparisons above are already
complete. The remaining work is product judgment on the literal authority.

1. Open
   `docs/prototypes/issue-128/paired-123-s05-scenario-content-spec.md` at
   **Fixture and combined-review model** and **Allocation and controlled-state
   matrix**. Confirm the corpus is exactly 17 shared, eight #123-only and ten
   S05-only scenarios; `CR-I` and `CR-O` only compose existing entries.
   Expected: every named case appears once in the matrix with its rows/context
   and controlled state, and the direction rule is explicit.
2. In that same document, review **Canonical Harbor Lights row bank** and the
   four provisional media identities listed above. Confirm the accepted row
   words and identities are suitable for the scenarios. Expected: 22 stable
   rows, no added narration, and either acceptance of each provisional media
   name or the first exact name that must change.
3. Review **Shared scenario content**, **#123-only scenario content** and
   **S05-only scenario content** in order. Judge the literal titles, summaries,
   older/newer states, neighbors, anchors, consequences and controlled-state
   copy. Pay particular attention to C07, C12, C17, O05, O07 and O09.
   Expected: each scenario is independently understandable and the same `C`
   geometry can be shared without erasing direction-specific decisions.
4. Review **Harness**, **Graphic inspection grammar** and **Shared surface
   navigation** near the top of the content specification. Expected: the frame
   owns no measured viewport space; identity remains plain text; pointer and
   keyboard inspection agree; Graphic styles never show simultaneous dashed
   and solid underlines.
5. Open
   `docs/prototypes/issue-128/paired-123-s05-scenario-corpus-recommendation.md`
   at **Renderer grammar comparison experiment**. Confirm C12 is the sole
   comparison host, both routing systems are rendered at both target
   viewports, the five comparison criteria are sufficient, and the routing
   winner remains a later visual Producer choice rather than an inferred prose
   decision.
6. If all judgments pass, respond exactly:
   **`Issue #136 corpus and renderer grammar accepted.`**
   If not, respond:
   **`Issue #136 needs revision: <first unacceptable scenario or rule>; expected <smallest correction>.`**

Issue #136 must remain **In review** until the Producer gives the acceptance
response above.
