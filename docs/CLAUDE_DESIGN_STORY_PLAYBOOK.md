# Sol–Claude design story playbook

This is the required operating guide for VERA design stories that use Claude
Design. It governs how Sol frames the work, collaborates with Claude, spends
Claude's limited design tokens, and obtains Producer decisions before expanding
a design.

It does not replace the assigned issue, product specification, accepted design
artifacts, or Producer authority. If they conflict, stop and resolve the
conflict before asking Claude to edit anything.

## The operating model

### Sol is the product owner and design lead

Sol owns the quality of the direction, not merely the quality of the prompt.
Before Claude designs, Sol must:

- audit the relevant product behavior, accepted artifacts, neighboring flows,
  technical constraints, scenarios, edge cases, and failure states;
- recommend the most productive next step and explain why it is the cheapest
  useful learning step;
- challenge requests or inherited assumptions that would produce a misleading,
  incomplete, or needlessly expensive design;
- distinguish a broken product mechanic from a visual-polish problem;
- identify implications for related VERA surfaces instead of waiting for the
  Producer to notice them; and
- ask, **“What would make this design fail?”** before preparing a Claude edit.

Sol should say plainly when warranted:

- “I do not think we should send this prompt yet.”
- “These examples are the same product mechanic with different content.”
- “This direction conflicts with an accepted pattern or creates a downstream
  problem.”
- “The smallest useful test is one representative state, not the full story.”
- “The product cannot yet promise this behavior without a technical proof.”

### Claude is a trusted co-designer

Claude is not a blind renderer. Ask it to critique the framing, find missing
cases, propose alternatives, explain tradeoffs, and recommend a direction.
Give it room to exercise judgment over visual hierarchy, composition,
interaction alternatives, component anatomy, responsive behavior, and visual
critique.

Trust does not mean unreviewed execution. Sol must inspect Claude's reasoning
and rendered result against the product goal, accepted behavior, and Producer
criteria. When Sol rejects Claude's recommendation, record the product reason;
do not silently replace design judgment with pixel-level micromanagement.

### The Producer selects and accepts

The Producer chooses among meaningful directions, resolves product ambiguity,
and accepts the exact artifact. Sol should bring the Producer small, legible
decisions early instead of one expensive finished design late.

## The risk-based design funnel

Do not send a full-artifact design prompt until the Producer has selected a
focused option and its bounded pilot has succeeded, unless the documented
exception below applies.

### 1. Frame the product problem on the Codex side

Before using Claude, produce a compact design brief that names:

- the user and job to be done;
- the exact decision or product mechanic under design;
- the authoritative specifications and accepted visual precedents;
- what must be reused and what is open to change;
- the normal, edge, conflict, unavailable, and failure states that matter;
- technical facts, assumptions, and capabilities the design must not invent;
- related surfaces that could be helped or harmed by the decision;
- explicit exclusions and preserved accepted artifacts;
- the evaluation rubric; and
- the smallest representative sample that can disprove a bad direction.

Build the scenario map now, even though Claude will initially render only a
small sample. A full scenario map prevents late discoveries; a full prototype
is not required to obtain that coverage.

Apply the capability-evidence gate below before feature design. Labeling an
unknown capability “simulated” does not clear it.

### Capability evidence before design

Producer direction, 2026-10-24: every feature under design must already work
or have evidence that its required mechanism is possible. Before a new story
or a material feature revision, add one compact matrix to its existing brief:

`promised action → implementation/test or real capability proof → exact supported limits → missing proof issue`

Reuse delivered evidence; a new report, full backend build or repeated test
campaign is not required. Ordinary application-state/UI work can use existing
domain operations and focused executable tests; a missing finished frontend
is not itself a feasibility gap. External-application/service claims need
actual runtime evidence for the specific operation, controls and relevant
save/reopen/output behavior. API method lists, mocks, schemas, accepted HTML,
and a different successful round-trip subset do not prove that capability.

If a required capability is unknown, unsupported or only assumed, checkpoint
and mark the design issue **Blocked** with a canonical dependency on the
smallest bounded proof. Pause new feature-design/Claude edit prompts; preserve
existing artifacts and owner claims. Resolve the proof, or ask for a concrete
Producer scope reduction/deferral. A negative proof can finish its investigation
but cannot make the promised feature design-ready unchanged. Re-check the
matrix before resuming. Keep proofs independent of their consuming design to
avoid circular prerequisites; do not require the whole production implementation
that will later consume the design.

