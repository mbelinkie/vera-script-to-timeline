# Checkpoint 3 review — issue-144 compiler corrections and next bounded seams

Read-only review complete. Findings below map to the five numbered questions in `checkpoint-03-cli-review-prompt.md`, with severity, file location, and smallest correction. I did not run any code, Resolve action, or test suite — findings are from static reading only.

## 1. Compiler receipt/failure corrections — closed, with one documentation gap

Verified directly in `packages/contracts/src/issue-144-compile-cli.ts` and `test/issue-144-compile-cli.test.ts`:
- `sourceHashes`/separate `lockfileSha256` (cli.ts:20-24, 87-89), output byte hashes (cli.ts:95-98), exit 75 on persistent drift distinct from exit 1 refusal (cli.ts:75-81, 103), BOM rejection via `TextDecoder({fatal:true, ignoreBOM:true})` (cli.ts:48) — all present and each has a passing test (lines 87-113 of the test file).
- The four hashed schema files (cli.ts:10-18) resolve to the exact same relative paths `compiler-core.ts` and `script-validator.ts` import with `with {type:"json"}` — no unhashed schema can silently drift. This closes a coverage question I checked but wasn't explicitly asked about.
- 11 test cases counted directly in the test file, matching the claimed 11 new / 73 total.

**This genuinely closes the checkpoint-02 receipt/failure concerns.** No custom JS parser is needed, and none should be added — not even for the host side:
- Duplicate-key rejection: Python's `json.loads(text, object_pairs_hook=...)` gets every (key, value) pair for each object from the stdlib's own tokenizer before collapsing duplicates; raising inside that hook when a key repeats requires zero custom parsing.
- Non-finite numbers: a numeral like `1e400` parses to `inf` via ordinary float conversion (not the `Infinity` literal), so it also needs a post-parse recursive `math.isfinite` walk over the result — again pure stdlib, no tokenizer.

**Finding (Low, documentation):** `docs/plans/issue-144-roundtrip-harness.md:79-80` states the host "rejects duplicate keys and non-finite numbers" but never names a mechanism. Without this, a future implementer could reach for a bespoke JS/Python tokenizer. Smallest correction: add one sentence naming `object_pairs_hook` + recursive `isfinite` walk as the required stdlib mechanism, closing off the custom-parser path explicitly.

## 2. Next bounded host stage — maps safely, no blocker found

Cross-checked against `python/vera_timeline_agent/build_jobs.py` and `studio_assembly.py`:
- `CORE_STAGES` (build_jobs.py:24-30) names match the plan's five stages exactly; `StageAdapter` is a generic `reconcile`/`execute` Protocol (build_jobs.py:118-123), so issue-owned verify-only speech/media adapters are structurally pluggable without touching accepted code.
- `BuildJobStore._output_path` enforces exactly one immutable regular file per stage (build_jobs.py:343-344, 369-372). The compiler CLI's single combined stdout envelope (manifest + report + hashes in one JSON object) is already shaped to satisfy this one-file-per-stage constraint for the `compiling` stage — no adapter-side repackaging logic is needed beyond writing that envelope to `context.output_path`.
- `writing_interchange` → `build_resolve_import_package`, `verifying_import_package` → `verify_resolve_import_package` both exist with matching names (`python/vera_timeline_agent/resolve_import_package/__init__.py:3-14`).
- Studio boundary injection is a real, already-tested pattern: `run_studio_assembly(..., adapter_factory=...)` (studio_assembly.py:89-131) is exactly how `tests/test_studio_assembly.py` injects fakes today (e.g. `adapter_factory=lambda _: adapter`). `run_studio_assembly` itself calls `verify_resolve_import_package` before touching any adapter (studio_assembly.py:102), so no live Resolve import happens unless a verified package already exists.
- `render=False, delivery=False` with `mode="studio"` correctly runs stages 0–6 (`generating_speech` through `verifying_timeline`) and skips `rendering_mp4`/`verifying_mp4`/`uploading` (build_jobs.py:289-300) — confirms the plan's "render/delivery false; Studio boundary still exercised" claim without code changes.
- The plan's "lost creation response" recovery design is consistent with the actual API: `check_project_name_available` genuinely only searches `GetProjectListInCurrentFolder()` (`studio_spike.py:540-544`), confirming the plan's claim that this is folder-scoped, not tree-wide. A project-tree walk for recovery is feasible without new APIs since `GetSubFolderList`/`GetClipList` are already verified callable in the existing preflight (`studio_spike.py:527-529`), but **this walk does not exist yet** — it's new code, not a gap in the plan's reasoning.

