# Issue 19 plan — external template intake and project-scoped reuse

## Objective

Produce the bounded, Producer-reviewable design decision required by GitHub
issue #19. The decision must let later slices register externally authored
template packages, make exact immutable revisions available to selected
projects, and let an authorized project creator copy none, some, or all
eligible templates into a new project without turning visibility into access or
silently changing revision identity.

## Scope

1. Define the accepted intake envelope, manifest and provenance evidence,
   revision identity, licensing declarations, validation, quarantine, and
   failure-reporting behavior.
2. Define the conceptual registry and project-library entities, ownership,
   immutable revision pins, withdrawal, retirement, supersession, and retained
   reproducibility.
3. Decide the unresolved copy model and explain the trade-off between a
   project-local immutable snapshot and a governed reference to a shared
   source.
4. Define a fail-closed new-project flow for selecting none, some, or all
   currently eligible templates and reporting duplicate, unavailable,
   incompatible, or unauthorized choices.
5. Define capability boundaries for intake, project-template administration,
   project creation, discovery, and cross-project copying without prematurely
   implementing a role or authorization system.
6. Provide Producer-reviewable scenarios and assign later work to template
   registration, project creation, compiler/placement, and authoring UI slices.
7. Identify every proposed contract as a separate Producer-approved follow-up;
   issue #19 changes no production contract.

## Exclusions

- No template design, animation, generation, conversion, repair, or format
  translation, including Fusion, After Effects, OGraf, or another native
  authoring format.
- No production registry, project library, project creation, copy command,
  authentication, authorization, persistence, object storage, compiler,
  Resolve placement, browser UI, or migration implementation.
- No import of historical or production templates and no mutation of a real
  VERA, research, Resolve, or design project.
- No shared contract, generated type, fixture, golden file, accepted test,
  dependency, manifest, lockfile, or application-code change.
- No decision about a native template format's semantic controls, render
  correctness, or Free/Studio fallback. Those remain format and placement work.
- No workspace-wide standards/override system or rights-evidence workflow
  beyond the minimum declarations and gates needed for safe intake and copy.

## Authority and accepted inputs

- GitHub issue #19 and the VERA roadmap are the live scope, routing,
  dependency, ownership, and review authority.
- `docs/Script-to-Timeline Product Spec - Fable Rev2.md` supplies immutable
  dependency revisions, project membership boundaries, template pinning,
  project-scoped `TemplateItem` / `TemplateRevision`, build snapshots, and the
  Phase 9 registry and package boundaries.
- Producer-accepted issue #13 supplies the VERA suite design contract, the
  hosted-Web/local-agent presentation, independently authorized project
  boundaries, authorization-valid DOM rule, and status/remediation grammar.
- `docs/plans/curated-fusion-graphics.md` supplies the existing separation
  between a curated immutable registry, semantic package validation, compiler
  work, Studio placement, and Phase 2 authoring. It does not authorize arbitrary
  template import or format-specific implementation here.
- `docs/IMPLEMENTATION_PROGRESS.md` is historical acceptance context only.

## Slice boundary before writing

- Roadmap dependency: issue #13, closed and `Done`.
- Dependency justification: #13 defines the accepted suite/project
  authorization and design-language boundary that the project-creation flow
  must preserve.
- Touched shared contracts: none.
- Touched fixtures or golden files: none.
- Touched application or infrastructure code: none.
- New dependencies: none.
- Planned issue artifacts: this plan and
  `docs/investigations/issue-19-external-template-intake.md` only.

## Decision tests

Reject any proposed behavior if one of these tests fails:

1. Can a later source edit, withdrawal, or permission change alter an existing
   project use, checkpoint, or build? If yes, the copy is not reproducible.
2. Can a visible name, list result, source-project membership, or stale setup
   token grant package bytes or destination access? If yes, the authorization
   boundary is invalid.
3. Can a retry, duplicate selection, or `all` selection silently choose a
   different revision or create a partial library? If yes, the flow is not
   deterministic.
4. Can a package enter a project before its exact bytes, declared
   dependencies, compatibility, and licensing evidence pass validation? If
   yes, intake is not fail-closed.
5. Can removal or supersession erase evidence needed by an existing use,
   checkpoint, or build? If yes, lifecycle semantics are destructive.
6. Does the decision require a production schema, role implementation, native
   format adapter, compiler, Resolve, or browser UI to be valid? If yes, move
   that work to the bounded follow-up.

## Verification

1. Map every issue #19 acceptance criterion to a named design section.
2. Check the design against the product specification, issue #13, and the
   curated Fusion plan without importing their later implementation scope.
3. Run `git diff --check` and inspect the full diff for scope drift.
4. Confirm only the two issue #19 documentation artifacts changed.
5. Confirm contracts, fixtures, goldens, generated types, accepted tests,
   dependency manifests, lockfiles, and application code are unchanged.
6. Run the pinned `npm run validate` repository gate.
7. Reinspect issue #19 and move it only to `In review` with the commit and
   concrete automated evidence. Never mark it `Done`.

## Producer acceptance outline

The final handoff directs the Producer to the exact intake boundary, copy-model
decision, lifecycle and authorization tables, new-project transaction, required
scenarios, and implementation split. Every step names an expected result and
the exact acceptance or failure response. Issue #19 remains `In review` until
the Producer explicitly accepts both the design and its implementation
boundaries.
