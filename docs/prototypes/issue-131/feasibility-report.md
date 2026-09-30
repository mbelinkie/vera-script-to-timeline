# #131 — reconciliation feasibility evidence

September 30, 2026. Investigation only; awaiting Producer acceptance.

## Result

**Conditionally representable; production feasibility is not established.**
Stable token identities, many-to-many row lineage, linked appearances, dormant
and preserved items, common-ancestor conflicts, and deferred decisions can be
represented without overwriting either source. The disposable experiments
demonstrate that narrow claim. Current v1 contracts cannot express several of
those states, and existing Resolve evidence does not establish occurrence
identity or exact program-audio/visibility observations after editorial edits.
Do not promote implementation on the strength of these experiments.

This is a useful negative gate, not a finding that reconciliation is impossible.
Keep undecidable work visible and blocked; preserve both sources. #139 must
settle the constraints below before final paired acceptance. S03 alignment
follows that review. This branch changes no product behavior or design artifact.

## Reproduce and interpret the evidence

From the repository root, with Node 24.19.0, npm 11.17.0 and the existing locked
dependencies:

```sh
node docs/prototypes/issue-131/check.mjs
npm exec -- vitest run docs/prototypes/issue-131/contracts.test.ts packages/contracts/test/compiler-core.test.ts packages/contracts/test/script-validator.test.ts
uv run --frozen pytest tests/test_studio_spike.py tests/test_otio_package.py
npm run validate
git diff --check
```

Use the repository's shell wrappers when running these commands. This machine
defaulted to Node 26.5.0, outside the declared engine range. Checks ran through
`npm exec --yes --package=node@24.19.0 -- <command>`. Bootstrap was locked
`npm ci --ignore-scripts` and `uv sync --frozen`; no dependency/lock changes.

- `synthetic.json` is invented, frozen investigation input, **not** a v1
  ScriptDocument, captured Resolve snapshot, accepted design fixture, or
  proposed public schema. Its repeated words and locators are intentional.
- `check.mjs` runs 12 stdlib-only representation experiments P01–P12. It reads
  inputs, constructs disposable values, checks failure classifications and
  source-byte immutability, and writes nothing. It is not a general reconciler.
- `contracts.test.ts` calls the actual validator/compiler on copies of accepted
  minimal input. Ten checks establish real v1 acceptance/rejection boundaries.
  In particular, a valid formatting split retains token IDs but cannot compile
  with its original narration dependencies. A cross-row endpoint is rejected
  even when the token exists elsewhere. Failed compilation returns diagnostics,
  not a partially usable manifest; inputs remain unchanged.
- Existing compiler tests prove frozen minimal/torture golden bytes and input
  immutability. Studio/OTIO tests exercise injected adapters and packaging,
  **not a live Resolve connection**.

The experiments assume already trustworthy identities, word/sample intervals,
coverage flags and section boundaries where explicitly supplied. They do not
prove how to obtain those facts, inspect effects, classify arbitrary edits,
persist to a database, handle concurrent writes, or execute a real update.
Serialized JSON reopening is representation evidence, not crash-recovery proof.

## Immutable authority and concurrent input

Product authority: `docs/Script-to-Timeline Product Spec - Fable Rev2.md`,
particularly §§6.13, 6.15–6.16, 7, 8.1–8.2 and 13. Baseline of this branch:
`c9a047feee8adc1ab28e9fc5c6481f1374366ebe`.

Accepted #123 is **not contained in that baseline**. Its accepted handoff,
annotation guide and r2 export were read from Git object
`70dfcf265bc17028875e05e0e9b7e7a2d0362f7d`; no historical local draft was
mistaken for the accepted compact 22-change authority. Acceptance was recorded
September 27. The artifact simulates detection/execution; its text/color
substitution heuristics are not production mapping evidence.

