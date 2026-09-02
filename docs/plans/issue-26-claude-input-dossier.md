# Issue 26 plan — semantic Claude input dossier

## Scope and gates

Assemble only the producer-reviewable semantic input to issue #14. Starting
baseline: committed main `163ecfa672fabeaaaae30fe3befa97f17aefe127`.
Issue #26 was Ready, unclaimed, with exactly `model:sol` and `effort:high`;
canonical dependencies #13 and #24 were both CLOSED/Done. The roadmap claim
uses `gpt-5.6-sol`, high effort, task `01a05fc0-5c61-7822-9038-d0721feb3541`,
and dedicated branch `codex/issue-26-claude-input-dossier`.

Read before implementation: AGENTS.md; the #13 and #24 plans and accepted
artifacts; product-spec §§4–10, relevant Phase 2/3/4/5/9 slices in §11,
§§13–14; accepted #27 capture reconciliation; and issues #14, #21, #26.
An initial shared roadmap lock prevented requests; a subsequent inspection
and claim succeeded without bypassing the lock. Claim was the first roadmap
mutation.

## Deliverables

Under `docs/prototypes/issue-26/`:

- `README.md`: source-pinned required/forbidden manifest, phase boundaries,
  decision owners, open decisions, and producer handoff.
- `scenario-spine.md`: tiered scenarios, role/capability matrix, semantic IA,
  component/state inventory, and phase/slice ownership.
- `content-kit.md`: fictional content IDs referencing the accepted #24 kit,
  deterministic reset state, and evidence identities; no schema fixtures.
- `acceptance.md`: deterministic scenario, viewport, pointer, keyboard, and
  accessibility checks plus the dossier's own producer acceptance steps.
- `claude-packets.md`: concise Pass 1 and Pass 2 instructions for later use.

## Exclusions and judgment boundaries

No visual hierarchy, layout, color, typography/token values, component
anatomy, navigation placement, or responsive composition decisions. The
source-owned two-column meaning is retained without copying visual literals.
No Claude artifact access/edit, UI/app/product code, contracts, fixtures,
goldens, accepted tests, private material, real media, deployments, data,
authentication, persistence, capture engine, Resolve, or Fusion actions.
No #14/#21 work, task dispatch, or issue completion.

Reviewer means the read-only Viewer journey; no deferred Reviewer role.
#24 decisions are conceptual coverage, not proof they exist in frozen v1.
#27 P27-01 keeps Periodic execution deferred while preserving #24 vocabulary.

## Contracts, fixtures, dependencies

Touched contracts/fixtures/generated types/accepted tests: none. The content
kit contains documentation-only aliases, not wire IDs or test data.
New package dependencies: none.
Roadmap prerequisites: #13 supplies accepted suite authority; #24 supplies
accepted content semantics. #27 is an already accepted reconciliation source,
not a new dependency mutation. #21 blocks later high-fidelity design, not this
symbolic semantic dossier. Existing dependencies remain unchanged.

## Verification

1. Check source documents byte-for-byte against their accepted commits.
2. Check local links, manifest/scenario/content references, all D24-01 through
   D24-19, every #24 required view, and both viewport/accessibility paths.
3. Scan new documents for private-service URLs, absolute local paths, secrets,
   visual literals, and scope drift; all fictional links use `.invalid`.
4. Run `rtk git diff --check` and the repository gate `rtk npm run validate`
   with pinned runtimes. No new tests are needed for this documentation slice.
5. Confirm only this plan and the five dossier Markdown files changed.
6. Commit/push, retain evidence, and use `rtk npm run roadmap -- review 26`
   to move only #26 to In review. Keep producer acceptance pending.

## Producer acceptance

Follow `docs/prototypes/issue-26/acceptance.md` §1: inspect pins/manifest,
walk Tier 1 and Viewer/runtime cases, confirm fictional IDs, compare #24 and
#27 coverage, inspect open decisions and packets, then reply `Accepted` on
#26 or report the first incorrect authority/scenario/content ID. The later
prototype checks are a script to review, not completed UI evidence.

## Retained verification results

- Five authority artifacts matched their pinned Git blobs byte-for-byte.
- Documentation checks passed: 24 R rows plus 19 individual D24 rows;
  19 scenario/test pairs; 35 fictional-content and 14 evidence aliases;
  all 14 K24 required views; local file/section links; table structure;
  reference bounds; whitespace; URL/privacy/visual-literal scan.
- Manual scope review confirmed semantic requirements and future test scripts
  only. No actual browser/artifact, layout, screenshot, keyboard/a11y, media,
  capture, or Resolve verification is claimed. Exact visual judgments remain
  with Claude and the Producer in #14.
- Fresh worktree bootstrap: the first validation attempt found the locked
  JavaScript dependencies uninstalled. `npm ci` installed the existing lockfile
  graph without manifest/lockfile changes; no new dependency was introduced.
- Pinned Node 24.19.0/npm 11.17.0 full `npm run validate` passed: generated
  contracts current; TypeScript lint/typechecks; 91 contract, 1 tooling,
  6 progress, and 23 roadmap tests; Python Ruff/format, strict mypy across
  51 source files, and 173 pytest tests. No tests skipped.
- `git diff --cached --check` passed. Staged scope is exactly this plan plus
  the five dossier Markdown files; all existing tracked files are unchanged.

Judgment calls retained for review: the OC→VO sample is edited explicitly to
OC→VO→OC in the test rather than rewritten as source content; all K24 views
are retained in focused tiers; Reviewer is a Viewer journey; Periodic is
conceptual/deferred under A27; future Preview option policy and detailed cut
permissions remain open rather than invented. Producer acceptance is pending.
