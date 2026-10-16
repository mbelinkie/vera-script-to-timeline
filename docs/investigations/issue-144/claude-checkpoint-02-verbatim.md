# Issue #144 checkpoint 2: review of the compiler entry and the rewritten plan

The compiler entry at `fd41725` is correct and does reuse the unchanged compiler; nothing in it blocks the next segment. The fixes worth making are about what its receipt claims and how failures are reported.

The rewritten plan is close. Two gaps should be settled before the narration and build stages are wired: a readiness deadlock between #148 and #145, and missing adapters for two #35 stages that every job runs.

**How I checked:** read-only repository reads at `fd41725` and `9c8973d`, plus local runs in a scratch export of the commit.

**Runtime caveat:** nodejs.org is blocked from my sandbox, so I ran Node v24.19.0 from the npm `node-linux-x64` repackaging after a locked `npm ci`. Everything I ran is reviewer evidence only, not calibration and not acceptance.

## What I reproduced

- **Your tests:** 8 of 8 pass.
- **Torture fixture through the entry:** the manifest and report strings are byte-identical to the frozen goldens; your tests only cover the minimal fixture.
- **Unusual paths:** the module hook resolves correctly from a checkout path containing spaces and non-ASCII characters, and from a symlinked checkout.
- **Wrong runtime:** on Node 22.22 the entry refuses with exit 69.
- **Inputs:** the input files are unchanged after each run.

## Compiler entry: `packages/contracts/src/issue-144-compile-cli.ts`

**1. The receipt's `codeHashes` don't cover the code that actually validates. Medium.**
- **Missing:** the compiler and validator run `ajv` and `ajv-formats` from `node_modules` (`compiler-core.ts:3-4`, `script-validator.ts:10-15`), and neither is hashed.
- **Doesn't belong under that name:**
  - `generated/contracts.ts` is imported for types only, so Node strips it and never runs it.
  - `package-lock.json` is a lockfile, not code.
- **Failure:** if `node_modules/ajv` changes after install, validation behaviour can change while the receipt stays identical.
- **Fix:** rename the field to something like `sourceHashes`. Report the lockfile hash separately, and state that installed packages are bound only through the lockfile and `npm ci`. Optionally hash the two resolved entry files.

**2. Exit code 1 means two different things. Medium.**
- **Where:** `INPUT_CHANGED` at lines 75-76 and a normal compiler refusal at line 89 both exit 1.
- **Related:** a Node too old for type stripping or `registerHooks` also exits 1, with a SyntaxError, before the friendly runtime check can run.
- **Failure:** a stage adapter could record a race or a runtime fault as a deterministic compiler refusal.
- **Fix:** give `INPUT_CHANGED` its own code (for example 75) and add a test for it. Have the host check `node --version` before invoking the entry.

**3. Non-canonical input bytes are accepted. Low-medium; not a regression.**
- **Probe result:** an input with a duplicate key compiles successfully (the last value wins), and so does one with a UTF-8 byte-order mark.
- **Divergence:** Python's `json.loads` rejects that byte-order mark, so the Python host and the entry can disagree about the same file. The accepted validator CLI parses the same permissive way, so this is consistent with existing behaviour.
- **Fix:** require canonical bytes for every file #144 itself produces (revisions, spliced dependencies), the same rule the package writer applies with `_require_canonical`. Refuse a byte-order mark and duplicate keys in operator-supplied inputs.

**4. Small simplifications and additions. Low.**
- **Redundant re-read:** re-reading the inputs after compiling adds little, because the output is built from the bytes already in memory. The code re-hash only catches a change that persists; it misses a change that is reverted between hashing and import. Keep it with that limit documented, or drop it.
- **Output hashes:** add `outputs.manifestSha256` and `outputs.reportSha256` so #35 receipts can bind the output bytes without re-deriving them.
- **Missing tests:**
  - the torture fixture run through the entry;
  - the `INPUT_CHANGED` path;
  - the policy on non-canonical input.

## Plan: `docs/plans/issue-144-roundtrip-harness.md` at `fd41725`

**A. Readiness can deadlock between #148 and #145 (lines 166-169). High; Producer or scope decision.**
- **What the plan asks:** #148 is to supply qualifying anchors, phrase and neighbour supports, and compiler dependencies.
- **Why that may be impossible:**
  - Anchor timing and word supports both need narration audio.
  - #148 excludes any paid or cloud service, so it can only supply narration that already exists locally.
  - Only #145 may choose a synthesis route, and #145 is blocked by #148.