| Input | State used | SHA-256 |
|---|---|---|
| #123 `Compact Mixed-Change Reconciliation Pilot - issue 123 export r2.dc.html` | Accepted; Git object above; 6,546,977 bytes | `b4fae31553a72925315c213260e515f32bc97b289d244905daf815402289fa03` |
| #136/#128 `paired-123-s05-scenario-corpus-recommendation.md` | Accepted paired planning, checkpoint `db16cec` | `aa97fddbe25cb0870032c408c26d5634562bab7ed25030eb4c0070841d639344` |
| #136/#128 `paired-123-s05-scenario-content-spec.md` | Accepted paired planning; #136 accepted at `cf72d58` | `f355a8e9ee08326c09a78c929b848ea4c9681e2a86889bc1eac4b5c80016a6c0` |
| #135 `S03 v3 authoring artifact - issue 135 export v2.dc.html` | Accepted; 3,943,452 bytes | `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea` |
| #140 `S03 v3 authoring artifact - issue 140 connector lanes.dc.html` | Accepted corrected lanes; 3,505,885 bytes | `08aca68edc5f1de6cbf180b2104a611d67561088fc3240972cd6e1f4108e7c0d` |
| #137 `plan.md` | Concurrent, read-only, unaccepted | `52ae2c3af53a40d73be382121039b255ce1d0db63381c3b6566588d872e01872` |
| #137 `Shared S03 Review Foundation - issue 137.dc.html` | Available local source, unaccepted; 3,567,653 bytes | `ba9450014ae0befc9c315aecb4ad710f73df8b1ea2d3b76e53ed42ab82e2a2e8` |
| `S03 Review rules - for second opinion.md` | Earlier private discussion snapshot; superseded | `d49c79cd3366236d4d28fd34882d92f2f84a4c0be03e07fda83c85a8b8091f7f` |
| `S03 Review correction pass - change log.md` | Earlier private discussion snapshot; superseded | `ca7aef11a8ac1f97cf368e71ca6aba34480666746335028e351ecd6237208d7e` |
| `S03 Review rules - for second opinion (1).md` | Current reported rules, Revision 3, September 30; describes r6 | `a2f982381340e6a6c5eaf61736de52e3e8cef3f6e85957cf9e46be1ffc6f2869` |
| `S03 Review correction pass - change log (1).md` | Current reported r6 corrections, unaccepted | `b0ef5cf6bf801a7f476209d60a7dfe6925446ea56d000ddb49814aeb8ad53cd7` |

Private locations/discussion are deliberately omitted. The current local
source cannot be equated with the reported r6 artifact: a corresponding r6
source/export was not available. Reported self-tests are therefore not
independently verified artifact evidence. #137 is not a dependency of #131.
Live GitHub acceptance, not stale “awaiting acceptance” handoff prose, controls
#136 and #140's state. Available snapshot hashes were rechecked unchanged.

Sanitized distinction for #139:

- **Reported Producer decisions in the current #137 evidence:** one inbound
  decision per group; comparison to a common baseline; inbound review before
  outbound when Resolve has unreviewed/new changes; retained deferred work;
  I01 remains blocked; I06 becomes shared C18 without shortening its 6.4s
  source edit; generated VO additions obtain audio during update.
- **Authority conflict requiring final review:** accepted #123 change 10 and
  paired C07 have independent inbound axes; #137 now reports one group
  decision. P09 demonstrates the newer representation, not its acceptance or
  amendment of the older design.
- **Reported scenario retirements:** I04/I05/O04/O06 stop being standalone
  successor examples; historical IDs keep their gaps. Their preservation,
  anchor-rewrite and split-safety obligations remain.
- **Still provisional:** r6 artifact conformance, some Graphic inspection
  treatment and colorblind presentation details. No technical result here
  validates a renderer or resolves those choices.

## Supported / unsupported / ambiguous matrix

Statuses apply separately to each column, not to the entire feature:
**S** = supported for the bounded claim by retained evidence;
**U** = unsupported by the present model or unsafe inference, so refuse it;
**A** = ambiguous until the named evidence exists. “S sidecar” only means the
invented representation works. Every Real Resolve A is an integration gate.

