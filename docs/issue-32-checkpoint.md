# Issue 32 checkpoint — Batch 5 evidence paused at Claude usage limit

## 2026-09-03 continuation

The original pilot limit below has been cleared. The pilot and Batches 1–4
completed in Claude Design; Batch 5 shadow wiring was written and its final
native PNG evidence/report is being recovered after a browser-tab interruption.
Claude then reported **“Paused — you've hit your limit”** during the narrowed
Batch 5 recovery request. Its displayed reset time is **1:10 PM on September 3,
2026** (America/New_York). Stop here until usage is available. This remains a
partial checkpoint, not an acceptance handoff. The active claim
is still this task on `codex/issue-32-design-system-transfer`.

The producer's latest direction is to continue bounded #32 work until Claude
reports exhausted usage. Do not begin #14 or reinterpret accepted decisions.
The live source is [VERA Redesign.dc.html](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=VERA+Redesign.dc.html).
Use the conversation **Issue #32 Batch 3 continuation**. The original tab is
currently `543775433`; rediscover it by title and URL if that ID expires.

### Completed batches and retained identities

The following are Claude's retained ledger/report results, inspected through
the live UI. Evidence paths in this section are inside the Claude project,
not files downloaded to this repository.

| Batch | Result | After identity | Evidence |
| --- | --- | --- | --- |
| Pilot | Shared CSS link works within this Claude project; no local declarations and 15 var references. Research source unchanged. | CSS 726 B, `5d025485…c7fe802d`; probe 8,775 B, `958c3f29…dcf05e2a` | `issue32-pilot-tokens.css`, `Issue 32 import probe.dc.html` |
| 1 | 65 accepted T-B consolidations wired plus two typography token leaves. Nineteen scenes at both widths; no computed, geometry, console, or decoded-RGBA changes. | 505,326 B, 5,049 lines, `8cfcd7ef…2f5de724` | `_b1-wire-ledger.json`, `_b1-diff.html`, `evidence/b1/` |
| 2 | 58 exact height-axis declarations wired. Nineteen scenes at both widths; no computed/geometry drift, unresolved vars, new overflow, console errors, or RGBA changes. | 506,255 B, 5,049 lines, `f5f772d988b86f7affdc6ec705e4ae10509616bffe5786f15190843118fdd0b8` | `_b2-wire-ledger.json`, `_b2-diff.html`, `evidence/b2/` |
| 3 | 307 declarations / 331 components wired from full collision attribution; 58 previously wired skipped, none held. Two states at both widths had equal computed and geometry digests. | 512,069 B, `b1b149371bd21938904d751367f478beba5b3a8a6fdf01cc31d658226a217003` | `_b3-wire-ledger.json`, `_b3-verify-harness.html`, `evidence/b3/verify-evidence.json`, `evidence/b3/rgba-compare.json` |
| 4 | 51 new leaves declared; 544 product component substitutions. 29 destinations/overlays × two widths = 58 pre/post comparisons, 24,520 element comparisons over 41 computed properties plus rectangles; equal geometry, node counts and overflow sets, zero unresolved vars, silent consoles, unchanged responsive deltas. Twelve native PNG frames had zero RGBA changes. | 519,711 B, 5,049 lines, `779ba6087b317f6b45d6ead57eb8ddf61916a59a6b7df760ab8fe7ab555ab25b` | `_b4-wire-ledger.json`, `_b4-verify-harness.html`, `evidence/b4/verify-evidence.json`, `evidence/b4/rgba-compare.json` |

The original preserved Research baseline is 500,502 B / 5,049 lines, hash
`e72fe386…d447e73`. Obtain the full hash from its retained ledger for the final
handoff. Never treat abbreviated hashes as a byte comparison performed locally.

Batch 1 established a true lossless PNG route at scale 1: 1280×802 and
1024×770 frames include the one-pixel borders around the authored viewports.
Batch 3's four 924×540 direct-preview PNG comparisons were equal, but do not
replace native-scale evidence. A cumulative native comparison is still needed
where Batch 3 changed consumers were not covered by an applicable native run.

### Preserved exceptions and pending decisions

- Row 13a remains held because its fixed-height precondition does not match
  the source's min-height. `--type-row` leaves remain unused; typography
  deferrals and documentation/specimen exclusions remain untouched.
