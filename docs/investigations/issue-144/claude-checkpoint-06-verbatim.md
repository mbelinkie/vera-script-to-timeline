# Checkpoint 6 review — visual semantics and prior native corrections

Read-only review complete (`issue-144-semantics.ts`, its test suite, `roundtrip_native.py`, a fresh re-read of `roundtrip_build.py`'s `run()` method, `checkpoint-05-disposition.md`, `retained-uid-evidence.json`, and `docs/investigations/issue-141/probe.py`/`report.md`).

## Confirmations of prior checkpoint's findings — all three closed

I re-verified each against the actual current code rather than trusting the disposition text:

1. **Inspector no longer requires unobservable fields.** `roundtrip_native.py:109-221` now builds `native_facts` from only `sourcePath`/`sourceHash`/`trackKind`/`trackIndex`/`recordRange`/`sourceRange`, maps an observed item to an authoring identity via unique-candidate matching (`candidates = [identity for identity, expected in native_facts.items() if facts == expected]`, raising on 0 or >1 matches), and the comment at lines 203-204 explicitly disclaims any authoring-field read. My High finding from checkpoint 5 is closed.

2. **SQLite-path trust gap is fixed.** `roundtrip_build.py:504` now calls `self.store._verify_completed(...)` before the custom replay loop (returning early with the already-"failed" status if it fails — `_verify_completed` itself flips job status internally on mismatch, confirmed by re-reading `build_jobs.py:385-430`), and line 532 now derives `output_path` via `self.store._output_path(self.job_id, stage["name"])` instead of trusting the raw SQLite string. My earlier recollection that this was still open was based on a stale read from an earlier turn — I re-fetched the file fresh this turn and confirmed the fix is actually present. My Medium finding is closed.

   **Minor note (Low, style):** this still reaches into `BuildJobStore`'s underscore-prefixed "private" methods (`_verify_completed`, `_output_path`) from outside the class. Not a bug, just a maintainability coupling worth a one-line acknowledgment in a comment if `build_jobs.py` is ever refactored.

3. **`GetUniqueId` is a real, exercised capability — but scoped to #141, not #34.** I grepped `docs/investigations/issue-141/probe.py` directly: `GetUniqueId` is called on Project, Timeline, TimelineItem, and MediaPoolItem objects hundreds of times throughout that accepted probe, and `report.md:416` states plainly "the actual capture contains `TimelineItem.GetUniqueId`." This is real, verified evidence the call exists and works, not something I'm inferring from general API knowledge. I confirm the disposition's framing precisely: this closes "does this API exist at all," it does **not** mean `studio_spike.py`'s #34 adapter exposes or verifies it (it still doesn't — I re-grepped, zero hits), and it does **not** qualify #144's current target/build — `retained-uid-evidence.json` is bound to #141's own historical identifiers (`projectUid`/`timelineUid`/`occurrenceUid`/`mediaUid` from a specific named capture file, hash-verified), not anything about the present snapshot. I'm not requesting any accepted-source change here, per the instruction — this is just confirmation, and a reminder that any real #145 WI capture still has to independently re-verify these callables against its own live target rather than inherit #141's evidence.

## `issue-144-semantics.ts` — bug hunt by category

I traced each category the prompt asked about against the actual code, not just the passing tests.

- **Alias/identity bypass:** none found. The `sourceUids` check (`issue-144-semantics.ts:78`) correctly forbids both directions of aliasing — a source re-mapping to a different media UID, and two different sources collapsing onto the same media UID.
- **Parser/type assumptions:** `validRange` (lines 46-52) correctly rejects strings, arrays, and extra/missing keys (`exactKeys` + `Number.isSafeInteger`, no coercion). The `range !== undefined` sub-check is dead code (the type is `FrameRange | null`, never `undefined`) but harmless.
- **Candidate uniqueness/precision:** `candidates()` (lines 103-124) requires a *single* candidate range whose compiled geometry exactly matches **both** paired items (video and audio) via `geometryMatches` — confirmed no partial-endpoint acceptance is possible; a candidate that reproduces only one of the two endpoints is excluded. The ambiguous-rounding test traces correctly to this exact mechanism.
- **Exact source/record endpoints:** the move/trim detection (lines 155-159) hardcodes the exact `+25`/`-25` deltas from the plan, not a configurable tolerance — confirmed by trace, not just the test.
- **Clearance/coverage:** `clearance()` (lines 98-102) checks the pair's *observed* (post-edit) geometry against every other *observed* current item on the same track, correctly excluding the pair itself. Coverage (voiceover-token-support) is enforced for free by delegating to the real `compileTimeline`/validator rather than reimplementing coverage rules — confirmed by tracing the "no validator-passing compiler range" test back to `compiled.ok` simply being false for every candidate, not a bespoke check.
- **Accept/reject completeness:** the combination of exact-length check + per-choice uniqueness (`seen.has`) + "row must exist" catches not just too-few/too-many choices but also the sneaky case of one proposal row targeted twice while another is silently uncovered.
- **Stale/malformed decisions:** `applyVisualDecisions` re-runs `proposeVisuals(input)` and requires byte-identical equality to the passed-in `report` before anything else (line 185) — since the report's own `bindings`/row `id`s are hashes of all seven inputs, any drift in any input invalidates every row ID, so this is a strong, not cosmetic, staleness gate.
- **Canonical revision hash/version/new-ID rules:** sequence bump, empty state vector, self-excluding content hash, and UUIDv5 construction (namespace+SHA-1, version/variant bits set correctly) all checked directly against the plan's stated rules — all match.
- **Composition of multiple accepted edits and replay:** `replaceRange` only ever mutates a visual event's own `range`/`version`, never narration text/tokens, so multiple accepted edits can't interact through the text itself; the final check at lines 211-214 still independently re-verifies each accepted row's geometry against a *fresh* compile of the fully-composed document rather than trusting the individually-chosen candidates — this is the right defense and I didn't find a gap in it.

**No concrete bugs found in this file.** This is a notably clean, narrowly-scoped module — the two-line "ambiguous" → "unique" reason overwrite at lines 165-166 is a little hard to read but not incorrect (verified all three outcomes — 0/1/2+ matches — produce the right final `reason`).

## Can this segment connect to the host proof workflow?

**Not yet, and it shouldn't need to change to.** `issue-144-semantics.ts` has no CLI/stdout entry today (confirmed: only `issue-144-compile-cli.ts` and `issue-144-semantics.ts` exist under `packages/contracts/src/issue-144*`) — it's a pure-function module, exactly analogous to `compiler-core.ts` before `issue-144-compile-cli.ts` wrapped it. The described next step (a stdout-only propose/decide CLI wrapper) is the proven pattern repeated, not a new design. One concrete thing worth flagging **before** that wrapper is built:

**Finding (Low/Medium, forward-looking, no current code to point at):** `proposeVisuals`'s candidate search can invoke `compileTimeline` up to 64×65/2 = 2,080 times per proposal row (explicitly disclosed as bounded in the code's own comment), and `applyVisualDecisions` re-runs the entire `proposeVisuals` once more for staleness checking. The existing compiler CLI's subprocess timeout (`_compile`'s `timeout=120` in `roundtrip_build.py:330`) was sized for a single compile, not thousands. Whoever wires the propose/decide CLI should pick a timeout budget empirically from the 64-token worst case, not reuse the compile CLI's constant.