| Behavior and affected paired cases | Disposable representation | Current contracts / tested bridge | Real Resolve gap and fail-closed result |
|---|---|---|---|
| Stable rows/tokens, unique anchors, endpoint changes; C03a/b, C06, C07, O04a/b, O06 | **S** P01/P02; repeated word identity survives reordering. Missing/duplicate IDs refuse. | **S** validator: stable IDs, token offsets/affinities; **U** automatic cross-row remap. Actual tests reject duplicate IDs and cross-row endpoint. | **A R1/R3**: stable observation-to-authoring binding after edits. No quote/filename/order-only match; keep sources and mark ambiguous. |
| Same-slot replacement/fulfillment and assignment swap; C08, C13, I03 | **S** P10/P11: slot, asset, row and occurrence are distinct. | **S** current event/source/provenance distinctions for authored output; **U** reliable edited-timeline occurrence binding. | **A R1/R4**: byte/source identity versus slot after replace/relink. Do not claim an unchanged asset from unchanged anchors/filename. |
| Row merge/split retaining words, visuals and existing cut; C12, O06 | **S** P02: old rows map many-to-many; token sequence and separate audio edit retained. | **U** durable lineage and spanning event relation in v1. Ten boundary checks show a valid split still requires new row/text-bound dependencies; compiler goldens remain unchanged. | **A R1/R2/R3**: actual segments/cut identity. Never regenerate or concatenate narration merely because rows regroup. Inbound split is excluded by accepted paired planning. |
| Linked/interrupted/resumed appearances and overlays; C09, C10, I01 | **S** P03: one logical item, multiple occurrences and truthful visible intervals, no filled interruption. | **U** general logical-item→many-occurrence registry; manifest provenance identifies one block/authoring ID, not arbitrary edit lineage. | **A R1/R3**: duplicates/razors and actual visible base with overlays. I01 adoption **U**, stays Blocked; linked display is only evidence. |
| Verified spoken-word cut, affected endpoint; C02 | **S** P04 for supplied exact, complete program omission; **U** picture-only/subword/other-track inference; **A** derived ends/offline audio. | **U** exact inbound speech-removal proof: current dependencies contain starts with derived ends, not verified edited-program word intervals. | **A R2**: program routes, sample boundaries, source time map and residual speech. Offline picture alone does not block independently proven inbound facts; unverified audio blocks deletion. |
| Camera state/framing and opaque/transparent coverage; C01, C09, C10, C14 | **S** explicit state can be stored; P03/P07 refuse incomplete coverage. No pixel or transform detector is demonstrated. | **S** authored visibility/framing fields; **U** observation-based proof from arbitrary track layout. | **A R3**: program-video/effect visibility and actual Wide/Tight evidence. An enabled clip or upper track is insufficient. Preserve current camera state if ambiguous. |
| Dormant alternatives and removal without loss; C11, I02, I03 | **S** P05: former range/asset survive hide/reveal; no active coverage while dormant. | **U** dedicated dormant registry/restore validation. Extras are not proof of this complete state or edited Resolve mapping. | **A R1/R3/R4**: covered/disabled versus deleted/unavailable. Keep former range as inspectable evidence, not active geometry; restore only with fresh safety checks. |
| Preserved/opaque additions and fixed-source placement; historical I04/I05, I06→reported C18, O09 preservation | **S** P06 fit/review cases keep source start, 160 frames at 25fps (6.4s), linked/opaque evidence; **U** collision/short row; **A** unknown anchor. | **U** independent timeline-bounds visual, preserved opaque registry and non-null timing overrides in current v1. Actual test rejects invented overrides. | **A R1/R3/R4**: bounds/effects/link capture. Keep original untouched on refusal; no duration fitting, invented out-word, dropped effect or flattened manual item. |
| Document-wide bed identity, cross-row/heading anchors, duration end; C15a/b/c, C16 | **S** P12 for independent document item with no out-word; P07 refuses structural cuts through it. | **U** reconciliation representation in the audited v1 authoring range. Existing authored manifest audio ranges do not establish inbound cue identity. Future music work is already #100. | **A R1/R2/R3/R4**: one bed versus fragments, source edit/fade/duration and overlapping program audio. Do not turn a bed into one event per row or invent an endpoint word. |
| Structural razors/heading boundaries; C12, I01, O07a/b/c | **S** P07 only for supplied section + exact A/V/word boundary with no crossing item; **U** arbitrary razor/crossing bed; **A** incomplete evidence. | **U** automatic inbound structural-razor inference. Marker save/reopen checks are not marker survival after editorial changes. | **A R1/R3/R5**: section-marker identity and all crossing media. Inbound section-marker editing remains excluded; outbound explicit authoring intent is not inferred inbound structure. |
| Common ancestor, compatible versus competing anchors; C17a/b, O04b, O08 | **S** P08: independent field changes differ from conflicting endpoint edits; destroyed anchors refuse combination. | **U** durable immutable reconciliation triple/classification contract; tested compiler does not classify editorial conflicts. | **A R1–R4** for observed facts. Compatibility requires valid surviving anchors and dependency validation, not “same/different row.” Do not auto-combine. |
| One group decision, conflict/Defer retention, stale/new sources; C07, C17, I07/I08, O02/O03/O08 | **S** P09 JSON roundtrip, all provenance hashes, stale rejection, deferred resurfacing and pending Keep-Script correction. | **U** review persistence/optimistic-concurrency contract; v1 rejects added decision fields. No database recovery/atomic commit is proved. | **A R1/R5** for a fresh trustworthy observation. Reopen retains unresolved work; changed observation requires inbound review. Keep Script does not modify Resolve or advance the baseline. |
| Missing/offline media and mismatched bytes; C02, C12, C16, I07, O08/O09 | **S** P04/P10: mismatch/offline block affected use only, never erase identity or infer deletion. | **S** verified import/package safety in existing tests; **U** complete edited-program/offline observation semantics. | **A R4**: distinguish unchanged offline item from deletion and wrong relink. An inbound fact may be independently verifiable; affected outbound media use/verification remains blocked. |

