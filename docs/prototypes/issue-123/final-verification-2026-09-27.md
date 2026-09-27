# #123 final verification — 2026-09-27

Status: **Producer accepted r2 on 2026-09-27: “Accept #123”**. No design changes
were made in this verification pass. Accepted S03 v3/#135, S01–S05, #127,
production contracts and the working Claude design remain untouched.

## Exact retained candidate

- File: `Compact Mixed-Change Reconciliation Pilot - issue 123 export.dc.html`
- Downloaded through Claude's project file menu; Producer completed Chrome's
  save dialog into Downloads. Copied byte-for-byte into this issue directory.
- Bytes: 6,546,892.
- SHA-256: `963fd77b58bcee720fcc4bf4375037ab2a2de725170b017d751efd17c878aacb`.
- **Failed standalone image evidence; do not treat this file as final.**
- Screenshot: `evidence/export-v1-missing-thumbnails.png`.

## Checks performed in Chrome

The exported candidate rendered in Claude's Chrome preview at 1024 × 768,
80% text and 0% thumbnails. Source/result text and controls were inspected
through the rendered accessibility tree, not inferred from fixtures.

| Check | Observed result |
| --- | --- |
| Change 10 partial answer | Choosing location alone leaves it Undecided and explicitly says endpoint unanswered. |
| Change 10 Resolve/Resolve | Current Resolve; passage at later location; B-roll ends on “off the water,”; ~4.6s; On Camera after its endpoint. |
| Change 10 Resolve/Script | Script after reconciling; later location with complete ~10.7s B-roll; queues extension only. |
| Change 10 Script/Resolve | Script after reconciling; original location with shortened ~4.6s B-roll and On Camera remainder; queues moving the passage back only. |
| Change 10 Script/Script | Current script; original location and complete ~10.7s range; queues move-back and extension. |
| Source switching after a decision | Switching back to Resolve preserves the selected compound outcome and its consequence. |
| Change 10 Defer | Deferred, neither side changes, no derived result shown. |
| Change 9 over new words | New narration under the No sound bumper; no No audio warning or Audio needed marker. |
| Change 9 after new words | New narration then visual-only bumper; No audio warning; queues Audio needed marker. |
| Change 17 Accept | Current Resolve footage; request closed as fulfilled. |
| Change 17 Keep script | Neutral current-script request retained; queues removal of the clip. |
| Change 17 merge | Derived script uses clip while request remains open as a follow-up, not a second active visual. |
| Change 21 Accept | Derived single row retains both sentences, two base clips and their internal cut, plus Graphic and spoken-word cue. |
| Initial/reset gating | 22 to decide; Reconcile disabled. |
| One unanswered | 1 to decide / 21 deferred; Reconcile disabled. |
| All answered as Defer | 0 to decide / 22 deferred; Reconcile enabled. Running it reports Reconcile simulated / 22 deferred · still unresolved. |

Some clicks in a rapid offscreen traversal did not record their decisions;
the cause was not established. Rendered statuses exposed the misses. Explicit
Enter activation recorded the remaining decisions and counts agreed exactly
with all 22 rendered statuses. This is not claimed as a clean pointer stress
test or a proven page defect.

## Independent export check

Served the exact retained file on `127.0.0.1:8123` and opened it in Chrome,
outside Claude. No adjacent Music Bed page or assets directory was supplied
at the referenced project paths. It loaded promptly enough to operate;
this was not a controlled cold-load performance measurement.

- Default 100% text / 22% thumbnails / internal 1024 × 768.
- Navigation to Change 21 and Enter on Accept produced the expected merged
  result with the correct text, three visual identities, and cue.
- **Actual screenshot shows black thumbnail rectangles** in Changes 20–21.
  The rendered thumbnail buttons have `background-image: url("")`.
- Console error/warning log was empty. Absence of errors did not prove images
  loaded. Image bytes present in the export likewise do not prove usable URLs.

The earlier commentary that thumbnails loaded was premature and corrected
after visual inspection. This candidate fails the exact-export gate.

## Repair request

Sent one concise request in the existing Claude chat to repair only standalone
asset wiring, retain this failed file, produce a separately named corrected
export with hash, and update HANDOFF. Explicitly prohibited working-design,
accepted-artifact, decision, renderer-direction and scenario changes.

## Acceptance gate history (completed or qualified by accepted handoff)

1. Retain corrected export and Claude HANDOFF/matrix; verify exact hash.
2. Visually verify real thumbnails in standalone Chrome, representative
   source/result switching and range inspection.
3. Carry forward earlier focused viewport evidence honestly; do not claim a
   new exhaustive 22-case × settings × outcomes sweep. Prior checks covered
   key graphics, music, cutaway, replacement and swap mechanisms.
4. Reconcile historical issue requirements with the current 22-case annotation
   guide and checklist without reopening Producer decisions.
5. Obtain explicit Producer acceptance of the exact corrected artifact before
   closing #123. Prototype renderer patches, color-based card detection and
   simulated detection/mapping/persistence/execution remain limitations.

## Corrected r2 verification

The Producer saved the separately named repair into Downloads. Retained
byte-for-byte as `Compact Mixed-Change Reconciliation Pilot - issue 123 export r2.dc.html`.

- Bytes: 6,546,977.
- SHA-256: `b4fae31553a72925315c213260e515f32bc97b289d244905daf815402289fa03`.
- Hash matches Claude's repair report. The failed r1 remains retained.
- Repair accepts `blob:` and `data:` image URLs in the private export renderer's
  image-path guard, which previously required an image filename extension.
  This is export wiring, not a change to the working design or accepted S03.

Opened the exact r2 independently in Chrome from localhost, with no adjacent
project assets or Music Bed source supplied. At internal 1024 × 768, default
text and 22% thumbnails:

- Actual screenshot shows the footage and quote-Graphic thumbnails in
  Changes 20–21, rather than r1's black rectangles.
- Change 21 Accept produces one combined row with both sentences, both base
  clips, their internal cut, the Graphic and its spoken-word cue.
- Enter on the Graphic's range control displays its violet inspected range
  across both sentences with visible focus; no details dialog opens.
- Selecting Current script displays the literal original two rows, while
  retaining the accepted outcome and its consequence. A selected-result
  control remains available.
- Chrome's captured error/warning log is empty.
- Screenshot: `evidence/export-r2-thumbnails.png`.

This resolves the observed standalone-thumbnail blocker. It is a focused r2
check, not a new exhaustive 22-case × viewport × settings × outcomes sweep.
Carry forward the earlier interaction evidence and its qualifications above.
Claude's updated HANDOFF and 22-case matrix were read in full in Chrome;
their rendered-test limitations remain relevant. Matthew subsequently supplied
explicit Producer acceptance: **“Accept #123”**. The final authority and
supersession record is [ACCEPTED-HANDOFF.md](./ACCEPTED-HANDOFF.md); it retains
the verification qualifications rather than claiming a new exhaustive sweep.