**No plan blocker for this segment.** The verify-only speech/media adapters and the project-tree recovery walk are simply not implemented yet (expected — plan says "Tests/implementations remain outstanding except compiler tests").

## 3. Audio gate proposal — calibration gap, not an implementation bug

From `retained-w1-reconstruction-measurements.json`: supported residuals are 0.0038–0.0042 (max-window) and 0.00020–0.00022 (whole); the proposed thresholds (0.006, 0.0004) sit ~40% above the worst supported case and comfortably below both disqualifying cases (whole-route-missing 0.2590, synthetic opposite-channel overlay 0.2334). The math itself checks out: `oppositeChannelOverlayCancelsWhenAveraged: true` empirically confirms the documented reason both channels are required, and gains (0.99999/0.70794/0.70787) sit inside the proposed `[0.69, 1.01]` freeze with real but thin margin (~1–1.5%).

**Finding (Medium, calibration limitation — not a bug):** every tested case is either comfortably under threshold (full word removed, two supported cases) or wildly over it (whole route gone, full-word synthetic overlay). There is no case near the 0.006/0.0004 boundary — e.g. a short/quiet word, a quarter-word partial excision, or a low-energy phrase — so the discriminative margin is unverified anywhere except at the extremes. `measure-retained-w1.py` also doesn't yet implement the "partial-head/tail" test the proposal itself says "must fail" (`checkpoint-03-cli-review-prompt.md:53`); it's only promised, matching the plan's own "Named new seam checks" list (`issue-144-roundtrip-harness.md:244`) as outstanding. This is explicitly a calibration-coverage gap (untested boundary), not an implementation defect — the windowing/fitting code is correct and the plan already self-limits scope ("not a speech classifier," "do not generalize... to arbitrary speech/private input").

**Smallest bounded correction:** before freezing the profile, add one more controlled synthetic case near the boundary (e.g., a short word or a partial/quarter-word residue on the same W1 fixture) to confirm the 0.006/0.0004 thresholds actually discriminate near the edge, not just at the extremes. This can be added to `measure-retained-w1.py` without any new native action or fixture change.

## 4. Composition/narration qualification — sound minimal seam, no hidden substitute found

The plan's design (`issue-144-roundtrip-harness.md:222-231`) is: use the actual compiled candidate as geometry authority; compare all retained **non-narration** occurrences by strict identity (unchanged); for narration specifically — the one entity whose UID/asset ID must legitimately change — substitute an explicit, hash-bound splice segment map plus full-program-mix audio evidence instead of UID equality. This is the correct minimal substitution: it only relaxes the check for the one attribute that structurally cannot survive unchanged, while keeping strict identity checks everywhere else, and it still requires full-extent program evidence (not a sampled subset) per the plan's existing "exact output extent"/"full phrase excision" requirements. I did not find a hidden lower-coverage substitute. This is unimplemented but not blocked — the design simply hasn't been built yet.

## 5. Future input readiness — no invented authorization found

The plan (`issue-144-roundtrip-harness.md:183-197`) already splits narration-independent preflight from narration-dependent checks, explicitly forbids #148 from synthesizing audio to satisfy anchor/support checks, and names missing original narration as a standing Producer/steward blocker rather than silently passing it. This matches checkpoint-02's disposition and introduces no new authorization. Confirmed clean.

## What can proceed now vs. must wait

- **Can proceed:** implementing the next host stage (immutable snapshot, Node preflight, verify-only speech/media adapters, wiring the actual compiler/package writer/verifier, injected Studio-boundary tests) — the API mapping checks out against accepted code with no blocker.
- **Must wait:** freezing the audio gate thresholds until a near-boundary synthetic case is added; any omission-rebuild positive (already stated as pending the Producer's wording/route decision); anything requiring #148/#145 (real narration, actual native run).

## Could not verify

- Could not run `npm run validate`, the vitest suite, or pytest — all test-pass counts (73, 17, 62) are taken from the documents/code as read, not independently executed.
- Did not inspect `script-validator.ts`'s `NARRATION_TEXT_HASH_MISMATCH` diagnostic implementation in detail; relied on the passing test asserting it.
- Did not review `python/vera_timeline_agent/narration/service.py` or `polly.py` beyond confirming their existence, since the plan explicitly excludes them from this segment.

This is an independent review only, not Producer acceptance.
