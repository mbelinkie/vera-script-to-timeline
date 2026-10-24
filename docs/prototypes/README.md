# Retained design inputs for issue #125

This directory recovers existing design sources, not a new design or a new
acceptance. The live roadmap still owns scope and status. Current `AGENTS.md`
and verification policy supersede workflow instructions in historical handoffs.

## Continue the advanced design

Matthew selected **Shared S03 Review Foundation - issue 137 r6** as the starting
working page for #125. Before editing it, #125 must explain its goals, settled
decisions and remaining choices in plain English. Continue the established row,
rail and connector design rather than reconstructing an earlier pilot.

- Latest located working editable page:
  [issue-137 r6](<issue-137/Shared S03 Review Foundation - issue 137 r6.dc.html>).
- Matching standalone preview:
  [issue-137 r6 export](<issue-137/Shared S03 Review Foundation - issue 137 export r6.html>).
- Accepted ordinary authoring/connector baseline:
  [issue-140](<issue-140/S03 v3 authoring artifact - issue 140 connector lanes.dc.html>).
- Paired scenario authority:
  [content specification](issue-128/paired-123-s05-scenario-content-spec.md) and
  [corpus recommendation](issue-128/paired-123-s05-scenario-corpus-recommendation.md),
  accepted through #136 and subject to later explicit Producer amendments.
- Earlier accepted inbound design:
  [issue-123 handoff](issue-123/ACCEPTED-HANDOFF.md).

The working r6 source/export came byte-for-byte from the September 30 design
archive. They are advanced but **not accepted as complete**. The old chat's r7
correction prompt was drafted, not implemented or sent. Check the current
Claude project for a genuinely newer page before making edits; do not invent a
missing r7 or treat the earlier #128 pilot as the latest design.

The r6 audit and unsent correction prompt remain in the original #137
worktree; #125's issue links their exact relative filenames and both old chat
IDs. Those notes are unresolved findings, not a second acceptance or an order
to repeat the whole review design inside the authoring issue. The current #125
scope covers transitions, comments, reorganization and other adopted authoring
footprints; downstream review work retains its own owners.

## Recovery provenance

| Recovered material | Historical source |
| --- | --- |
| #123 r2 export, annotation guide, handoff and verification | `70dfcf265bc17028875e05e0e9b7e7a2d0362f7d` |
| Accepted S03 v2 comparison source and its render assets | `cdaa3106da91fb5a040c8bbde22e2c61c0d3e162`, only `issue-127/source-v2/` |
| #128 planning documents | `db16cec` |
| #135 v2 export, evidence and accepted handoff | `570c8d5`, `d6b363c`, `367f776` |
| #136 checker and historical review handoff | `cf72d5828a040dd859e30966e72bdab5f0450753` |
| #140 accepted connector source, checker and handoff | `ad8d9845f48ccd8b3cadec585ab41d2dad3acd34` |

The #136 and #140 handoffs predate their acceptance and still say review-ready;
the recorded Producer acceptance on their GitHub issues remains authoritative.
No new Producer judgment is needed to recover these exact sources into `main`.
The #140 HTML references two relative support files that its historical commit
omitted. They are restored unchanged from the accepted #127 `source-v2/`
directory; the HTML itself is not changed.

Key SHA-256 identities (not normalized or reformatted):

- #123 r2: `b4fae31553a72925315c213260e515f32bc97b289d244905daf815402289fa03`
- #135: `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea`
- #140: `08aca68edc5f1de6cbf180b2104a611d67561088fc3240972cd6e1f4108e7c0d`
- #137 r6 editable: `fe9d0bb63405faa1fba57938e1dbffe8a420b12241b9e6c569b180412895626b`
- #137 r6 standalone: `25d82916e9f0427e1423aa502d6a2cd6ebd4fdc3f67588d7f327892c86b831ce`

## Focused checks

With the repository's `.nvmrc` runtime:

```sh
node docs/prototypes/issue-135/check.mjs
node docs/prototypes/issue-136/check.mjs
node docs/prototypes/issue-140/check.mjs
```

These original checks verify retained bytes, baseline provenance, row/scenario
content and connector source markers. They do not prove new browser rendering,
new Producer acceptance, production behavior or complete design coverage.

Historical HTML whitespace is deliberately preserved to retain accepted hashes;
do not reformat the exported sources. The #123 failed first export is retained
and labeled as failed in its handoff, not an alternative accepted baseline.
