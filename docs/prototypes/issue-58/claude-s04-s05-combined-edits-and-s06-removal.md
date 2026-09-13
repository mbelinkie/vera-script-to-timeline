# Claude brief: finish S04 and S05; delete S06

Please continue editing the existing **Script to Timeline — Prompter Runtime and Suite Navigation S04–S06** design artifact.

Use your own design judgment to implement the requirements below. Do not stop after describing the changes: make the changes in the artifact, exercise the relevant interactions, and verify both supported internal viewports. Keep working through the remaining Claude usage allowance, up to 100%, if needed to finish implementation and verification. Prioritize a coherent, working artifact over a long written response.

## Scope

- Finish the remaining S04 copy changes.
- Correct the S05 interaction and truthfulness issues below.
- Delete S06 entirely.
- Do not redesign unrelated parts of S04 or S05.
- This is still a design simulation. Do not imply Producer acceptance or mark issue #58 complete.

## S04 — Prompter script

The current interaction model is approved. Preserve all of the following:

- controls at the top;
- readable document-sized script;
- pills in the app for non-spoken material and square brackets in exported/copied text;
- the working **Simplify brief camera changes** option;
- the missing-camera preflight, exact phrase highlighting, link back to the phrase, and genuinely disabled export action;
- the post-create **Download prompter text** and **Copy prompter text** actions;
- no “Marker target removed” scenario or prompter notice.

Make these copy changes:

1. Rename the user-facing page from **Prompter export** to **Prompter script**.
2. Remove **Produced 12 March 2026**. There is no produced/done milestone in VERA. Use a neutral source label such as **Based on Revision A**.
3. Update related action and accessible labels where needed so the page consistently speaks about preparing or creating a prompter script; keep **Download** and **Copy** as the explicit output actions.

## S05 — Resolve timeline

Preserve the current core model:

- one self-explanatory **Resolve timeline** page;
- first-run **Create timeline** state;
- later **Update timeline** flow;
- per-row selection of script changes;
- separate **Review Resolve changes** flow;
- explicit per-conflict choice between keeping the Resolve edit and taking the script change;
- every update creates a new version beside the current one and never overwrites it;
- accepted cuts remain in the script, struck through and marked **cut in edit**, while being excluded from prompter text and counts;
- no preview-versus-release distinction and no final/done state.

### 1. Make inspection claims honest

VERA's assumed live structural inspection is limited to timeline items, positions, trims, and tracks. Existing effects, transitions, color work, audio mixing, markers, and hand-added items may be preserved because the update starts from a duplicate of the current Resolve timeline—not because VERA fully understands those edits.

Replace language such as **Carries over your trims, order, effects, tracks, levels, markers and hand-added items** with a clear explanation along these lines:

> Starts from a duplicate of your current timeline, so your existing Resolve work stays in place.

Where useful, separately state what VERA actually inspected: items, positions, trims, and tracks. Do not claim semantic understanding of effects, color, transitions, mixes, or hand-added material.

### 2. Correct Resolve Free

Resolve Free cannot simultaneously say that external control is unavailable and claim **Read from your open Resolve timeline just now**.

Design a genuinely manual-import state:

- VERA prepares a timeline file/package for the user to import into Resolve Free.
- The primary action must say **Prepare timeline file** or an equally explicit manual-import label, not **Update the timeline**.
- Provide short, concrete import instructions after preparation.
- Do not show live inbound Resolve-change detection in this state unless the user has explicitly supplied/imported a fresh timeline snapshot. In the current prototype, assume no such snapshot.
- Be explicit about what can and cannot be preserved in this fallback. Do not promise that the manual import automatically carries over edits from the existing Resolve timeline unless the design demonstrates a truthful mechanism.

### 3. Correct disconnected states

When Resolve is closed or VERA cannot connect to the computer running Resolve:

- do not say **Read from your open Resolve timeline just now**;
- either show the last successful inspection with an honest timestamp/source label, or hide/disable the inbound Resolve-change section until reconnection;
- script-side change selection may remain available;
- the update action must stay unavailable with a plain-language reason;
- replace **edit workstation** with **the computer running Resolve** or **this computer**, as appropriate;
- avoid leading with **helper** as a user-facing concept. Prefer **VERA can’t connect to Resolve** and give the concrete action needed. If the helper must be named in secondary explanation, describe it simply.

Apply the same evidence rule to unsupported-version and broken-link states: never present stale or impossible live-read claims as current.

### 4. Keep conflict decisions visible and reversible

After the user chooses **Keep my Resolve edit** or **Take the script change**, do not make the conflict disappear.

Keep a compact resolved row visible through confirmation, showing:

- the affected change;
- the selected decision;
- a clear **Change** action or both radio options so the choice can be revised.

### 5. Make all counts unambiguous

The current flow can say **Applies 3 of 4 selected changes** and then **Includes 4 of 5 script changes** in confirmation. Replace this with one consistent accounting model everywhere, for example:

> 4 selected: 3 will be applied; 1 will be skipped because you chose to keep the Resolve edit. 1 other change is not selected.

Use the same numbers and terms in the list header, summary, footer, confirmation, and result.

### 6. Retain the strongest existing S05 work

Keep and verify:

- the clear first-timeline empty state;
- independent inbound review that does not alter the timeline;
- the accepted-cut behavior, including restore;
- explicit uncertainty for reordered items rather than an automatic decision;
- a confirmation step that names what will happen, what will not happen, and what the user should check by hand;
- responsive stacking at 1024 × 768.

## Delete S06 entirely

S06 is not necessary. Cross-product navigation should be a simple header action in the relevant VERA products, with a possible web landing page later. It does not need its own slice or page in this artifact.

Remove all S06 material, not merely the visible page:

- remove the **S06 · Suite navigation** harness tab;
- remove every S06 scenario control and state;
- remove the S06 template/page/body;
- remove S06-specific JavaScript, data, labels, accessible descriptions, comments, and dead styles;
- update harness text and simulation notes so the artifact describes only S04 and S05;
- do not replace S06 with a new navigation design.

If the artifact filename cannot be changed safely inside Claude Design, leave the filename alone; the rendered artifact itself must contain no S06 experience or references.

## Verification before stopping

Use the remaining available usage—up to 100% if necessary—to complete this verification rather than stopping at a prose summary.

Verify at both **1280 × 800** and **1024 × 768**:

### S04

- base output;
- brief-camera-change option on and off;
- missing-camera preflight and disabled action;
- create result with Download and Copy actions;
- app pills versus square-bracketed exported/copied text.

### S05

- no-timeline/create state;
- connected update with no conflict decision yet;
- both conflict choices and the ability to revise them;
- consistent selection/application/skipped counts through confirmation;
- Review Resolve changes, accepted cut, and restore;
- Resolve closed;
- connection unavailable;
- Resolve Free/manual import;
- unsupported version;
- broken timeline link;
- honest evidence/source labels in every state.

Finally confirm that no S06 tab, scenario, rendered page, accessible label, or dead interaction remains. Fix any issue you find during verification before replying.
