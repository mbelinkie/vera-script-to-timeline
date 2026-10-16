# Claude source-backed performance follow-up

Advisory review, 2026-10-12. Model: claude-opus-5-5; session: e40aafc9-8584-47ec-b96c-b5c97564104c. Supplied accepted fixture and roundtrip source in addition to the prior timing packet. Tools disabled; no new benchmark or code changes.

Steward assessment: this strengthens static call-chain evidence but does not prove runtime dominance or savings. It rejects the earlier mutable-setup snapshot idea and narrows measurement toward the PCM evidence renderer/verifier. The suggestion to memoize fixture-rendered output bytes is not adopted; approved test-boundary change and tamper/mutation parity would be necessary. Frozen/runtime checks remain live. Historical counts are not current acceptance inventory.

## Retained Claude response (unverified recommendations)

# performance_verify follow-up: omission and roundtrip test cost

**Basis.** This review comes from reading the supplied sources. All timings come from the #184 recorded run (plan and TSV, 2026-10-11), plus my own arithmetic on that data. I executed nothing and used no tools.

Each claim is tagged:
- **[S]** static fact from the code
- **[M]** recorded measurement
- **[I]** inference from comparing test durations

## Prior-hypothesis ledger

| Hypothesis | Static verdict | Dominance |
|---|---|---|
| Repeated omission setup | **Confirmed [S].** Each test calls a plain helper: `inputs()` → `run("build")` → `bind-baseline`. Generation and composition tests then also run bind-omission-evidence → propose → decide. | Bounded, not attributed (F2) |
| Expensive synthetic PCM in `FrameProvider.synthesize` | **Falsified as a candidate [S].** About 2.1×10⁵ sample iterations per `inputs()` call. | Not credible as dominant |
| Expensive PCM in the evidence renderer and verifier | Not separated before. It is per-sample interpreted Python at roughly 10⁶–10⁷ steps per call [S/I]. | Unmeasured (F3) |
| Duplicated Node startup | **Confirmed [S].** | Small per spawn; spawn count unknown (F4) |

## Findings

### F1 — The routine gate's Python cost is mostly audio-evidence fixture construction (Medium)

**Evidence.**
- [M] #184 plan: non-slow tests accumulated 81.600 s, of which `test_issue144_audio_evidence.py` accounts for 70.278 s (about 86%).
- [M] TSV: `test_structural_refusals[<lambda>-controls0..5]` take about 1.27 s each, and `[complete route removal]` takes 1.403 s.
- [S] Those refusals are raised in `roundtrip_audio._observation`, which runs before `_render`, `_gains` and `_metrics`.
- [M] The positive deterministic case takes 4.007 s.
- [I] So about 1.2 s per test is spent before the product reaches its structural refusal. That time goes to one of two places:
  - test-module input generation (`_wav` and helpers, not supplied), or
  - the product's `_pcm` source decode (an `int.from_bytes` generator per sample).

**Classification.** #184's acceptance criteria are covered (fast runs took 97.9–103.5 s). The optimization opportunity is missing a measurement.

**Falsifiable scenario.** Run a serial cProfile of one `test_structural_refusals` node ID.
- If `roundtrip_audio._pcm` owns most of the time rather than the test-module helpers, this candidate is wrong. The cost is then product-side and out of this lane.

**Minimal safe next action.** Measure first. If test helpers dominate:
- Generate the base fixture outputs once per process as immutable `bytes`, keyed by their generation parameters.
- Write fresh per-test copies into `tmp_path`, so each parametrized tamper lambda still mutates only its own files.
- Never share `array` or `list` objects, which are mutable.
- Never cache `verify_omission_evidence` reports.
- Each xdist worker computes its own copy, so isolation holds.

### F2 — Slow cost is concentrated in omission-family modules, but phases cannot be attributed (Medium)

**Evidence.**

[M + my arithmetic] TSV sums by module:

