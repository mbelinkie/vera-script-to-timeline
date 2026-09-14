# Issue 123 retained design evidence

## Artifact and authority

- Prototype: `timeline-to-script-reconciliation.html`
- Deterministic evidence checker: `check.mjs`
- Evidence images: `evidence/*.png`
- Hash manifest: `evidence/SHA256SUMS`
- Plan and Producer walkthrough: `../../plans/issue-123-timeline-to-script-reconciliation.md`

The artifact is a self-contained design simulation. It does not observe or
control Resolve, modify a script, persist a decision, build a timeline, or
change export/release behavior. It adds no package dependency and changes no
contract, fixture, golden file, generated type, shared token, or production
code.

The accepted inputs were inspected before this artifact was created:

- #14 accepted S03 plan, prompts, and Producer acceptance at commit `11cef62`;
- #58 accepted S05 plan, comprehensive outbound-review briefs, final semantic
  corrections, and retained Producer evidence at commit `7eb71ca`; and
- the authoritative three-way Regeneration Review behavior in §6.16 and the
  related capability/failure rules in the current product specification.

The design deliberately reuses #58's compact affected-row presentation,
script-order review, non-color old/current language, row controls, selected and
skipped counts, safe bulk control, explicit consequences, one-page scrolling,
focus treatment, and narrow-viewport reflow. It reverses the authority direction:
the comparison begins from last applied build + current script + managed
Resolve timeline, and no Resolve observation becomes canonical script truth
without an explicit supported adoption.

## Retained state matrix

Every route was rendered at both exact browser viewport sizes. All filenames
below exist in both `-1280x800.png` and `-1024x768.png` forms.

| Route | Retained evidence | Expected design result |
| --- | --- | --- |
| `?state=entry` | `entry-*` | S03 shows a non-color timeline-change alert and dedicated action beside Prompter/Resolve access. |
| `?state=review` | `review-*` | Three sources, five row classes, filters, defaults, row decisions, counts, and safe bulk selection are visible. |
| `?state=conflict` | `conflict-*` | Four explicit outcomes are bounded; the transition occurrence is a separate protected item below the row decision. |
| `?state=result` | `result-*` | New v19 result, untouched v18, preserved work, out-of-sync row, deferred work, and dependency effects are named without an execution claim. |
| `?state=no-change` | `no-change-*` | S03 says the timeline matches Build 18 and offers no false reconciliation action. |
| `?state=unavailable` | `unavailable-*` | Browser, local-agent, and Resolve boundaries plus recovery actions are explicit; no observation is inferred. |
| `?state=focus` | `focus-*` | A numbered keyboard route and visible focus ring show the intended order and native control types. |
| `?state=non-color` | `non-color-*` | Grayscale rows retain icon, uppercase label, border pattern, inserted/deleted text treatment, and decision wording. |
| `?state=overflow` | `overflow-*` | Long narration, stable IDs, paths, and transition names wrap inside one row with no page-level horizontal overflow. |
| `?state=error` | `error-*` | A missing baseline marker stops comparison, preserves the timeline, and offers retry, relink, and manual-preservation actions. |

## Producer direction retained

- Resolve-only changes are unselected by default. Script-only and compatible
  rows follow the documented selected defaults; conflicts are selected
  proposals but remain blocked until reviewed; unchanged rows are hidden.
- **Select all safe updates** selects only script-only and compatible rows. It
  never selects Resolve-only rows, unresolved conflicts, protected editorial
  work, or transition changes.
- The explicit outcomes are **Use script version**, **Keep Resolve version for
  now**, **Adopt supported Resolve change into script**, and **Review manually
  in Resolve**, with direction and consequence stated under every choice.
- Bounded adoption is named only for clean in/out refinements and subtitle-copy
  edits. Arbitrary tracks, effects, ripple edits, grades, mix changes,
  protected additions, and transition changes are preserved or routed to
  manual Resolve review.
- A transition-default or occurrence-override change is a distinct protected
  reconciliation item. The artifact never reclassifies it as a trim or
  subtitle edit and never offers automatic adoption.

## Verification record

`node docs/prototypes/issue-123/check.mjs` passed on 2026-09-13:

> Issue 123 prototype: 10 states × 2 viewports passed; 20 screenshots retained.

For each route and viewport, the checker runs the artifact in the local browser,
asserts its route-specific marker, asserts `scrollWidth <= clientWidth`, retains
a PNG, and verifies the PNG's exact pixel dimensions. The SHA-256 manifest pins
the prototype, checker, and all twenty images.

Independent visual inspection confirmed:

- the entry action is prominent at both sizes without displacing the accepted
  two-column writing surface;
- the 1280 review keeps the sticky reconciliation plan beside the rows, while
  the 1024 review reflows the plan above one continuous row list;
- the conflict choices remain readable at both sizes and the page scroll keeps
  the protected transition item in the same decision context;
- focus, no-change, unavailable, overflow, error, and result views remain
  legible without clipping or horizontal overflow; and
- the explicit design-simulation label and result copy never assert that a
  production script or Resolve operation occurred.

## Acceptance status

Acceptance authority is Producer. The full ordered walkthrough is in the plan.
This evidence is ready for review but does not constitute acceptance. Issue
#123 must remain **In review** until the Producer replies with explicit
acceptance or identifies the first unacceptable state.