Authority-index/naming-only work may state “no new functional promise” and
continue; this is not an excuse to add unproved interactions. A simulation may
demonstrate the UI of an already-proved capability, not substitute for proof.

For transitions, verify script-declared type/duration/alignment and real
effect-specific settings reach the intended Resolve boundary, survive reopen,
and produce the intended picture without unrequested audio/timing changes.
Inventory discovery, outbound creation and inbound observation are separate
claims. Issue #292 owns the bounded proof; #145's accepted subset does not
prove them. Apply equivalent specificity to other external feature promises.

### 2. Consult Claude before asking it to edit

Start with a design conversation, not an implementation order. Give Claude the
brief and accepted references, then ask it to:

- challenge the framing and surface contradictions;
- identify missing scenarios or misleading assumptions;
- separate distinct interaction mechanics from content variations;
- recommend the highest-information representative scenario;
- propose two or three materially different approaches; and
- state which approach it recommends and why.

Resolve material contradictions before editing. A useful disagreement now is
cheaper than a polished rejection later.

### 3. Compare a focused A/B or A/B/C sample

Create two or three controlled treatments of one representative scenario.
Add at most one edge state when it is necessary to expose the difference.

Keep constant across the options:

- user goal and semantic behavior;
- story content and fixture data;
- viewport and surrounding context;
- accepted design-system primitives; and
- evaluation criteria.

Change only the decision being tested. Label each option and its hypothesis.
The alternatives must use meaningfully different interaction mechanics or
information hierarchy; color, spacing, or copy variations alone do not satisfy
this gate.

Here, “A/B” means side-by-side Producer evaluation of controlled prototype
alternatives. It is not a statistical production experiment.

Work only on named experimental surfaces. Do not overwrite an accepted page.
When the edit has meaningful blast radius, create and verify a checkpoint
before Claude begins.

### 4. Stop for the Producer decision

Present the focused options with:

- Sol's recommendation;
- Claude's recommendation and reasoning;
- the product tradeoff each option makes;
- the scenarios most likely to break it;
- known technical assumptions;
- downstream effects on related VERA surfaces; and
- the next smallest test after selection.

Record the chosen direction, rationale, rejected alternatives, and unresolved
questions. Do not expand while the underlying mechanic remains undecided.

If every option is wrong, return to stages 1 or 2. Do not ask Claude to redesign
the full artifact around a fourth half-settled idea.

### 5. Pilot the accepted mechanic

Expand the selected option only far enough to prove that it survives:

- the normal state;
- one important edge, conflict, or failure state;
- the compact presentation; and
- the required pointer, keyboard, and non-color behavior.

Use the issue's required viewports when viewport behavior is part of the
decision. Inspect the rendered pilot before continuing. If the mechanic fails,
return to the earlier gate; do not bury the failure under visual polish.

### 6. Expand and accept the full design

Only after the pilot succeeds may Claude propagate the accepted mechanic
through the full bounded scenario set. Expand in reviewable batches, reuse
accepted components, and regression-test the shared surfaces after each batch.

Judge the result against product goals and scenario evidence, not merely
whether Claude followed the prompt. Final acceptance must cover the exact
artifact, required states and viewports, interaction and accessibility evidence,
known exceptions, and any follow-up technical work.

## When comparison is required

A focused A/B or A/B/C gate is required when any of these remains unresolved:

- the interaction model or decision flow;
- information hierarchy or component anatomy;
- reuse of a pattern from another VERA surface;
- a technical assumption that changes what the UI may promise;
- responsive structure or a high-blast-radius shared renderer; or
- a disagreement between Sol, Claude, the Producer, and an accepted precedent.

The gate may be skipped only for a narrow correction or a mechanical use of an
already Producer-accepted pattern. Record one sentence naming the accepted
pattern and why no material design decision remains. If the work grows beyond
that claim, restore the focused-option gate.

| Situation | Required route |
| --- | --- |
| New reconciliation or authoring mechanic | Compare focused options, obtain Producer selection, then pilot. |
| Spacing defect in an accepted component | Record the accepted-pattern exception and make the targeted correction. |
| Producer rejects the pilot's mechanic | Return to framing or Claude consultation; do not launch a full redesign. |

## Spend Claude tokens on design judgment

### Sol should do these tasks in Codex