- All 17 responsive pairs declared in Batch 4 remain unwired at their JS
  numeric ternaries. This batch explicitly preserved branch expressions;
  these are implementation holds, not new producer-approved exceptions.
- A40 `--header-gap-*` is entirely held. Accepted List A says wide 13 / narrow
  9; the accepted responsive inventory and source L4090 say `(cmp ? 9 : 15)`.
  Neither token was declared or wired. Producer resolution is required before
  final package acceptance; do not silently pick a wide value.
- `--bp-compact: 1024px` is declared; its only comparison site
  `const cmp = s.vw === 1024` (L3674, doc-data) remains literal.
- The known keyboard field-outline defect remains a separate follow-up.
  Genuine keyboard input earlier showed a gold solid 2px button outline with
  2px offset, and a field matching focus-visible with outline style none.

### Resume here: Batch 5 recovery boundary

The first Batch 5 run preserved
`VERA Redesign (pre-Batch-5 shadow baseline).dc.html`, wrote the shadow changes,
created `_b5-wire-ledger.json` and `_b5-verify-harness.html`, and reported all
five relevant sites reached after repairing harness state selection. It was
capturing native pre/post PNGs when the temporary tab closed. No final Batch 5
hash/result is claimed yet.

The current recovery prompt explicitly forbids rewriting source or any baseline. It
must verify the pre-Batch-5 file still matches Batch 4's full after hash above,
match current source to the shadow ledger, reuse successful comparisons, finish
only missing PNG evidence, and report exact hashes/site counts/results. Stop
after that report. Its last completed visible tool group is **“Screenshot,
Comparing B9-B12 pixel pairs”**, followed by an artifact link to
`VERA Redesign (pre-Batch-5 shadow baseline).dc.html` and the usage-limit notice.
The UI also lists source/ledger matching, preserved-baseline hash verification,
and reads of existing per-site proofs, but it has not surfaced the final report
or full post-shadow hash. Do not infer completed acceptance from those labels.

Resume this exact recovery request with Claude's **Resume** control. Do not
resume the older full Batch 5 editing prompt: doing so restarted audit reads
after the tab interruption. The older restart was stopped and replaced with
this evidence-only request before a final result. The recovery must disclose
any intervening mutation or baseline conflict.

The complete visible conversation at the limit is retained locally in
`out/issue-32/claude-batch5-usage-limit-2026-09-03.txt` (ignored evidence). The
live tab was marked for handoff. Focus, final export/import, and #14 remain
unstarted. After reviewing the Batch 5 report, the next bounded implementation
is focus-token wiring with real keyboard proof and no defect repair. Responsive
branch wiring, A40 producer resolution, the versioned package and separate
adoption artifact, and final cumulative verification remain before acceptance.

## Historical pilot checkpoint (2026-09-02)

Recorded 2026-09-02, America/New_York. This is a partial implementation
checkpoint, not an acceptance handoff. #32 is not ready for review and #14
remains blocked by its acceptance dependency.

## Resume here

Open the [Issue 32 import probe in Claude Design](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=Issue+32+import+probe.dc.html).
Claude paused during its pilot verification/correction with **“Paused — you've
hit your limit.”** The active page reported **11:30 PM** as the reset time.
Do not restart the audit or submit the full wiring request. Resume the existing
bounded pilot after usage is available, retain its final source/package hashes,
and review its correction result before proceeding to the next batch.

The dedicated task and branch are recorded in
`docs/plans/issue-32-design-system-transfer.md`. The branch starts at the exact
required `9a6f8c18d79b1533a4e601fec158099db3642613` commit. Initial inspection
confirmed Ready, model:sol/effort:high, complete criteria, no claim, and #21
closed/Done. The exact-profile claim succeeded.

## Changes so far

Claude created only the small pilot package `issue32-pilot-tokens.css` and
`Issue 32 import probe.dc.html`. The working Research artifact, accepted audit,
and baselines were excluded from the prompt; their visible file timestamps
remained unchanged. A complete source hash comparison has not yet been
obtained, so timestamp observations are not represented as byte proof.

Repository changes are this checkpoint and the bounded plan. No production
code, contracts, fixtures, golden files, accepted tests, or dependencies changed.

## Confirmed pilot observations

The live probe contains a real DOM link:

```html
<link rel="stylesheet" href="./issue32-pilot-tokens.css">
```

The stylesheet viewer displays the four requested declarations:

