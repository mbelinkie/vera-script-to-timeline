# Issue #156 — authoring realization inspection checkpoint

Saved at the Producer's request to stop at a checkpoint on 2026-10-08,
11:29 EDT. **Incomplete planning work; no acceptance requested.** This is a
resume record, not the realization plan or an approved contract-change note.

Resumed at the Producer's request on 2026-10-08 with bounded Luna source
inventory and independent review. The completed proposed
[realization plan](issue-156-authoring-realization.md) and its retained
verification evidence supersede the provisional decisions and remaining-work
status below; this original checkpoint remains historical.

## Ownership and permitted scope

- Issue: [#156, Accepted authoring-contract realization plan](https://github.com/mbelinkie/vera-script-to-timeline/issues/156).
- Chat identity: `01a11c1d-6413-7e50-9022-fc1a7357e1db`.
- Route: `gpt-6.1-sol` / `xhigh`; Light workflow, no delegated agents.
- Worktree: `/Users/matthewbelinkie/.codex/worktrees/5f1e/VERA Script to Timeline`.
- Branch: `codex/issue-156-authoring-realization`.
- Baseline: `96978919616df0148d9c4b06781aeb80acfa85e4`.
- Preflight passed: Ready; exactly `model:sol` and `effort:xhigh`; Size L;
  Acceptance Producer; complete planning acceptance criteria; no competing
  claim. Canonical prerequisites #55/#56/#127 were all Closed and Done.
- The dedicated branch was created from detached HEAD. The first roadmap/work
  mutation was the successful claim using the actual chat identity and route.
  The issue remains claimed and In progress, not In review or Done.

Authorized outcome: one bounded documentation plan translating accepted
authoring decisions into precise, sized schema/compiler/migration/UI handoffs,
mixed-rate preparation, frozen-v1 regression gates, and separate v2/23.976
Studio qualification. Before implementation, state scope, exclusions,
contract/fixture boundaries, dependency justifications, automated checks, and
Producer acceptance steps.

Excluded: product code; actual schemas/generated types/fixtures/goldens or
accepted-test changes; migrations; Research/private data or original-media
mutation; paid/provider calls; uploads/sharing; Resolve operations; repository
migration; automatic creation/dispatch of implementation packages. Preserve
#148's independent scope, dependencies, claim, branch, and private bundle.

## Sources already inspected

The accepted design documents are available in Git objects but are **not all
present in this main-baseline checkout**. Read their pinned revisions; do not
assume they were merged or cherry-pick them as incidental setup.

| Authority | Exact revision and artifact | Inspection result |
| --- | --- | --- |
| #147 planning direction | `75029de57baa594d3dfc7f509a09cfc21943e088`; `docs/investigations/issue-147-completion-roadmap-audit.md`, `docs/issue-147-producer-decisions.md` | Accepted Q1: local Studio, single writer, English initial sources, qualified 23.976, durable service/companion, review MP4/Drive. Prompter optional; Free and inbound remain later scope. No runtime acceptance follows from the audit. |
| #55 | `a561735e7b0c735ccd6185aa407e82581a19b2d9`; `docs/investigations/issue-55-presenter-visual-contract.md` | Read the full note and issue acceptance record: presenter/default precedence, temporary still, visual-only timing, undefined/unresolved/intentional states, proposed files/types/fixtures, compatibility and acceptance. |
| #56 | `9e2b8817ffe97fbc9d6fcf31099aca578c5022bb`; `docs/investigations/issue-56-ordered-visual-contract.md` | Read the note and acceptance evidence: structural sequence, one cutaway level, continuous parent, returns, edits, anchor lifecycle, trim, thumbnail, complete-clip policy, migration and all four v2 contracts. |
| #127 | `cdaa3106da91fb5a040c8bbde22e2c61c0d3e162`; `docs/prototypes/issue-127/successor-handoff.md`, `adopt-adapt-defer.md` | Accepted bounded successor: quiet singleton numbers, independent overlays, row-local visual numbering, correct OC/resume labels, separate music M namespace. No production schema/runtime qualification. Accepted-source HTML hash in the handoff: `632cfce2b9fea8832b7c13387811d5739518f1247d10bb81ae605671b2005535`. No new HTML created. |
| D24 | Accepted issue #24 revision `e72aa2436fa49d6b256b7cf811d5c1dea39120c3`; baseline `docs/investigations/issue-24-representative-script-coverage.md` | Read coverage, D24 decision table, follow-up ownership, and anchor invariants. Relevant Q1 rules: taxonomy, Unplaced/two-of-three, identity versus locator, evidence versus picture. Later variants, proposals, capture/motion/composites/highlights remain separately owned. |
| Product specification | Baseline `docs/Script-to-Timeline Product Spec - Fable Rev2.md`, especially §§6.1–6.4, 7, 8.1–8.4, 9.1–9.6, 13 | Original independent lanes and v1 boundaries, source ownership, preparation/materialization, import-without-transcode, canonical manifest, new-timeline safety and failure policy. |
| Historical acceptance | Baseline `docs/IMPLEMENTATION_PROGRESS.md` | Read historical acceptance/frozen boundaries. It is not the live tracker. |
| Current owners | Live issue bodies #145, #157, #160, inspected 2026-10-08 | #145 qualifies v1/25-fps only; #157 consumes the selected adapter; #160 owns actual suite QA and mixed-rate positives. #81/#82 retain Research resolution/copy and #85 local import. |
| Current compiler | `packages/contracts/src/compiler-core.ts` at baseline | Read public exports, preconditions, block scheduling, anchor resolution, presenter/visual compilation, source/audio ranges and rational helpers. Ready mismatched-rate video is rejected at `compileVisual`; source duration is currently reused as record duration. |
| Current contracts/tooling | Four v1 schemas; `packages/contracts/scripts/generate-contracts.mjs`; `packages/contracts/package.json` | Read root/definition inventories, generator and exports. TypeScript uses one aggregate file; Python generates per-schema modules. Four v2 schemas plus #55's ancillary settings contract require explicit registry/type decisions. |
| Narration/caller inventory | `packages/contracts/src`, `packages/contracts/test`, narration Python modules, `roundtrip*` modules | Searched compiler/validator callers and source-map surfaces. #144 callers explicitly consume v1. Existing provider source mapping translates byte ranges to UTF-16; narration adapter maps validated marks into compiler dependencies. Detailed v2 bridge inventory remains unfinished. |
| Research machinery | Published pin `0499666c59167cef9dcd2665845f7ef6090e64df`, `packages/export-settings/src/index.ts`; completed M5-03 and M5-08 specs | Source-rate export default confirmed; existing injectable FFmpeg/FFprobe adapter, private staging, verification and lifecycle patterns exist. Their older loose export-duration tolerance is not authoring sync qualification. Exact current media adapter API/code remains to inspect. |
| FFmpeg primary documentation | [Filters](https://ffmpeg.org/ffmpeg-filters.html#fps), [CLI](https://ffmpeg.org/ffmpeg.html), accessed 2026-10-08 | Output sampling and timestamp handling are distinct from input-rate metadata coercion. This supplies implementation facts, not VERA or Studio acceptance. |

## Confirmed design reconciliations to carry forward

1. **Four v2 contracts:** `script-document-v2.schema.json`,
   `compiler-dependencies-v2.schema.json`, `timeline-manifest-v2.schema.json`,
   `build-report-v2.schema.json`. #55 also names
   `authoring-project-settings-v1.schema.json`. No file has been created.
2. #55 proposes additive v1 defaults and independent authored host spans.
   Accepted #56 explicitly replaces full-frame timing and authored host spans
   with one v2 primary sequence and derived host visibility. Carry #55's
   defaults/state semantics into that v2 authority; write the exact separately
   approved reconciliation/change note before any schema implementation.
3. #127 visual numbering includes independent overlays in start-anchor order,
   with the base before a coincident overlay. #56's structural content-slot
   ordinals alone cannot satisfy that rule. Keep machine slot/payload identity
   separate from derived human row/ordinal references; finish the reconciliation
   explicitly rather than persisting a second timing model.
4. D24's general Unplaced and two-of-three timing must not create a second
   authority for primary structural boundaries. Distinguish unattached items,
   structural primary picture, independent overlay timing and visual-only
   block timing. Finish exact schema/UI/refusal rules in the plan.
5. Preserve all frozen v1 bytes and #144 proof inputs. New v2/24000/1001 goldens
   demonstrate compiler determinism only. Actual Studio save/reopen/render,
   source/audio verification and fresh-target recovery need separate evidence.
   #145 evidence never automatically qualifies v2 or 23.976.

## Mixed-rate path under evaluation — not a final decision

The leading proposal is verified immutable **build-time derived normalization**
for ordinary supported CFR media. It avoids making authors preconvert clips and
keeps delivered placement at one verified timeline rate. Native mixed-rate
placement has not been qualified and cannot be assumed correct from API
presence. No normalization, native placement or media experiment has run.

Before selecting the path, inspect and reuse existing Research media-tool
machinery and STT verification/cache/materialization patterns. Do not add a
second generic transcoding engine or mutate Research canonical packages.
Same-rate media should bypass unnecessary re-encoding. #85 import still only
inspects/verifies; normalization belongs to an explicitly audited build stage.

The plan must pin rational source/record mapping for 25 and 30 fps into
24000/1001, fractional and same-rate cases, normal-speed duration/audio sync,
rounding and handle bounds, source trim and word associations, source/derived
identity and cache/profile/provenance keys, build binding, disk/cancel/retry/
cleanup recovery, and actionable VFR/unsupported refusal. Requested encoder
settings or relabeled metadata cannot substitute for actual output verification.

#56 forbids editorial holds, frame repeats and retiming as shortage remedies.
If ordinary CFR resampling needs dropped/duplicated samples or bounded endpoint
quantization, state the narrow distinction and approval boundary explicitly;
do not silently treat #56 as authorization for that behavior. This checkpoint
does not accept a new conversion policy.

## Remaining work at resume

1. Reinspect live #156 ownership/dependencies and the dedicated branch before
   further work; continue this claim only if still valid. Do not re-dispatch.
2. Complete precise current interface/caller inventory: schemas/types,
   narration token/source maps, compiler outputs, package/OTIO/Studio consumers,
   Research media-tool APIs and build-stage receipts.
3. Draft the actual realization plan with closed entity/field ownership,
   precedence reconciliations, migration report/activation/cancellation/rollback,
   v1 compatibility lifetime and fail-closed version dispatch.
4. Select/justify the mixed-rate path and its exact arithmetic/profile/test
   matrix. Scope any necessary adapter package once; do not create/dispatch it.
5. Name finite sized dependency-root implementation packages, their exact
   interfaces, success/refusal/recovery, deterministic fixtures/goldens and
   real-application gates. Preserve existing UI, #157 and #160 ownership and
   keep later presenter/music/transition/inbound/capture scope out of Q1.
6. Retain design reference/interface checks, relevant repository verification,
   artifact identity and forecast. Move to In review only when the plan is
   complete, with a short numbered Producer checklist and exact acceptance
   response. Producer acceptance is required for closure.

## Verification and forecast

No product/contract/fixture/generated/accepted-test file changed. No external
product operation ran. Full `npm run validate` has **not run**: the current
shell reports Node `v26.5.0`; this worktree has neither `node_modules` nor
`.venv`, while the repo requires Node 24.19.x/npm 11.17.0. No toolchain or
dependency installation was attempted. Pin or locate the supported runtime
before the eventual required gate; do not call a wrong-runtime pass equivalent.

The initial forecast after the first substantive source/compiler comparison
was **2–4 remaining active hours**, medium confidence. Main uncertainty:
mixed-rate adapter/interface and acceptance detail. This was an inspection
estimate, not a completion promise. Reassess after completing that inventory.
The Producer-requested checkpoint wait, Producer approval, and future Studio
qualification are excluded from active effort. No 24-hour policy applies.

At this checkpoint, the proposed model and package boundaries are unfinished.
Resuming must not mistake this record for a Producer-approved contract or a
delivered runtime capability.