| Module | Accumulated |
|---|---|
| omission_decisions | ≈601 s |
| omission_generation | ≈670 s |
| omission_preparation | ≈300 s |
| composition | ≈319 s |
| generation_recovery | ≈215 s |
| wi_flow | 294 s |
| **Total** | **≈2.4×10³ s** |

That total is out of 2,974 s accumulated Python time.

[S] `setup()` in `test_issue144_omission_generation.py` and in `issue144_composition_fixture.py` is called inside the test body, not as a fixture. So `--durations` books it under "call", and the TSV cannot separate setup from scenario cost.

[I] Comparing durations gives these bounds:

| Test | Time | What it bounds |
|---|---|---|
| `test_no_omission_preparation_refuses_before_any_evidence_or_provider` | 17.714 s | `inputs()` + build + bind-baseline + refusal, with no evidence call |
| `test_unqualified_omission_report_cannot_be_accepted` | 30.440 s | — |
| `test_generation_binding_link_alias_refuses_before_provider` | 55.164 s | setup through decide-omission, plus one refused run |
| Generation happy path | 152.626 s | generate/rebuild/promote plus verification replays add ≈97 s |

**Classification.** Partial: per-test timing exists, per-phase timing is missing.

**Falsifiable scenario.** If phase timers on the 55 s alias test show bind-evidence/propose/decide below half its wall time, then the claim "post-build phases dominate" is wrong. Optimizing `inputs()` would then be the priority instead.