All unsupported experiment cases are classifications, not executed changes;
both original snapshots remain byte-identical. This does **not** certify a
production transaction or untouched real timeline: no such transaction ran.

### Accepted #123 traceability

These are mechanism correspondences, not replacement scenario IDs or new
design acceptance. All 22 accepted changes are accounted for:

| #123 changes | Mechanism / matrix row |
|---|---|
| 1, 8, 11, 22 | Framing and endpoint identity (C01/C03 mechanisms); R1/R3 |
| 2, 3, 5, 19 | Visual-only insertion, atomic deletion and row moves; stable IDs plus structural/coverage checks. P01/P02 test identity, not a complete atomic production apply. R1/R3/R5 |
| 4 | Cross-heading linked display, I01 stays blocked; P03/P07 |
| 6, 15, 16, 20 | Opaque cutaway, dormant base, transparent Graphic and return visibility; P03/P05, R3 |
| 7, 13 | Document-wide music identity and fade-only versus duration change. P12 proves identity/end representation, **not** a fade observation; R2/R3 required |
| 9 | Concurrent rewrite/Graphic intent and audio consequences; P08/P09, R2/R3 |
| 10 | Move plus endpoint compound decision; P01/P09; explicit old/new rule conflict for #139 |
| 12, 17, 18 | Replacement, fulfilled request and clip-pairing swap; P10/P11, R1/R4 |
| 14 | Word cut plus affected visual boundary; P04, R2 |
| 21 | Two-row merge beneath a Graphic while retaining words/clips/cut; P02 and actual compiler boundary tests, R1/R2/R3 |

Paired O01 first creation/current-state, O05 narrated additions, O07 marker
authoring and O09 retry are inspected for baseline/identity/preservation
implications only. O10 rendering and the outbound retry/execution lifecycle
are outside this investigation; they receive **no** feasibility certification.
O05's reported generated-VO correction is product evidence, not an audio
generation implementation here.

## Current bridge and required real observations

`python/vera_timeline_agent/studio_spike.py:633` appends events and checks the
returned count; it does not stamp authoring identity on ordinary occurrences.
Verification near line 865 sorts per-track items by record start and compares
duration/source-start/media ID. This works for verified pristine assembly,
not reliable matching after duplicate signatures, razors, moves or overlaps.
Timeline-marker custom data/save-reopen evidence is narrower than item lineage.

The installed vendor `DaVinciResolveScript.pyi` documents item unique IDs,
markers/custom data, source/record bounds, enabled state and Fusion access.
Those signatures are capability hints. No documented stability guarantee was
found for razor, duplicate/copy, relink, reopen or marker survival. No new
Resolve call was made for #131; no installed-version behavior is asserted.

Smallest external follow-up (disposable, approved synthetic project; operator
edits through audited product flows, observer read-only):

