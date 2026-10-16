# #207 — concrete Producer decision

**Producer-accepted, design only**, 2026-10-14. [Acceptance record](acceptance.md).
The checklist below records the reviewed decision; the approved note stays
byte-identical. Exact artifact:
[CN-207-ID1](../../plans/issue-207-target-identity-handoff.md).
Raw file SHA256:
`e02da9eacd54fb90b7ca4ba63f1c3f72f37b997e426828ad8237d0bd1adc6006`.

The operation lets you supply the current saved disposable target's two visible
names. An installed, read-only operation records the real UIDs. You then confirm
that exact result separately before #204 can receive authority. You do not have
to discover invisible UIDs. No code or app operation occurs in #207.

## Ordered acceptance checklist

1. Open the linked note and read **Decision, scope and existing evidence** and
   **Finite reads, target drift and honest limits**. Expected: only the named
   current saved disposable NONproduction target is read; two complete agreeing
   name/UID reads; no selecting/saving/rendering; observation grants no effect.
   Decide whether this is the intended bounded identity handoff.
2. Read **Freshness, replay, confirmation and receipt consumption**. Expected:
   a separate personal confirmation binds the actual result hash and all four
   identifiers before #204 authority; 30-minute attended window and one use per
   capture/receipt; expiry or uncertain failure requires fresh capture. The
   normal request/restart transition is permitted with renewed confirmation.
   Decide whether the proposed window and retry cost are acceptable.
3. Read **Exact future ownership and integration baseline** and **Change note**.
   Expected: #208 uses its own worktree, adopts reviewed unmerged #204 source
   onto accepted main under a coordinator freeze/grant, returns one reviewed
   integrated revision, and creates a fresh release. #204 does not need to close
   first. No frozen boundary or ordinary-build guard change is approved here.
   Accept that route, or name the precise section to change.

If all three judgments are accepted, reply exactly:

> Approve CN-207-ID1 SHA256 e02da9eacd54fb90b7ca4ba63f1c3f72f37b997e426828ad8237d0bd1adc6006, design only.

To reject or amend, reply `Change CN-207-ID1: <section and required change>`.
Any note edit changes the hash and requires acceptance of the new artifact.
This accepts a design; it issues no target authority, installation/runtime grant
or successor dispatch. Explicit acceptance is now recorded; #208 still needs
its source-ownership handoff and separate grants.

## Retained evidence and limited checks

- [Receipt audit](receipt-audit.md): assignment/baseline, independently rehashed
  actual #109 result and missing UID boundary, accepted-interface inspection,
  clean #204 checkpoint and unmerged source prerequisite.
- [Design review](design-review.md): owner adversarial static review and fixes;
  no independent/runtime qualification claimed.
- [Implementation evidence checklist](implementation-checklist.md): meaningful
  negative cases, actual Studio/operator evidence and final validation ordering.

Final documentation checks: whitespace/diff confinement, all relative Markdown
links resolve, exact note hash matches this checklist. The design delivery was
this new note and four new #207 verification Markdown files; later acceptance
adds only the receipt/record and this status update. The four #204 runtime
files were compared directly between reviewed 724a829 and checkpoint de4ed9b:
all byte-identical. Current remote main 017e7cf was independently rechecked;
#192 changes do not overlap the six listed source prerequisite paths, and the
note requires preserving them during composition. No source/config/lock/contract/fixture/golden/accepted test
was changed. No tests, fast/full, Claude, media, install or native operation ran.
Checks are documentation evidence only, not prior-suite equivalence or External
acceptance. Roadmap and final delivery commit are recorded on issue #207.