- **Scope doubt:** measuring audio supports may also fall outside #148's "authoring/preparation only" scope.
- **Fix:** if narration doesn't already exist, #148 hands off with those narration-dependent checks marked pending. #145 runs them as a gate after choosing its narration route and before any native action.
- **No cycle for #144:** its tests only need public inputs — the published W1 kit and the `slice_1_x` fixtures.

**B. #35 always runs `generating_speech` and `resolving_media`, and the plan maps neither. High; bounded implementation.**
- **Evidence:** `build_jobs.py:289-300` requests every core stage for every job. Line 56 only rules out render and upload.
- **Failure:** wiring `NarrationService` into `generating_speech` would reach Polly.
- **Fix:** `generating_speech` should only verify the prepared or spliced narration dependency and its bytes. It must never construct a provider. Test that it refuses missing assets and never imports `polly` or `boto3`.

**C. Composition through hand-written ripple arithmetic (lines 191-195). Medium-high; simplification.**
- **Proposal:** check equivalence by compiling instead. Compile the candidate revision with its spliced narration dependency, then require exact equality with the raw edited geometry.
  - A ripple edit matches automatically, because the splice removes exactly the same interval.
  - The ±25-frame move and trim deltas get checked in the same compile.
  - A lift that leaves a gap, a spanning item, or a non-uniform shift fails equality and refuses.
- **Effect:** this replaces separate shift-detection logic with one compiler-backed comparison.

**D. "Gain per route using retained calibration" (lines 120-123). Medium.**
- **Why:** my offline fit found different gains by topology: embedded A1 ≈1.000, WAV A2/A3 ≈0.708. That is reviewer evidence only.
- **Freeze:**
  - the reconstruction method;
  - the window length;
  - the residual threshold;
  - the PCM render requirement.
- **Estimate per case:** each route's gain, within a fixed plausible range; refuse anything outside it.
- **Label:** W1's word supports are declared by the fixture generator (`media/manifest.json`). Label them that way rather than "independently measured".
- **Feasibility:** the gate can run on the standard library plus the `ffmpeg` the accepted normalizer already uses. numpy isn't locked.

**E. The test list doesn't name the new seams' tests (lines 199-206). Medium.** Add named tests for each:
- **Reconstruction gate:**
  - synthetic partial-head and partial-tail residue;
  - an unattributed extra route;
  - a gain outside range;
  - an incomplete render extent;
  - a snapshot fingerprint that doesn't match.
- **Splice:**
  - a cut not aligned to a frame;
  - an audible join;
  - exact `timeMs` shifts;
  - sentence marks dropped;
  - UTF-16 offsets around surrogate pairs.
- **Wording rule:** punctuation in a joining gap; deleting a first or last token; an anchor endpoint on a removed token.
- **Link sidecar:** an extra link; a non-reciprocal link; unequal ranges.
- **Speech stage:** `generating_speech` never synthesizes.

**F. Wording-rule precision (lines 148-158). Low-medium.**
- **Redundant rule:** tokens exclude punctuation (verified: `"Hello world."` tokenizes to `Hello`, `world`). A sentence boundary therefore always puts punctuation in a joining gap, which the gap rule already refuses. Define "sentence start" as covered by that rule rather than as a second test.
- **Whitespace:** define the allowed whitespace set exactly, for example ASCII space, tab, LF and CR. JavaScript `\s` and Python `isspace` disagree on several characters.

**G. `liveContentHash` (line 62). Low-medium.**
- **Single serializer:** compute it only in the TypeScript entry, or add a byte-identity test between the Python and TypeScript canonical JSON on the torture document.
- **Scope:** apply it only to revisions #144 produces. Documents from #148 can't be checked against this rule, so don't refuse them on it.

**H. Recovering after a lost response (lines 182-186). Low.**
- **Name lookup is narrow:** project lookup uses the current folder only (`studio_spike.py:540-544`), and the project UID first becomes known at the first WI capture.
- **Persist intent:** write it before calling `run_studio_assembly`, through the `adapter_factory` wrapper.
- **Rehydration:** require exactly one matching project anywhere in the project tree, or operator confirmation.

## What can start now, and what must wait

**Can start now:**
- the host proof skeleton and job adapters, against fakes, including the verify-only speech stage;
- the wording rule and splice, on synthetic WAVs;
- the reconstruction gate as a repository test on the retained W1 data;
- the link and render sidecar schemas, against fakes;
- the compile-to-observed composition check.

**Must wait:**
- **Omission rebuild positive:** until the Producer decides the narration route and wording rule.
- **Real anchor and support preflights:** until finding A is resolved.
- **Native acceptance:** remains #145's.