| Probe | Required observations and retirement condition |
|---|---|
| R1 occurrence identity | Capture authoring binding, item UID/custom data, source identity, ranges and track before/after save/reopen, trim, move, razor, copy/paste and duplicate timeline. Include identical duplicate signatures. Retire only when each operation has a proved binding rule or an explicit unsupported state; never silently pick a candidate. |
| R2 word/program audio | Known synthetic repeated words with verified sample intervals; linked/unlinked A/V cuts, picture-only trim, partial-word cut, second audible track, disabled/muted item, retime/offset and derived-end precision. Read complete program routing; retain source/time-map and operator/render evidence if public API cannot prove samples. Retire when complete-word removal versus residual/unknown speech is distinguished; otherwise keep word deletion unsupported. |
| R3 visibility/structure | Opaque cutaway and return, transparent/effected overlay, disabled/offline picture, row merge beneath a Graphic, exact section razor and a bed crossing it. Retire when program visibility and all boundary crossings are observed or explicitly unsupported; no track-order heuristic. |
| R4 availability/source | Move a locator, relink verified bytes, supply different bytes at the same locator, and make media offline without deleting its occurrence. Retire when access state, hash identity, disappearance and affected-media blockers are distinct; preserve original item/slot evidence. |
| R5 baseline/review freshness | Observe the same project/timeline before/after reopening and new manual edits, including section markers. Retire when snapshots can be pinned and rechecked consistently or inconsistency fails visibly. Persistence/atomic commit still requires later implementation tests, not this Resolve probe. |

Record exact product/version/build, scripting mode, timeline identity, frame
rate/time base, raw readback and unsupported APIs. A failed probe is valid
evidence when retained and blocking. This issue neither creates that project
nor authorizes external mutation; the Inbox proposal names the later boundary.

## Producer decisions / #139 constraints

1. **Identity gate:** no occurrence matching by position, filename, quote or
   signature alone. Ambiguous/duplicate mappings stay blocked until R1/R4.
2. **Structural/audio gate:** preserve token lineage and existing source audio
   independently. Merges do not authorize narration regeneration. Formatting
   splits need valid new dependencies even with unchanged flattened words.
   Inbound splitting/section-marker edits remain excluded unless separately
   approved. Cross-heading I01 stays blocked, not “fixed” by linked display.
3. **Word-removal gate:** only verified complete program-audio evidence can
   authorize deleting spoken words. Derived ends and frame-only bounds do not
   establish sample-exact omission. Unknown routes/effects/retimes stay blocked.
4. **Preservation gate:** dormant former ranges are evidence, not active
   coverage. Preserved source edits/durations/manual effects are never shortened,
   flattened or deleted to fit a row. The unsafe plan must leave originals intact.
5. **Decision authority:** explicitly settle C07 independent axes versus the
   reported one-group rule, and I06→C18/retirements. The technical proof does not
   silently amend #123/#136. Renderer/Graphic/colorblind choices remain #137/#139.
6. **Freshness gate:** compare baseline/current Script/current Resolve; retain
   decisions and unresolved evidence against all three revisions. New/unreviewed
   Resolve changes route inbound before outbound under the reported current rule.
   Keep Script may retain a pending correction; Defer is not resolution or
   outbound permission. Neither advances the applied baseline by itself.
7. **Contract gate:** approve a separate versioned change before implementation;
   see `proposed-contract-change.md`. Do not relax current validators, replace
   golden files or rewrite accepted artifacts to make the design appear feasible.
8. **Availability gate:** media absence is not a deletion signal. Independently
   verified inbound facts may remain decidable; affected outbound use/verification
   needs verified bytes. Unbounded observation uncertainty blocks the plan.

Accepting this report accepts the investigation and these open gates, **not**
production readiness, a schema amendment, or a new renderer. A Producer may
instead request a narrower supported design before further implementation.

## Check record and follow-up coverage

- Representation proof: **12 passed**, input hash
  `98fede0b93d26d1f19632250208a111671bd3650b7d18b8930fca86262643dbf`.
- Focused actual contracts/compiler/validator: **72 passed** (10 new boundary
  checks and 62 existing checks), including exact minimal/torture compiler goldens.
