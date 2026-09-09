# Exact Claude Design prompt — issue #58 S04–S06

Create one new, focused high-fidelity prototype artifact in the existing Claude
Design project `VERA design feedback`. Name it exactly:

`Script to Timeline - Prompter Runtime and Suite Navigation S04-S06.dc.html`

Use the Producer-accepted artifact `Script to Timeline - Two-Column Authoring
S01-S03 v2.dc.html` as the visual, shell, spacing, typography, component,
keyboard, and responsive baseline. Do not edit that accepted artifact. Create a
separate successor artifact for S04–S06 only. Do not redesign S01–S03, add
S07–S19, or copy a Research screen and rename its nouns.

This is a design simulation. It must not claim or perform a real export, sync,
authentication check, local-agent action, media operation, background job,
Resolve action, or cross-product navigation. Every successful operational
result must say `Simulated`, and the prompter result must say `Simulated — no
file written`.

## Overall harness and composition

Add a compact prototype harness with three mutually exclusive modes:

- `S04 · Prompter`
- `S05 · Runtime boundary`
- `S06 · Suite navigation`

Add internal viewport controls for real `1280 × 800` and `1024 × 768` layout
states. Reflow; never scale the desktop canvas down. Keep the accepted VERA
near-black surround, floating product header, white document/work surface,
violet primary accent, warm status neutrals, compact radii, clear typography,
and strong visible focus. Reference the already accepted shared token version;
do not invent, rename, or change tokens.

For each mode, include a reset control and a compact scenario-state chooser.
The currently selected scenario, viewport, product, project, role/runtime where
relevant, and simulated revision/job identity must be readable together. Avoid
prototype-only instructions inside the product surface; put test-only controls
in the harness. Keep every status understandable without color, using concise
text plus an icon or shape. Invalid role/capability actions must be absent from
the DOM, not decorative disabled controls.

## S04 · Prompter-readable output and boundaries

Use only these accepted fictional inputs:

- F03 spoken OC: `A quiet harbor can still hide a moving pattern.`
- F04 one intact spoken paragraph: `Watch the marker behind me as the tide
  turns and the reading begins to drift.` Base state begins OC on `Watch the
  marker behind me`, changes to VO on `as the tide turns`, and returns to OC on
  `the reading begins to drift`.
- F10 spoken VO: `The instrument calls this the Lunara effect.`
- F34 non-spoken cues: PAUSE at the F04 OC/VO boundary and pronunciation
  `Lunara` as `loo-NAH-rah`. Include-in-prompter begins on.
- F05 Direction: `Keep this calm.`
- F06 Citation: `Coastal Sensor Primer`.
- F28 zero-duration production marker: `Check the on-screen units in Resolve.`
- F32 excluded draft note: `Verify the fictional units before publication.`
- one visibly labeled fictional source-transcript excerpt, used only to prove
  that asset transcript text is excluded.

Show an input-side boundary summary and a large, prompter-readable output
preview. The output contains only spoken wording in document order. It starts
with `(OC)` on its own line, adds `(VO)` or `(OC)` only when host visibility
changes, and never alters or splits the paragraph wording. PAUSE and
pronunciation may appear only as unmistakably non-spoken cues, visually and
accessibly distinct from spoken text. Optional section labels are also
non-spoken navigation labels.

Provide two independent options: `Include non-spoken annotations` and `Include
section labels`. Toggling them changes only the controlled non-spoken content.
Direction, citation, production marker, excluded note, and source transcript
must never appear in the spoken output. Include an exclusions disclosure that
names those excluded families without reproducing hidden content as output.

The primary action is `Preview prompter`, not a download or production export
control. A successful result shows the source `Revision A`, option settings, a
stable simulated text identity, and a stable simulated sidecar identity.
Repeating the same revision/settings must show the same identities and content.
Do not claim bytes were written.

Add these resettable failure branches:

1. `Missing camera state`: remove the assignment from one spoken range. Hide
   the successful preview action/result and show a blocking, non-color notice
   that names the affected spoken phrase and offers a focus/return route to it.
   Never guess OC or VO.
2. `Marker target removed`: keep F28 as a zero-duration production marker but
   show it as `Unplaced` with `Reattach` and `Dismiss` actions. It stays excluded
   from prompter output and is never silently deleted or given duration.

## S05 · Browser, local-agent, Free/Studio, and durable-state boundaries

Keep normal browser writing readable and available in every permitted runtime
state. Never invent a separately packaged Desktop authoring application.
Capability comes from the selected typed state, never from browser identity.

Represent the following explicit state branches with exact product language:

- `No local agent`: browser writing remains available. Local execution actions
  are absent from the DOM. A concise explanation says a trusted local agent on
  the producer workstation is required for media preparation and Resolve
  delivery work.
- `Agent disconnected`: browser writing remains available. Show a non-color
  disconnected state and reconnection guidance; no executable local action.
- `Local agent connected · Resolve Free`: show `Prepare Resolve timeline` as a
  simulated local-agent action. Explain that Free produces a verified Resolve
  Import Package and stops at `ready_to_import`; the user then uses
  `File > Import > Timeline` and confirms placement. Never show or claim Free UI
  automation or automated in-Resolve verification.
- `Local agent connected · Resolve Studio supported`: show `Build in Resolve`
  only when a supported standard desktop Studio installation is running with
  external scripting enabled. Label any outcome simulated.