**Minimal safe next action.** A reporting-only run of three node IDs: the 17.7 s, 55.2 s and 197.1 s tests.
- Run serially, with no other heavy work (#184 ritual).
- Use `python -m cProfile -o … -m pytest -p no:xdist <nodeid>` for attribution.
- Add an out-of-tree, pass-through pytest plugin (loaded with `-p` from a scratch `PYTHONPATH`). It should log:
  - every `subprocess.run`/`Popen`: `argv[0:2]` plus wall time;
  - call counts and wall time for `OmissionBoundary.evidence`, `OmissionBoundary.capture`, `verify_omission_evidence`, `PreparedBuild.__init__` and `PreparedBuild._code_hashes`.

**Caveats.**
- cProfile inflates per-sample generator loops relative to subprocess wait. Confirm with an uninstrumented wall run.
- `from`-imports bind early, so patch the consumer namespaces.
- Never patch attributes that tests themselves monkeypatch: `roundtrip_generation.replace_row_narration`, `roundtrip_proof._replace_pointer`.
- Keep this off acceptance runs, and add no locked dependency (see the interface map).

### F3 — Rank the evidence renderer and verifier as the plausible per-sample hotspot, not FrameProvider (Medium)

**FrameProvider is small [S].** `FrameProvider.synthesize` loops `range(cursor*16)`:

| Row | Duration | Samples |
|---|---|---|
| First row | 8 × 1000 ms | 128,000 |
| Second row | 5 × 1000 ms | 80,000 |
| Revised row | Σ(800+40i), i<7 = 6,440 ms | 103,040 |

The revised row is synthesized once. Replays reuse the cache: `provider.requests` stays at 1.

**The evidence path is larger [S].** `OmissionBoundary.evidence` does the following:
- re-decodes each source with `_pcm`;
- mixes per sample, per channel, per segment (`channels[ch][…] += value*gain`) into lists sized `extentFrames×1920`;
- repeats this for both `reference.wav` and `program.wav`;
- then calls `_wav(channels, 3)`.

`verify_omission_evidence` then:
- decodes all sources and both stereo renders per sample;
- `_gains` makes R²+2R `fsum` passes;
- `_metrics` creates a generator plus an `fsum` per sample, per channel, for both reference and output;
- runs a sliding-window loop.

`_route_samples` uses C-level slicing, so it is not a hotspot.

[I] If the extent equals the two rows (200+125 frames), that is about 6.2×10⁵ samples per channel. Each verify would then cost on the order of 10⁷ interpreted steps. The number of evidence/verify calls per test is unknown, because `roundtrip_omission.py` was not supplied.

**Classification.** The FrameProvider hypothesis is falsified [S]. Evidence-path dominance is missing.

**Falsifiable scenario.** If the profiles from F2 show cumulative time under `FrameProvider.synthesize` comparable to time under evidence/verify, this ranking is wrong.

**Minimal fixture-only candidate (only after measurement).** In `OmissionBoundary.evidence`, content-address the rendered WAV `bytes`. The key is:
- (source id, sha256) pairs,
- `_receipt_bytes(observation)`,
- extent,
- the gain tuple,
- sample width.

The baseline calibration render repeats within a test, and across tests, because inputs are deterministic (uuid5 IDs, seeded tones).

These must stay live on every call:
- `evidence_calls.append`;
- every origin read with its sha256 assert;
- every file write;
- `self.write_render(...)`, because `WireBoundary` drives the real `wi.perform` queue/inspect render there, and the memo must sit before it;
- receipt hashing of the written output.

**Product-side changes are out of lane.** Optimizing `_metrics`, `_gains` or `_pcm` is not a minimal candidate:
- `roundtrip_audio.py` is listed in `CODE_PATHS` and in the report's `codeHash`;
- `fsum`-exact numerics sit near the 0.0004 and 0.006 thresholds.

Such changes need a separately approved change note.

**Not prioritized [S].** `OmissionBoundary.capture` hashes the full media file for every event, and groups events in O(E²). At the event counts and file sizes visible here, this is small.

### F4 — Node startup is duplicated but bounded per spawn (Low)

**Spawn inventory [S].**

| Caller | Node spawns |
|---|---|
| `PreparedBuild.__init__` → `_check_runtime` | 1 (`node --version`) |
| `_compile` | 1 more `_check_runtime`, plus 1 compiler run (`issue-144-compile-cli.ts`, timeout 120 s) |
| Fixture `_compile(root,"node")` | 1 in `inputs()`, plus a second in composition `setup()` |
| `OmissionGeneration.finalize` | `session._semantic("finalize-omission", …)` (child process; presumably Node, source not supplied), plus `PreparedBuild(self.revision)` |
| Test bodies | direct `PreparedBuild(...)` constructions |

`finalize` runs on both publish and every replay.

**Bound [M/I].** `test_actual_compiler_and_package_run_all_core_stages_without_synthesis` takes 2.414 s. That includes at least three Node spawns plus package build and verify. So spawns explain the 30–150 s tests only if counts reach dozens per test, which is unknown.

**Classification.** Partial.

**Non-candidates.** Both runtime-pin checks are #144 locked-toolchain invariants:
- The re-check inside `_compile` guards against the executable or PATH changing between construction and compile.
- `test_wrong_node_refuses_before_any_job_or_snapshot` depends on the constructor-time refusal order.

**Falsifiable scenario.** Wrapper counts × mean Node wall time ≪ test wall time ⇒ Node startup is not material.

**Next action.** Count spawns only. If Node time is material, the only fixture-side lever is composition `setup()`'s redundant first compile. Its manifest only seeds narration plan entries that the second compile also yields. But `inputs()` is shared, so changing it needs a change note.

### F5 — Sharing setup through mutable snapshots is infeasible or weakening (High risk)

**Evidence [S].** Identity is bound to absolute, root-local paths:
- `inputs()` writes `materialization-plan.json` origins as absolute paths under `root/narration-cache`, and `PreparedBuild` hashes them.
- `service_inputs` binds `"cacheRoot": str(cache)`. It requires `cache.is_relative_to(session.root)`, no symlinks, and `st_nlink == 1`.
- `cache_replay` compares `assetRecordPath == str(entry.path/"asset.json")`.
- `_regular` refuses symlinked ancestors and `nlink != 1`.

Tests also mutate session state:
- the pointer (interrupted `_replace_pointer`);
- job stores (`pending.store.resume`);
- retained cache and receipt files, via 8 tamper targets in `test_retained_generation_and_actual_cache_cannot_be_replaced_by_status_claims`.

**Classification.** Issue-scope guardrail, from #144's acceptance criteria (stale and tampered inputs fail closed; replay is idempotent) and #35's idempotency.

**Falsifiable failure scenario.** Suppose a session-scoped template proof root is copied per test.
- Without path rewriting, `cache_replay` or `_verify_media` refuses.
- With rewriting, the helper re-authors product receipts. A regression in `finalize(publish=True)` receipt construction would then pass every test that starts from the template.
- Hardlink or symlink sharing is refused outright.

**Next action.** Reject snapshot or template proposals. Restrict caching to pure test-input bytes (F1, F3). Product-output caches, such as the fixture compile or the narration-cache tree produced by FFmpeg normalization, rank last and are not recommended.

## Accepted invariants — must stay live

- **`PreparedBuild` checks:** `_check_runtime`, `_assert_current` (rehashes about 45 `CODE_PATHS` entries plus inputs and frozen inputs), `_verify_media`, `_verify_compiler_files`, `verified_package`.
- **`OmissionGeneration.finalize(publish=False)`:** recomputes `replace_row_narration`, `_semantic`, both `cache_snapshot` calls and byte or receipt equality. The replay assertions (`session.run(...) == generated/rebuilt/promoted`) and the 8-target tamper loop depend on this.
- **`fresh()` capture and comparison:** `capture` plus `proposal_inputs` comparison; the `drift` and `stale` tests depend on it.
- **Capture identity:** nonce and `requestHash`, plus `WireBoundary` nonce-keyed capture paths.
- **Evidence verification:** `verify_omission_evidence`, including `files.current()` and the report hash.
- **Boundary counters:** `boundary.requests`, `evidence_calls`, `studios` and `provider.requests`. Calls into the boundary or provider can be neither skipped nor deduplicated.
- **Gate shape:** #184's full gate stays serial and unchanged. Any edit to #144 test helpers is an accepted-test change that needs a separate change note. This should be a new, separately authorized item, not a reopening of #184, whose acceptance criteria are evidenced.

## Dependency and interface map

```
test body ─ setup() [plain fn]
  inputs(): _visual_inputs* → NarrationService.process_block ×2
            (FrameProvider → Normalizer/FFmpeg* → NarrationCache)
            → fixture _compile(node)* → materialization-plan (abs origins)
  composition setup(): +gzip publication media → fixture _compile(node)
  ProofSession.run*: build → PreparedBuild(node --version, CODE_PATHS hash)
     → BuildJobStore stages (verify speech/media, _compile: node×2,
       package build/verify) → NativeStages/InjectedStudio
  → bind-baseline/bind-evidence/propose/decide*: Boundary.capture,
     Boundary.evidence (fixture mix+_wav) → verify_omission_evidence
  → generate: fresh(capture) → finalize: replace_row_narration,
     _semantic(node*), PreparedBuild, cache_snapshot ×2
```

`*` marks code that was not supplied.

**Coupling.** `CODE_PATHS` includes `uv.lock` and `package-lock.json`. Any dev dependency added for performance work (profilers, numeric libraries) therefore changes every `snapshot_id`. #184's pytest-xdist lock change already did this. That is recomputed live, not a defect. Prefer stdlib or out-of-tree measurement.

## Unverified

- The bodies of `roundtrip_omission.py`, `roundtrip_proof.py` (`_semantic`, capture), `_visual_inputs`, fixture `_compile`, `_wav`, `run_demo`, `Normalizer` and `NarrationCache`.
- How many evidence/verify calls and Node spawns each test makes.
- The actual `extentFrames`.
- Whether audio-evidence base fixtures are identical across parameters.
- Whether cache metadata embeds absolute paths.
- Media file sizes.
- Every phase attribution above, and all runtime-saving claims; none are asserted.