- Injected Studio/OTIO: **70 passed**, Python 3.12.14, pytest 9.1.1.
- Full `npm run validate`: **passed**; generated types current; TypeScript lint/
  typecheck; 141 contracts + 1 smoke + 6 progress + 23 roadmap tests; Python
  lint/format/typecheck and **175 tests**. Node 24.19.0, npm 11.17.0,
  Vitest 4.1.11, uv 0.12.5.
- Accepted #135/#136/#140 hash checks: **passed** via their retained `check.mjs`
  commands. #123 accepted export hash checked from its Git object.
- New boundary test strict typecheck: `npm exec -- tsc --noEmit --strict --target
  ES2023 --module ESNext --moduleResolution Bundler --esModuleInterop
  --resolveJsonModule --skipLibCheck --types node
  docs/prototypes/issue-131/contracts.test.ts` **passed**. The first ad-hoc
  invocation lacked Node types/ES2023 libraries; the corrected invocation uses
  the repository's installed types. No dependency was added.
- Optional direct ESLint of the new docs proof could not run: the existing
  typed-lint configuration enables parser services for `packages/**/*.ts`
  and disables typed rules for `scripts/**/*.mjs`, neither covering docs.
  This is not a full-validation failure. `node --check` and execution of the
  proof pass; repository ESLint passes. No lint configuration was broadened.
- Frozen-boundary diff against `c9a047feee8adc1ab28e9fc5c6481f1374366ebe`:
  **passed**, exactly eight investigation-only paths; no change outside
  `docs/plans/issue-131-reconciliation-feasibility.md` and
  `docs/prototypes/issue-131/`. Contracts, fixtures, goldens, generated types,
  accepted tests/design artifacts and locks are unchanged. `git diff --check`
  and `git diff --cached --check`: **passed**.
- Initial proof correctly failed on absent input. Initial split experiment
  failed `VOICEOVER_VISUAL_GAP` because its test copy removed visual coverage;
  the final copy retains explicit per-row placeholders. Neither failure was
  “fixed” by changing production validation or accepted input.
- Locked installation reported three pre-existing high-severity dependency
  advisories (`brace-expansion` 5.0.9, `fast-uri` 3.1.6, `js-yaml` 4.3.1).
  Read-only `npm audit --json` exited 1; no automatic fix. This is separate from
  validation and reconciliation feasibility, tracked in Inbox
  [#142](https://github.com/mbelinkie/vera-script-to-timeline/issues/142).

Semantic duplicate search covered open and closed issues. Existing #101 owns
production baseline/observation capture, #102 three-way classification, #103
review UI/persistence refinement, #104 selective regeneration, and #100 music.
#110's accepted Fairlight capability probe does not establish word-cut or
occurrence-survival evidence. None is a duplicate of the bounded preproduction
R1–R5 observation experiment. Created Inbox
[#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141),
Sol/xhigh, External, explicitly blocked by #131. Created separate Inbox #142,
Terra/high, Automated, with no dependency. Their body proposals are retained
beside this report. No task was dispatched and no other chat was messaged.
No issue is closed here.

## Producer acceptance checklist

1. Open this report's **Result**, then the matrix. Expected: every named #131
   behavior has a bounded status, check or specific missing observation. Decide
   whether any claim overstates the proof or a gate should narrow the design.
2. Open `check.mjs`, `synthetic.json`, and `contracts.test.ts` beside the
   reproduction/check record. Expected: invented evidence is clearly separated
   from actual v1 checks and real Resolve evidence; sources are never written.
   Deterministic checks already passed; no manual rerun is required for approval.
3. Read **Producer decisions / #139 constraints**, especially C07 and I01.
   Expected: accepted design remains immutable; unresolved old/new authority
   and missing real observations stay explicit for final acceptance.
4. Open `proposed-contract-change.md`. Expected: impacts, compatibility,
   migration, generated types and acceptance changes are complete proposals
   only. No frozen contract/fixture/type has changed on this branch.
5. Review R1–R5 and the retained follow-up proposals. Expected: only disposable
   approved evidence work is proposed, never real-project mutation or dispatch.
6. Respond **`Issue #131 feasibility report accepted.`** or name the first
   incorrect status, missing evidence or constraint requiring correction.

#131 remains open/In review until that explicit Producer acceptance.
