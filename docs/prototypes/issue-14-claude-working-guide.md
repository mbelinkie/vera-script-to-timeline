# Working with Claude Design on issue #14

Practical guidance for [#14 — Design and approve the Script-to-Timeline browser
authoring prototype](https://github.com/mbelinkie/vera-script-to-timeline/issues/14),
written from the #32 design-system transfer work. This is a companion to the
accepted inputs, not a new product specification or approval to start #14.

At this writing, #13 and #26 are Done; #32 is still Blocked and its imported
system is a candidate. Before starting #14, inspect the live roadmap and pin
the exact **producer-accepted #32 package and artifact**, including exceptions.
Do not promote a candidate merely because it renders successfully.

## 1. Give Claude a design job with a clear boundary

Claude should own composition: hierarchy, density, component anatomy, navigation
expression and compact reflow. Codex should keep the brief coherent, preserve
accepted decisions, inspect results, coordinate evidence and maintain the
handoff. Matthew owns product and visual acceptance.

Describe the user's job and the observable outcome before listing constraints.
For example: “Let a writer mark OC → VO → OC inside one intact paragraph and
understand which words a Picture covers.” Avoid prescribing every panel and
pixel before Claude has proposed a composition.

Separate three kinds of instruction:

- **Fixed:** accepted product meaning, permissions/runtime boundaries, sample
  content, shared token values and the scope of the selected scenarios.
- **Open for design:** arrangement, hierarchy, how selection is expressed,
  discoverability and responsive composition within those fixed rules.
- **Needs a producer decision:** conflicts between accepted sources, changes
  to shared visual values, or a product behavior the authorities do not settle.

Do not ask the producer to reconfirm settled decisions. Preserve each decision
with its scope. Matthew's A40 approval resolved one header gap; it did not
approve all of #32.

## 2. Start with a compact, authoritative input packet

Use these existing inputs rather than reconstructing the product in chat:

- [Suite contract](../vera-suite-design-contract-and-claude-brief.md): shared
  grammar and separate product artifacts in one suite project.
- [Accepted semantic dossier](issue-26/README.md): authority pins, required and
  forbidden behavior, decisions and phase boundaries.
- [Scenario spine](issue-26/scenario-spine.md),
  [fictional content kit](issue-26/content-kit.md), and
  [acceptance script](issue-26/acceptance.md): exact scenario/content/check IDs.
- [Pass 1 / Pass 2 packets](issue-26/claude-packets.md): coverage envelopes,
  which can be divided into smaller prompts.
- The eventual #32 acceptance handoff: exact imported system version, evidence
  and known exceptions. [The #32 checkpoint](../issue-32-checkpoint.md) is
  interim evidence, not that acceptance handoff.

Keep the full authorities available in the project. In each prompt, provide
only the relevant excerpts and IDs plus a short accepted-state summary. Do not
paste the entire history repeatedly. A short prompt must not silently narrow
the full acceptance requirements.

Use only the approved fictional material. Do not send private scripts, Research
records, personal identities, local paths or real media to make a mockup richer.
Runtime and media operations remain simulated; the browser does not acquire
Resolve or local-agent capabilities through persuasive UI copy.

## 3. One coherent outcome per prompt

Use this structure; it is a checklist for the author, not mandatory verbosity:

| Part | What to specify |
| --- | --- |
| Starting point | Exact artifact/version and accepted package; preserve a baseline before consequential edits. |
| User job | What the person must understand or accomplish. |
| Scope | Named scenario, content and acceptance IDs; exact allowed changes. |
| Invariants | Existing accepted states and behavior that must survive. |
| Design latitude | What Claude may propose without another decision. |
| Verification | The affected checks and viewports, with a reusable method. |
| Deliverable | Artifact plus short result, changed IDs, evidence paths and unresolved decisions. |
| Stop | Finish this result; stop on a specific ambiguity or discrepancy; do not start the next group. |

For #14, a useful first group is S01–S03: open the project, write naturally,
mark an intact paragraph and attach Pictures to exact word ranges. Get producer
feedback on this core composition before spreading it across S04–S19. This is a
proposed working sequence, not a replacement for the dossier's full coverage.

Do not combine first composition, every scenario, a new verification harness,
a full audit and a polished handoff in the same request.

### Starter prompt for a future authorized #14 task

```text
Using [accepted Script artifact/version] and the exact #32-accepted imported
system [package/version/hash], design only the S01–S03 core writer journey.
Use the corresponding #26 content IDs and acceptance steps supplied below.

The writer must open the fictional project, edit natural two-column prose,
mark OC → VO → OC within one intact paragraph, and attach Pictures to exact
word ranges with understandable coverage validation. Preserve the dossier's
semantics and simulate browser save/reload; implement no production services.

Propose composition, selection feedback and compact reflow. Preserve the shared
system and Research artifact. Keep later scenarios in the coverage ledger;
do not compose them in this batch. Surface a real semantic conflict instead
of inventing behavior.

Check the named journey at 1280×800 and 1024×768. Return the artifact, scenario
mapping, changed files, known limitations and a brief producer walkthrough.
Stop for composition feedback before extending this design to other groups.
```

Replace placeholders with verified identities; do not send an unfilled template.

## 4. Give corrections as observable problems

Finish inspecting a result before sending one prioritized correction packet.
Name the scenario, action, observed problem and required outcome. Explain why
it matters, but let Claude choose the visual treatment when that remains open.

“Make it clearer” is difficult to verify. A better correction is: “In S03,
after selecting the second range, the card highlight still points at the first.
Make the selected words and active card agree, including keyboard navigation.”

```text
Against [reviewed version], correct only [scenario IDs]:
1. [Action → observed problem → required outcome.]
2. [Action → observed problem → required outcome.]

Preserve [accepted states]. Do not change shared token values or product
semantics. Recheck these scenarios at both widths and any other scenarios
using the changed shared component. Return the exact delta and evidence.
Separate unresolved blockers from optional polish, then stop.
```

After this pass, assess unresolved problems and the smallest next action. Do not
turn “one more improvement” into an automatic redesign or audit loop. A new
producer choice needs a concrete comparison and recommendation, not a vague
request to continue.

## 5. Match verification to the claim

#14 is new visual design. A newly approved composition is expected to look
different. **Do not copy #32's pixel-identity gate onto all #14 design work.**
Use visual/interaction review for intentional design changes and regression
checks for accepted states that a later edit should preserve.

Before a large capture run, prove one representative case end to end:

1. Open the actual state through its real control, in the correct artifact.
2. Confirm the intended viewport/layout, selected content and open overlays.
3. Capture at native scale and inspect the image's actual dimensions/content.
4. Confirm the evidence tests the claim being made; retain its source identity.

Label viewport screenshots, app-frame captures, full-content captures and
scaled previews accurately. In #32, Research's 1280×802 image included borders
around a 1280×800 authored stage. The adoption page's 1280×875 image was a
content-height element capture. Neither label alone proved viewport coverage.
Later inspection also found Batch 4's supposed native images were only 924×540.
Measure this at capture time, before trusting a large report.

Open menus and popovers before claiming they work. Resolving a CSS variable
with a closed popup does not verify its consumer. A hidden subtree with correct
geometry does not prove that a person can see or reach it.

Use real Tab and Shift-Tab for keyboard claims, plus the relevant activation,
dismissal and return-focus steps in the dossier. Calling `.focus()` can inspect
a style, but cannot prove the user's keyboard route. Codex successfully tested
real keyboard input in the embedded Claude preview when a separate preview URL
was unavailable. Use supported tools; do not bypass access restrictions.

Keep one evidence ledger from the first design group:

| Scenario/state | Artifact identity | Width | Actions/checks | Evidence path and actual bounds | Result / gap |
| --- | --- | --- | --- | --- | --- |
| [ID + precise state] | [version/hash] | [1280 or 1024] | [what was exercised] | [file + dimensions] | [pass, fail, unverified] |

Separate Claude's report, Codex's direct observation and producer acceptance.
“No console errors” is not visual acceptance. A todo marked done is not evidence.
Reuse a capture only when its source, state, viewport and method still apply;
consecutive hashes alone do not prove two images show the same state.

## 6. Keep the loop efficient

Use Claude for visual composition and changes that benefit from its design
workspace. Prefer Codex or an existing suitable harness for repeatable parsing,
counts, hashes, computed-style checks and keyboard interaction when access
permits. Keep successful harnesses; do not ask Claude to rebuild them per prompt.

During iteration, verify affected scenarios and shared dependencies. Maintain
the full S01–S19 and keyboard/accessibility ledger so omissions are visible
early. At the final milestone, complete the required independent checks at
both viewports; do not infer full coverage from one representative screen.
Do not rerun a full matrix for a manifest or wording correction.

If a comparison differs, first check source identity, scenario/selection,
viewport, capture boundaries and rendering readiness. Then inspect the actual
visual difference. Do not immediately repair the design, silently replace the
baseline or call an evidence mismatch a product bug.

When a tool fails, identify the narrow failed capability and choose a supported
alternative. In #32 the background design checker repeatedly returned no
verdict. Record that limitation; another automatic retry is not stronger proof.
Browser disconnection and Claude usage exhaustion are separate problems.

## 7. Preserve context and resume exactly

Use Claude's native new-chat summary at a natural batch boundary when the
conversation is large. Project files remain available, but verify the summary
against the durable decision/evidence records before relying on it. It can
carry forward stale holds or overstate completion.

Keep a concise checkpoint containing:

- Current artifact/package identities and preserved baseline.
- Completed scenario IDs and exact evidence, including invalidated evidence.
- Approved decisions and exceptions; pending choices kept separate.
- Last successful operation, unfinished work and any exact mismatch.
- The next bounded action and explicit stop condition.

```text
Resume only [unfinished operation] on [exact artifact/version]. Read the
existing result/ledger first; the previous run completed [IDs and evidence].
Do not repeat edits, overwrite baselines or recapture passing cases.

Finish [specific missing checks/deliverable]. Preserve [decisions/exclusions].
Stop at the completed report, a concrete unresolved discrepancy, or an actual
service usage-limit interruption. Return changed IDs, evidence and what remains.
```

Respect Matthew's current usage instruction. When authorized to continue until
exhaustion, a 90% warning alone is not a service rejection; #32 continued beyond
that warning. Conversely, do not click Resume repeatedly after an actual
“you've hit your limit” pause. Save the visible reset time without promising
that another prompt will fit. Do not assume background work continues after
Codex ends its turn or arrange a later run unless asked.

## 8. Finish with a reviewable result

The handoff should name the exact prototype and imported system, summarize
accepted design decisions, map every scenario to its owning product-spec slice,
and identify any unresolved issue or follow-up. Supply ordered producer steps
with expected outcomes at both viewports. Keep simulated behavior clearly
separate from implemented behavior.

A passing Claude report is evidence to inspect, not permission to close #14.
Independent viewport/accessibility checks and explicit Producer approval remain
required. Do not claim production persistence, collaboration, media acquisition,
or Resolve execution from a successful prototype walkthrough.

The most useful pattern from #32 was a compact request, one reviewable result,
a targeted correction and a durable checkpoint. Its expensive mistakes were
trusting evidence labels too long and discovering coverage gaps near the end.
For #14, track those gaps from the first scenario group while keeping the
conversation focused on the writer's experience.