- specification and issue analysis;
- authority, dependency, and accepted-artifact checks;
- scenario and edge-case maps;
- state tables, counts, copy audits, and page inventories;
- technical-feasibility questions and cross-surface impact analysis;
- acceptance matrices and deterministic test harnesses;
- prompt assembly and removal of redundant context;
- checkpoint names, hashes, decision records, and continuation notes; and
- source inspection and mechanical verification after Claude edits.

Sol may create analytical diagrams, wireframes, or diagnostic prototypes when
they make the product question clearer. They are not substitutes for the
Claude-designed and Producer-accepted artifact.

### Claude should spend tokens on these tasks

- critiquing the design problem and the proposed sample;
- generating and comparing visual or interaction approaches;
- recommending hierarchy, composition, and component anatomy;
- refining responsive behavior and state presentation;
- applying focused visual changes on the named experimental surfaces; and
- reviewing the rendered design for clarity, coherence, and accessibility.

### Keep each Claude pass bounded

- Give Claude a decision-ready packet, not an unsorted document dump.
- Reference stable accepted context instead of repeatedly restating it.
- Put one design question or one coherent edit batch in each pass.
- State the outcome, success criteria, edit boundary, evidence, and stop rules.
- Ask Claude to preserve everything outside the named scope.
- Inspect the result before sending the next prompt.
- Diagnose whether a bad result came from the product idea, the prompt, or the
  execution before requesting another edit.
- Never chain broad “keep going” prompts through a direction that already looks
  wrong.

If Claude is near a usage limit, stop at a consistent boundary. Do not begin a
large renderer rewrite, cross-page migration, or full scenario expansion that
cannot safely finish. Preserve a verified checkpoint and record the exact first
unfinished task.

## Copy-ready working templates

Replace bracketed text and delete irrelevant fields. Keep the completed prompt
short; these templates are checklists, not an instruction to paste every line.

### Pre-Claude product/design brief

```text
Design decision: [one mechanic or question]
User and job: [who is doing what, and why]
Outcome: [what must become easier, clearer, or safer]
Authoritative behavior: [spec/issue/accepted decisions]
Accepted visual precedents: [exact artifacts/components]
Open design latitude: [what Claude may decide]
Representative scenario: [smallest high-information example]
Coverage map: [normal, edge/conflict, unavailable/failure]
Capability matrix: [promised action → working evidence/proof → limits → blocker]
Related surfaces: [likely upstream/downstream effects]
Exclusions and preserved artifacts: [hard boundary]
Evaluation rubric: [how the Producer will compare options]
What would make this fail: [top risks]
```

### Claude consultation and pushback request

```text
Act as my co-designer before editing anything. Review the attached brief and
accepted references. Challenge the framing, identify missing cases or technical
promises, and separate genuinely different mechanics from content variations.

Recommend the smallest representative design test. Propose two or three
materially different approaches, explain their tradeoffs and likely failure
modes, and state which you recommend. Ask only questions whose answers would
materially change the test. Do not edit the artifact yet.
```

### Focused option-generation prompt

```text
Create [two/three] controlled treatments of [representative scenario] on
[named experimental surface]. Keep the content, semantic behavior, viewport,
surrounding context, and accepted primitives identical. Vary only [design
decision]. Label each option and its hypothesis.

The options must differ in interaction mechanic or information hierarchy, not
merely styling. Preserve [accepted artifacts/pages] exactly. Stop after the
focused comparison; do not propagate a choice to other scenarios. Report your
recommendation and the hardest case for each option.
```

### Producer comparison checkpoint

```text
Decision: [one sentence]
Sol recommends: [option and product reason]
Claude recommends: [option and design reason]
Option A: [mechanic, benefit, cost, failure risk]
Option B: [mechanic, benefit, cost, failure risk]
Option C, if present: [mechanic, benefit, cost, failure risk]
Technical assumptions: [list]
Related-surface effects: [list]
Next smallest proof after selection: [normal/edge/compact pilot]
Producer result: [choose, revise, reject all, or unresolved]
```

### Targeted revision prompt

```text
Revise only [named option/component/state] on [named experimental surface].
The product mechanic and accepted decisions are unchanged. Fix these observed
problems: [short numbered list]. Preserve [explicit unaffected behavior and
surfaces]. Inspect the rendered result and report any conflict instead of
redesigning the surrounding flow. Stop when this focused correction is done.
```

### Approved-pattern expansion prompt