- `Resolve closed`, `External scripting off`, and `Version mismatch`: show a
  readable specific remediation state. The invalid `Build in Resolve` action
  is absent from the DOM. Do not fall back to UI automation.

In the connected + Free branch, demonstrate E02/E04:

1. Revision A is acknowledged. Editing creates local-only Revision B and shows
   `Local changes`, then `Syncing`. Preview waits and states why; it cannot claim
   the unsynchronized text.
2. Acknowledge B. Show `Synced`, then allow `Preview`. The result is
   `Simulated Preview B`, visibly non-release, with frozen source Revision B.
3. Advance the live head to Revision C. The Preview remains Revision B and gains
   a `Newer live revision available` notice. Retry never follows the live head.

Add one isolated durable-job simulation with a stable synthetic job ID, frozen
source Revision B, and stage `Verifying import package`. `Simulate browser
close/reopen` must restore the same job ID, source, and stage. It must not
cancel, restart, duplicate, or claim a real background job. If a retry state is
shown, it resumes from the last verified stage; unrequested stages are labeled
`Skipped`.

Use a compact capability facts panel that clearly separates:

- browser-only reading/writing and prompter preview;
- trusted-local-agent-required preparation; and
- Resolve-required Studio application/verification.

The panel explains current facts; it does not become a setup wizard.

## S06 · Safe reciprocal VERA suite navigation

Use a VERA product switcher containing exactly `Research Video Clips` and
`Script to Timeline`. It must be visually and accessibly distinct from the
same-product project switcher. Show the current product. Pointer and keyboard
activation of the other product must disclose `Opens in a new tab`. In the
simulation, keep the source tab/context visibly intact and show a destination
preview; do not actually navigate.

Provide a `View safe handoff details` disclosure. It may show only these three
categories:

- source product identifier;
- opaque source-project hint; and
- bounded intent `open linked projects`.

Use a clearly synthetic opaque hint, never a readable project name. Also show a
concise `Not transferred` list: script/transcript/comment/clip/search content,
credentials or tokens, permission claims, URLs/object keys/local paths,
artifact/media locators, jobs, files, and unsaved selection. Do not add a
production envelope or schema.

The destination treats the hint as untrusted, establishes its own session,
rechecks its own current membership, and never creates or links a project.
Include separate resettable states for both Script-to-Research and reciprocal
Research-to-Script navigation:

- `One authorized destination`: prioritize that destination only after the
  destination rechecks authorization.
- `Several authorized destinations`: show a chooser containing only projects
  the current account may know exist. Include a safely overflowing long
  authorized name with a full accessible name.
- `No linked destination`: open the destination's normal home; linking remains
  a separate later authorized action.
- `Unauthorized`, `Stale`, `Archived`, `Unlinked`, and `Destination unavailable`:
  show a nonrevealing home/access/unavailable fallback with no protected project
  title, content excerpt, automatic link, or permission grant.

For Script-to-Research, a linked Research project may be prioritized only after
current Research membership is rechecked. Otherwise use normal Research home
or a safe access state. For Research-to-Script, one authorized linked Script
project may be prioritized, several yield an authorized chooser, and none yield
normal Script home. Research membership and Script membership remain
independent.

Add one same-product project-switch demonstration that updates the entire
current product context and never looks like or triggers the product switcher.
Do not simulate transferring paths, files, local work, jobs, or desktop-runtime
state through suite navigation.

## Interaction, accessibility, and responsive evidence

At both internal viewports, every pointer action needs a discoverable keyboard
equivalent. Use native roles and state where possible. Supply meaningful
accessible names for the mode tabs, viewport controls, product/project
switchers, prompter options, status/failure notices, chooser, disclosures,
dialogs, and actions. Use Tab/Shift+Tab for logical traversal; Enter/Space for
activation; arrows within tabs/radios/menus; and Escape to close a modal or
popover and restore focus to its opener. Show a strong focus ring against both
the near-black shell and white work surface.

Use `role=status` or `role=alert` appropriately without stealing focus. Do not
use color, font weight, animation, tooltip-only copy, or icon-only labels as the
sole carrier of OC/VO, spoken/non-spoken, sync, capability, failure,
authorization, current product, or new-tab intent. Prompter text must remain
comfortable to read at 1024. Long authorized chooser names may truncate
visually but retain full accessible names; unauthorized states may not contain
hidden protected names in visible or accessibility-only content.

The 1024 layout must use real compact reflow: no horizontal overflow, clipped
focus ring, scale-to-fit canvas, independently scrolling document columns, or
off-screen required action. The harness may scroll vertically. Respect reduced
motion; no authored meaning may depend on animation.

## Required self-test and final report

Before finishing, reset and run S04, S05, and S06 at both `1280 × 800` and
`1024 × 768` with pointer and keyboard. Inspect visible pixels and the DOM/
accessibility tree. Report:

1. the exact artifact name and that the accepted S01–S03 artifact was unchanged;
2. every scenario branch exercised and its observed result;
3. the measured rendered viewport size and horizontal overflow count for each
   width;
4. focus order, reverse order, visible-focus, Escape/focus-return, status
   announcement, non-color, readability, and long-name overflow results;
5. DOM absence results for invalid local-agent/Resolve actions and protected
   unauthorized project names;
6. repeated S04 identity equality and durable-job identity continuity; and
7. any remaining limitation or open Producer judgment.

Do not say the simulations implement production behavior. Do not mark or imply
Producer acceptance.
