# Checkpoint 10 finished-segment review — bounded audio-evidence verifier

Read-only review complete, bounded to the listed files (`roundtrip_audio.py`, both new test files, the plan/disposition, and the `CODE_PATHS` diff). This traces the actual code paths for each item requested, not just the passing tests.

## One concrete bug found

**Finding (Low severity, `roundtrip_audio.py:181-189`) — the `programControls` neutrality check's dict-equality shortcut makes its own type-strictness checks unreachable, and lets a boolean slip through where an int/bool distinction was clearly intended elsewhere in this same file.**

```python
elif program != {"gainDb": 0, "effects": [], "limiter": False} or (
    not isinstance(program, dict)
    or type(program.get("gainDb")) not in {int, float}
    or program.get("limiter") is not False
):
```

Because `or` short-circuits, the `type(...) not in {int, float}` and `is not False` checks only get evaluated when `program != {...}` is already `False` — i.e., when `program` already equals the expected dict by value. But Python dict equality compares values with `==`, and `False == 0` and `0 == False` are both `True` — so `{"gainDb": False, "effects": [], "limiter": False}` and `{"gainDb": 0, "effects": [], "limiter": 0}` both equal the expected dict and pass this check, bypassing the type checks that exist specifically to prevent that. This is a real inconsistency, not a one-off oversight: the author got this exact pattern *right* twice elsewhere in the same file — the route-level controls check (`type(controls["gainDb"]) not in {int, float}` evaluated unconditionally before the value check, lines 222-225) and the render settings check (`any(type(settings[key]) is not int ...)` as the first `or` operand, lines 406-416) — so this one branch is the odd one out.

**Consequence check:** I confirmed this has no numeric/safety impact — `programControls` is never used in any downstream reconstruction or gain computation, only as a structural gate — so a `gainDb: False` or `limiter: 0` passing through doesn't change any verdict. It's a precision/consistency gap, not an exploitable path to a wrong "supported" result.

**Minimal fix:** reorder so the type checks run first (matching the two correct examples already in this file), e.g. `type(program.get("gainDb")) not in {int, float} or program.get("limiter") is not False or program != {...}`.

**Minimal test:** neither test file exercises `gainDb: False` or `limiter: 0` specifically (`test_structural_refusals` only covers `limiter=True` and non-empty `effects`) — add one parametrized case for each to `test_structural_refusals`.

## Everything else requested, traced and confirmed sound

- **Evidence substitution / calibration leakage:** I checked whether the calibration receipt's claimed `observationHash: baseline_hash` could be satisfied by secretly supplying the *edited* program's bytes as "reference.wav." It can't: `_gains`/`_metrics` independently reconstruct the program from `baseline_routes` (known geometry) and require that reconstruction to be numerically consistent with whatever bytes "reference.wav" actually contains (`"unchanged calibration consistency differs"`, line 630-631). Since the edited program has a real gap where the omitted word was, a mislabeled edited-as-calibration file would fail this check on its own, independent of the separate `calibration.json["jobId"] != render.json["jobId"]` guard (line 622-626). Confirmed by `test_gain_fitted_only_to_unchanged_reference` (scaling the reference 2x correctly fails on "gain qualification," proving gains are derived from the actual bytes, not trusted labels).
- **Wrong positive acceptance / ambiguity:** route↔source binding requires exact bijection (`identity in ids or source_id in source_ids or source_id not in sources`, lines 200-201); the two-tier route check (`(id, sourceId, controls)` equality across baseline/edited, then full-route equality for every non-target route) jointly forces every non-target route to be byte-identical while allowing only the target route's segments to change. The "no interior omission" check correctly rejects first/last-token deletion and non-contiguous omission (lines 591-597), and the "partial support" refusal (line 576-577) runs strictly before a support can be classified as omitted/retained, so no partial-interval case can slip into either bucket.
- **Silent route removal:** caught two ways — `len(routes) != len(sources)` for whole-route removal (line 191-192), and `not segments` explicitly labeled "complete route removal" for an emptied route (line 229-230).
- **Malformed JSON types / boolean-vs-integer:** `_int`'s `type(value) is not int` (not `isinstance`) correctly rejects booleans everywhere it's used (confirmed by the `recordStart=True` test case), and the route-controls/render-settings checks use the same discipline — the one exception is the bug above.
- **Neighbor/source interval completeness:** every declared support on *every* source (not just the target's) is checked — non-target supports must retain full, unambiguous intersection with the edited observation (`"untouched route token removed"`, line 587-588) independent of whether that source happens to have declared supports at all, since a support-free non-target route is still protected by the whole-route byte-equality check.
- **Unsafe local paths / hash drift:** `_Files.read` rejects absolute paths and any `.`/`..` component anywhere in the path (not just a prefix check), confirmed by the `"../escape.wav"` test; it reuses the already-hardened `_regular()` symlink-ancestor walk; and `files.current()` re-verifies every previously-read file's hash immediately before the final verdict is set.
- **Replay report bindings:** the report is a pure function of immutable inputs (`report["reportHash"]` is a self-hash, not an external binding), confirmed deterministic by direct equality assertion on two successive calls.
- **Qualification boundary:** `real_issue145` is refused at the very first check, before any file is touched, and `retained_consistency` structurally can never reach `"supported"` — there is exactly one line that sets a non-refused status, gated only by the function's own `evidence_level` parameter, which the caller supplies directly (no JSON field can override it).

## Is this an honest building block, not an all-refused substitute?

Yes. It has a real positive path (`test_complete_closed_routes_positive_and_deterministic`), real and meaningfully distinct negative paths (22 structural refusals + 8 receipt/profile refusals, each tied to a specific, different reason string), and it correctly keeps the numeric tolerance explicitly subordinate to discrete structural proof — the quiet/tiny-residue test only ever reaches `consistent_unqualified`, never `supported`, and asserts the limitation text is present in the report. The retained-W1 test independently hash-verifies publication bytes, all word supports (not just "charlie"), full `base.mov`/`a1_alpha.wav` equivalence, and the actual native record/source ranges from the real W1 capture, while still correctly landing on `consistent_unqualified` rather than claiming a live positive. The plan's own added render-liveness caution is present in `LIMITATIONS` and in the receipt-binding checks. I found no path that manufactures a false "supported" result and no scope creep into live native/provider territory.

This is static advisory review only — not test execution or native evidence.
