# Checkpoint 12c finished-code review — pure canonical bridge (revise/finalize-omission)

Read-only review complete, bounded to `issue-144-omission-build.ts`, the new/changed branches and loader hooks in `issue-144-proof-cli.ts`, `_semantic`'s artifact-binding logic in `roundtrip_proof.py`, and both new bridge test files. I traced the logic directly rather than trusting the summary.

## Canonical raw handoff binding — confirmed sound, one operational note for later

Two different checks exist for the handoff's claimed document identity, and I verified they're complementary, not duplicative: `issue-144-proof-cli.ts:59` checks `handoff.revisedDocumentHash !== hash(bytes[0])` — a comparison against the **raw file bytes**, matching exactly how `replace_row_narration` originally computed it in Python (`_digest(_operator_bytes(revised_path))`, checkpoint 9). `finalizeOmission`'s own internal check (`omission-build.ts:27`) compares against `sha256CanonicalJson(document)` — the **re-serialized parsed object**. These only agree when the on-disk file is the unmodified canonical output of `revise-omission`. I checked whether this is a real risk for the eventual host integration and concluded it isn't: the already-proven `_decide()` pattern (`roundtrip_proof.py:546-547`) already writes TS artifact text to disk verbatim, never re-serializing through Python's own JSON writer, and this new test follows the identical discipline (`revised.write_text(revision["artifacts"]["script-document.json"])`). So this is confirmed consistent with the established pattern, not a new gap — worth naming only so whoever wires the public workflow knows *why* both checks exist and doesn't "simplify" by dropping one.

## Changed-vs-unchanged dependency guard — confirmed thorough, one test-precision gap

I traced all three layers of this guard: `withoutNarration` equality (everything except the `narration` array must be byte-identical, catches the "metadata" test), array-length equality (`dependencies.narration.length === prior.narration.length`), and positional equality for every non-replaced index (`omission-build.ts:40`, catches the "unchangedRow" test *in principle*).

**Finding (Low, test precision, `issue-144-omission-bridge.test.ts:75`):** the "unchangedRow" case mutates the handoff by *appending* a duplicate narration entry (`data.handoff.dependencies.narration.push(structuredClone(...))`), which changes the array length. That means this case is refused by the earlier length-equality check (step 8), not by the positional-equality check at line 40 that the test name implies it's exercising — the test doesn't assert which specific error fires, so this isn't caught, but it means the positional-equality guard for an *unchanged-length* mutation (e.g., a different narration row's `textHash` silently altered without changing array size) is currently unproven by a dedicated test. **Smallest fix:** add one case that mutates an existing non-replaced narration entry's content in place (e.g. `data.handoff.dependencies.narration[1]!.textHash = hash("x")`, same length) to specifically exercise line 40 rather than the length check.

## Fresh IDs / compile / artifact output — confirmed correct

`revisionId` is reused unchanged (only its `export` keyword changed, confirmed by direct read), seeded from `{document, priorDependencies, verifiedHandoff}` — binding the fresh build/manifest/report IDs to the full handoff, not just the script, as checkpoint 12b required. The "no stale splice" guard (`omission-build.ts:41`) independently recomputes `textHash` from the block's actual text rather than trusting the dependency's claim, and requires the new `assetId`/`audioHash` to differ from the old ones — confirmed exercised by the "oldAudio" test (relabeling old audio under the new revision correctly refuses). The Python integration test confirms the full chain end to end: `finalized["artifacts"]["timeline-manifest.json"]` byte-matches what `PreparedBuild`'s own durable compile stage later reproduces (`rebuilt.manifest_path.read_text() == manifest`), and the untouched second row's dependency stays byte-identical through the entire finalize→rebuild chain (`rebuilt.dependencies["narration"][1] == prior.dependencies["narration"][1]`).

## Visual path unchanged — confirmed

The `propose`/`decide` branches' internal logic in `issue-144-proof-cli.ts` is byte-identical to before; only the `if/else` chain was restructured to accommodate two new `else if` branches. No regression.

## Pure-vs-host authority — confirmed, not prematurely wired

`ProofSession.run()`'s public action dispatch list is unchanged (`build/bind-baseline/propose/decide/rebuild/promote/status` only) — I checked this directly, not just the prompt's claim. The only Python-side changes are `SEMANTIC_SOURCES` gaining the two new TS files for drift tracking, and `_semantic`'s artifact whitelist conditionally expanding for the `finalize-omission` action string — neither adds a reachable public path. The integration test calls `session._semantic(...)` directly, bypassing `run()` entirely, confirming this really is a bridge exercised in isolation, not smuggled into the public workflow. `assert not session.pointer.exists() and not rebuilt.intent_path.exists()` at the end of that test independently confirms no baseline/native side effect occurred anywhere in the chain.

## No blockers found

One concrete, smallest-possible test addition recommended above; everything else checked out by direct trace of the actual logic, not by trusting the stated test outcomes. This is a sound pause point.

Static review only — not test execution or final #144 acceptance.
