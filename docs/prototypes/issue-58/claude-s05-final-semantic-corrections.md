# Claude brief: final S05 semantic corrections

Continue editing S05 in the existing **Script to Timeline — Prompter Runtime
and Suite Navigation S04–S06** artifact.

This is a narrow correction pass, not a redesign. Preserve the new complex
scenario set, the current cross-section context presentation, the section-range
pills, the existing format/resolution/quality choices, equal action weight,
S04 unchanged, and S06 completely deleted.

Before editing, ask Matthew any focused question needed to resolve a material
ambiguity. If the requirements below are clear, say so and proceed.

## 1. Treat Resolve section markers as zero-duration points

Resolve section markers are not visuals and are never "on screen" for a span of
narration. Correct every section-marker card, including marker rename, add,
remove, and move examples.

Remove language such as:

- `On screen for “Section: …”`
- `Previously on screen for “Section: …”`

Marker cards must not use visual-coverage hover underlines. They have no
duration or coverage range.

Use semantics like these:

- renamed marker: `Resolve marker renamed from Conclusion to Closing at this section boundary; zero duration.`
- added marker: `New Resolve marker “Verification” at the Verification section boundary; zero duration.`
- removed marker: `Removed Resolve marker “Setup” from its previous section boundary; zero duration.`
- moved marker, old position: `Resolve marker “Closing” at its previous section boundary; zero duration; removed from this position.`
- moved marker, current position: `Resolve marker “Closing” at its current section boundary; zero duration; added at this position.`

Keep the existing red/green row and card treatments, marker identities,
checkbox behavior, mirrored pure-move selection, and timeline consequences.
Only correct the false duration/coverage semantics.

## 2. Make Render settings a real popup dialog

`Create and render` and `Update and render` must open a true **Render settings**
dialog rather than expanding a large panel inside the page.

The dialog remains exclusively about render settings. Do not restore any
timeline-confirmation summary, comparison recap, affected-row recap, or copy
beginning `Create version 3 of Harbor Lights — Main`.

Required dialog behavior:

- clearly separates from the page with a dialog surface and backdrop;
- has an accessible name of `Render settings`;
- moves keyboard focus into the dialog when opened;
- keeps keyboard focus within the dialog while open;
- closes with Cancel or Escape;
- returns focus to the Create/Update and render button that opened it;
- fits at both `1280 × 800` and `1024 × 768` without horizontal overflow;
- uses at most one ordinary vertical scroll region if its content cannot fit;
- keeps its final action and Cancel available without creating independently
  scrolling form columns.

Preserve the current settings and choices:

- Last used and VERA default;
- named saved presets;
- H.264 · MP4, H.265 · MP4, ProRes 422 · MOV, and DNxHR SQ · MXF;
- 1920 × 1080, 3840 × 2160, and 1280 × 720;
- Draft, Standard, and High;
- destination folder;
- filename pattern;
- complete-timeline or continuous From/Through section range; and
- the current section pills.

The final dialog action remains context-specific:

- `Create timeline and render`
- `Update timeline and render`

That action starts the combined operation with no further confirmation.

## 3. Correct the Create/Update and render accessible action

The button on the review page currently implies that clicking it immediately
performs the operation. It actually opens Render settings.

Keep the visible labels:

- `Create and render`
- `Update and render`

Use accessible descriptions such as:

- `Open render settings for creating the first timeline and rendering it.`
- `Open render settings for updating the timeline and rendering it.`

Do not describe the first click as completing the operation or as needing no
second interaction. The final action inside the dialog is what starts the
timeline-and-render run without another confirmation.

`Create timeline` and `Update timeline` remain immediate one-click actions.

## 4. Label and focus preset naming

After `Save preset` is activated, do not show an anonymous blank field.

Required behavior:

- show a visible `Preset name` label;
- associate the label with the text field accessibly;
- move focus to the field;
- disable `Save preset` while the name is empty or only whitespace;
- Enter saves a valid name;
- Escape or Cancel exits naming without closing the Render settings dialog;
- after saving, show the named preset in the saved-settings control and select
  it; and
- return to the ordinary `Save preset` control when naming is cancelled.

Do not redesign preset management beyond this compact inline naming state.

## 5. Fix old/current range concatenation everywhere

The Closing camera-state row is now correct, but the same defect remains in
other changed rows. No visual card, marker card, hover treatment, focus
treatment, or accessible description may concatenate deleted and current text
into one range.

### Operator wording example

Previous wording:

`The operator described the change as “slow.”`

Current wording:

`The operator described the change as “slow, then sudden.”`

The unchanged Logged Clip is associated with the current sentence when shown
as a current visual. Its accessible description should say:

`Logged Clip. Currently on screen for “The operator described the change as “slow, then sudden.””.`

It must not produce a glued value such as:

`slow.”“slow, then sudden.”`

Hovering or focusing the current Logged Clip must underline only current words;
deleted inline-diff tokens must never become part of its current coverage.
Because the visual and its coverage rule did not change, retain the ordinary
gold current-range underline.

### General range rule

- unchanged/current visual cards reference only current wording;
- new visual cards reference only current wording and use solid green;
- removed/old visual cards reference only previous wording and use dotted red;
- a changed range may name both previous and current spans, but they must be
  separate labeled values;
- deleted inline-diff tokens never belong to a current range;
- inserted inline-diff tokens never belong to a previous range; and
- identical old and current spans remain separate version associations when
  the visual itself was replaced.

Apply the same correction to every scenario, not only the named operator and
Closing examples.

### Marker rename example

Do not emit `Section: ConclusionClosing` or treat either string as an on-screen
range. Present separate values:

- previous marker name: `Conclusion`
- current marker name: `Closing`

Then use the zero-duration marker semantics from section 1.

## 6. Preserve accepted choices

Do not change:

- the current cross-section context reveal presentation;
- section-range pills;
- Draft / Standard / High;
- 720p / 1080p / 2160p choices;
- the current codec/container choices;
- equal emphasis for timeline-only and timeline-and-render actions;
- row-level selection and partial split/merge warnings;
- the complex-scenario harness; or
- the external placement of prototype-only failure controls.

## 7. Verification

Before finishing, verify at both `1280 × 800` and `1024 × 768`:

1. Every Resolve marker is described as a zero-duration point and never as
   on-screen coverage.
2. Marker cards do not paint narration-range underlines on hover or focus.
3. Render settings opens as a real dialog, traps focus, closes with Escape, and
   returns focus to its triggering button.
4. The dialog has no timeline-confirmation recap.
5. Create/Update and render buttons accurately announce that they open render
   settings.
6. Preset naming has a visible label, correct focus, empty-name prevention,
   Enter save, and Escape/Cancel behavior.
7. Every current visual range excludes deleted text; every previous range
   excludes inserted text.
8. No accessible name contains glued old/current wording such as
   `ConclusionClosing` or `slow.”“slow, then sudden.”`.
9. Create timeline and Update timeline still begin immediately.
10. The accepted scenario set, context behavior, section pills, render choices,
    S04, and S06 deletion remain unchanged.

Fix every inconsistency found during verification before reporting completion.
