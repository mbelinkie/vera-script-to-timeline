# Issue 13 plan — VERA suite design contract and Claude artifact structure

## Objective

Produce the bounded, producer-reviewable design decision and Claude brief for
GitHub issue #13. The deliverable decides how Research Video Clips and Script
to Timeline should be organized in Claude Design, defines their shared design
language and authorization boundaries, and identifies the inputs required
before a high-fidelity Script to Timeline prototype begins.

## Scope

1. Inspect the current Research Video Clips Claude artifact and its checked-in
   design-review bundle, including the actual scenario inventory, component and
   state breadth, role variants, viewport coverage, approval status, and open
   follow-on work.
2. Compare a single suite artifact against separate product artifacts in one
   Claude project and make one bounded recommendation.
3. Define the source of truth and propagation rule for shared primitives:
   design tokens, suite shell and switching, comments and mentions, Topics,
   search, readiness and remediation, dialogs, accessibility, responsive
   behavior, and common component states.
4. Define where Research Video Clips and Script to Timeline must remain
   product-specific rather than forcing false uniformity.
5. Define Desktop/Web presentation treatment and reciprocal browser suite
   switching without weakening separate product authorization, membership,
   deployment, data-ownership, or desktop-runtime boundaries.
6. Provide an executable Claude brief and a step-by-step producer acceptance
   checklist for the decision artifact.

## Exclusions

- No Research Video Clips redesign or edit to its Claude artifact, design
  bundle, production code, or roadmap.
- No Script to Timeline prototype, high-fidelity screen, production UI, shared
  UI package, or token wiring.
- No change to contracts, fixtures, golden files, generated types,
  dependencies, deployments, permissions, data, or runtime configuration.
- No resolution, consolidation, or override of issue #21's independent token
  reconciliation decisions.
- No dispatch or implementation of another roadmap issue.

## Authority and inputs

- GitHub issue #13 and the VERA Script to Timeline roadmap are the live scope,
  routing, ownership, and review authority.
- `docs/Script-to-Timeline Product Spec - Fable Rev2.md` supplies the
  authoring, collaboration, role, research-integration, build, and deployment
  behavior.
- `docs/IMPLEMENTATION_PROGRESS.md` supplies historical acceptance and frozen
  boundary context only.
- The Research Video Clips `BEHAVIOR-CONTRACT.md`,
  `WEB-EDITION-DESIGN-BRIEF.md`, `APPROVAL-CHECKLIST.md`, `UI-CONTEXT.md`, and
  live Claude artifact supply the observed and approved Research design input.

## Contracts, fixtures, and dependencies

- Touched contracts: none.
- Touched fixtures or golden files: none.
- New dependencies: none.
- Roadmap dependencies: `None`, as required by issue #13.
- Related issue #21 remains independent. Its producer-approved token output is
  a prerequisite input to later high-fidelity visual work, not a dependency
  for completing this conceptual structure and contract decision.

## Deliverable

Create `docs/vera-suite-design-contract-and-claude-brief.md` containing:

- the observed Research artifact inventory and regression risks;
- the artifact-structure comparison and recommendation;
- the versioned shared design-language boundary and source-of-truth table;
- Desktop/Web and product-specific treatment;
- the safe reciprocal browser suite-switching contract;
- explicit deployment, membership, authorization, data, and runtime boundaries;
- the shared-change propagation workflow without shared production UI code;
- prerequisites, inputs, and build instructions for Claude;
- automated evidence and a producer acceptance checklist.

## Verification

1. Run Markdown/style checks available in the repository.
2. Run `npm run validate` because the repository gate is the authoritative
   broad regression check, even though the slice is documentation-only.
3. Run `git diff --check` and inspect the final diff for scope drift.
4. Confirm `/contracts`, `/fixtures`, generated types, accepted tests, golden
   files, dependency manifests, and lockfiles are unchanged.
5. Reinspect issue #13 and move it to `In review` with retained evidence only
   after the deliverable and checks are complete. Never mark it `Done`.

## Producer acceptance

The final handoff will identify the exact document to open and give ordered
checks for: the Research inventory, artifact decision, source-of-truth table,
Desktop/Web treatment, safe suite switcher, explicit system boundaries,
high-fidelity prerequisites, and the precise acceptance or failure response.
Producer acceptance remains authoritative.