```css
--gold: #c49b50;
--font-ui: Inter,sans-serif;
--gutter-wide: 15px;
--gutter-narrow: 13px;
```

Independent read-only DOM checks found:

| Check | Observed result | Limit |
| --- | --- | --- |
| Pilot button | `rgb(196, 155, 80)` background; `Inter, sans-serif` family; inline consumers reference `var(--gold)` and `var(--font-ui)` | Representative import only |
| Wide spacing control | `gap: var(--gutter-wide)` computes to `15px` | Pilot setting, not final application verification |
| Compact spacing control | `gap: var(--gutter-narrow)` computes to `13px` | Pilot setting, not final application verification |
| Baseline button, genuine Tab input | Workspace button matches `:focus-visible`; gold solid `2px` outline, `2px` offset | One representative baseline control |
| Baseline field, genuine Tab/Shift+Tab | Input matches `:focus-visible`, offset `1px`, computed outline style `none` | Reproduces the accepted audit's separately tracked outline defect; no fix or defect acceptance |

The rendered spacing report initially lagged its selected setting. The compact
result above was measured from the actual flex container after the state
settled, not inferred from that report. Claude's own correction pass is still
paused, and the pilot has not been accepted as complete.

The external browser's screenshot API returned **JPEG bytes**, including for
files initially given a `.png` suffix. The clipped capture was black; the
full-viewport diagnostic visibly captured the frame and gold keyboard ring.
The files were renamed accurately. These are previews only and cannot satisfy
lossless pixel-identity evidence. Do not repeat this method for a full matrix.
Use the accepted Claude native element-capture route or another verified
lossless operator/harness route for the required before/after evidence.

The file viewer's Copy action and editor-value read yielded empty strings;
the Download attempt did not produce a confirmed download. No source or package
hash is claimed. Do not use the empty-copy artifact as a package.

## Retained local evidence

All files below live under the task worktree's ignored `out/issue-32/` directory:

- `accepted-remaining-audit-rendered.txt`: accepted audit text read from the DOM.
- `prior-wiring-evidence-rendered.txt` and `tb-decision-sheet-rendered.txt`:
  historical evidence, subject to the source-version limits in #21.
- `pilot-import-dom.json`: observed stylesheet links and inline stylesheet text.
- `pilot-compact-computed.json`: actual compact flex gap and geometry.
- `pilot-rendered-checkpoint.txt` and `claude-paused-checkpoint.txt`: saved
  rendered pilot and paused status.
- `baseline-keyboard-pilot.json` and `baseline-field-keyboard-pilot.json`:
  actual focus observations after keyboard input.
- `baseline-button-focus-preview.jpg` and
  `baseline-field-focus-preview.jpg`: lossy browser previews, not pixel proof.
- `baseline-clip-black-invalid.jpg` and `empty-copy-attempt.invalid`: retained
  failed capability attempts, not valid evidence inputs.

![Baseline keyboard focus preview; JPEG, not pixel-identity evidence](../out/issue-32/baseline-button-focus-preview.jpg)

## Remaining work and stop conditions

1. Finish the existing pilot after the session reset. Obtain exact source and
   package bytes/hashes through a supported export path and verify true import
   isolation. Do not treat the pilot as the Script-to-Timeline target artifact.
2. Confirm current Research bytes against the accepted preserved baseline and
   inspect the accepted T-A/T-B tally files. Credit completed work only where
   source identity and evidence apply.
3. Establish a successful lossless native capture before requesting a matrix.
   Real keyboard input is available; synthetic focus is unnecessary.
4. Apply the approved token-family/consumer batches with source-ID traceability.
   Keep B9–B12's four shadow decisions separately evidenced. Preserve the 73
   literal dispositions, deferred typography, documentation/instrumentation,
   and every recorded exception. Stop for any newly required producer choice.
5. Produce the complete versioned export, import that same package into the
   separate Script-to-Timeline artifact, and finish all required Research and
   target checks at 1280 × 800 and 1024 × 768.
6. Only then supply exact artifact/version links and the producer acceptance
   checklist required by the plan and issue. Move to In review with retained
   evidence; do not close without explicit producer acceptance.

No new producer design choice is currently asserted. The immediate blocker is
Claude usage availability; lossless capture and exact-byte export remain
capability gates for the next batch. No additional task was dispatched.