## Next planned seam (nonce-based WI capture) — design check, nothing to inspect yet

The proposed design (nonce ties a capture response to its specific request; a cached file can't satisfy a new request's nonce; equal adjacent reads detect drift only) is sound and consistent with everything already proven in this codebase. One concrete, grounded recommendation: model the nonce file's write the same way `_reserve_intent` already does it (`roundtrip_native.py:325-346`, `O_CREAT|O_EXCL|O_NOFOLLOW`, fsync file+directory) rather than inventing a new reservation primitive — that pattern is already implemented, tested, and reviewed twice now.

## What can proceed / what must wait

- **Can proceed:** building the propose/decide stdout CLI wrapper around `issue-144-semantics.ts` following the existing compile-CLI pattern, with a realistically-sized timeout.
- **Must wait:** any real WI nonce/capture implementation (doesn't exist yet to review); any reliance on `GetUniqueId` through #34's adapter specifically (still unverified there); any omission-rebuild positive (pending wording/route decision, unchanged).

## Could not verify
- Did not run `vitest`/`pytest`; the "20 new + 62 accepted = 82" and "27 passed" counts were not independently executed.
- Could not confirm Resolve's actual `TimelineItem`/track-index semantics beyond what `studio_spike.py`'s `place_events` and #141's probe already demonstrate — the native `trackIndex` correspondence used in `roundtrip_native.py`'s `native_facts` relies on manifest track `"index"` fields matching Resolve's own indexing, which is accepted #34/#35 behavior, not something newly introduced here.
- Did not verify whether DaVinci Resolve's `GetUniqueId()` return value is stable across save/reopen cycles for `TimelineItem` specifically (as opposed to Project/Timeline) — #141's report documents the call exists and was captured, not its long-term stability guarantees.

This is review only, not acceptance.