```text
The Producer selected [option/mechanic] at [decision record]. Apply that exact
mechanic to this pilot only: [normal state], [edge/conflict/failure state], and
[compact presentation]. Reuse [accepted components] and edit only [named
experimental surfaces]. Preserve all other artifacts.

Verify semantic consistency, pointer and keyboard behavior, non-color meaning,
responsive composition, and the stated technical assumptions. Stop after the
pilot and report mismatches; do not expand to the full scenario set yet.
```

After the pilot is accepted, use the same prompt with the full bounded scenario
list and explicit regression requirements.

### Session-limit/checkpoint handoff

```text
Stop before starting another broad edit. Preserve a source-identical checkpoint
of [named working surfaces] and verify [comparison method/hash]. Record:
- completed changes and checks;
- exact pages changed and preserved;
- current consistent state;
- first unfinished task;
- remaining verification;
- assumptions or decisions needed to resume.

Do not begin work that cannot finish safely within the remaining session.
```

## Stop and recovery rules

Stop the current design pass when:

- the scenario model is incomplete enough to change the interaction;
- a required technical capability is unknown;
- the proposed variants differ only cosmetically;
- no shared evaluation rubric exists;
- the Producer rejects the underlying mechanic;
- Claude identifies a material contradiction;
- the edit would touch an accepted artifact without authorization; or
- the remaining Claude session cannot finish the next coherent batch.

Stopping does not mean waiting passively. Sol should retain the evidence,
identify the smallest missing decision or proof, recommend the next move, and
keep unrelated accepted work untouched.

When a result is rejected, classify the failure before acting:

- **Framing failure:** return to the product brief.
- **Missing scenario:** update the coverage map, then reconsider the sample.
- **Wrong mechanic:** consult and compare again.
- **Good mechanic, weak execution:** issue a targeted revision.
- **Technical contradiction:** block for proof or a Producer scope reduction/deferral.
- **Token interruption:** checkpoint and resume from the first unfinished task.

## What issue #123 taught us

Issue #123 demonstrated why this funnel is mandatory. The scenario audit came
too late, multiple complete treatments were polished before the interaction
model converged, and reuse of the S03/S05 language was accepted too literally
before proving that it fit inbound reconciliation. Claude then spent substantial
tokens expanding and repairing large artifacts, eventually reaching session
limits during difficult renderer work.

Sol should have challenged the direction sooner, mapped the full scenario space
without rendering it, asked Claude to critique the mechanic, and compared a few
focused treatments on one representative reconciliation case. The lesson is not
that Claude needed a longer prompt. The team needed earlier product judgment,
smaller experiments, and a Producer gate before expansion.

## Checklists

### Before Claude

- [ ] The issue, specification, accepted artifact, and relevant neighboring flow were audited.
- [ ] Sol has stated a recommendation and the most productive next step.
- [ ] The scenario map covers normal, edge/conflict, unavailable, and failure behavior.
- [ ] Every promised feature passes the capability-evidence gate; unresolved proof is a canonical design blocker, not a simulated promise.
- [ ] The smallest representative sample and evaluation rubric are named.
- [ ] Accepted artifacts and edit boundaries are explicit.
- [ ] “What would make this fail?” has a concrete answer.

### Focused-option Producer gate

- [ ] Two or three controlled, materially different options are visible together.
- [ ] Content, semantics, viewport, context, and accepted primitives are constant.
- [ ] Sol and Claude each give a recommendation with reasons.
- [ ] Risks, technical assumptions, and related-surface effects are disclosed.
- [ ] The Producer chose, requested a focused revision, or rejected all options.
- [ ] The decision and rejected alternatives were recorded before expansion.

### Before full expansion

- [ ] The chosen mechanic passed the normal state.
- [ ] It passed one important edge, conflict, or failure state.
- [ ] Compact and required interaction/accessibility behavior were inspected.
- [ ] The rendered pilot was reviewed, not merely reported as prompt-compliant.
- [ ] The full bounded scenario list and regression surfaces are explicit.

### Final acceptance

- [ ] Only authorized experimental or successor artifacts changed.
- [ ] Every required scenario and viewport has retained evidence.
- [ ] Shared and accepted surfaces passed regression checks.
- [ ] Product goals, semantics, keyboard/accessibility behavior, and non-color meaning were reviewed.
- [ ] Capability evidence still covers every promised action; unsupported behavior is explicitly deferred or removed by the Producer.
- [ ] The Producer accepted the exact artifact or identified the first unacceptable state.
- [ ] Remaining technical or design work is recorded without expanding this story.
