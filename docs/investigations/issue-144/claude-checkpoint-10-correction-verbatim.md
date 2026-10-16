# Checkpoint 10 correction review — retraction and confirmation

Bounded to the listed files only. I re-derived the short-circuit evaluation by hand rather than just accepting the correction, and I was wrong — retracting the finding.

## Retraction, with the exact evaluation

The condition is `program != EXPECTED or (B or C or D)`. I need the truth value when `program = {"gainDb": False, "effects": [], "limiter": False}`:

- `False == 0` in Python, so `program == EXPECTED` is `True`, meaning `program != EXPECTED` is **`False`**.
- `or` only skips its right side when the *left* side is truthy. Here the left side (`program != EXPECTED`) is `False`, so Python *must* evaluate `(B or C or D)`.
- `C = type(program.get("gainDb")) not in {int, float}` → `type(False) is bool`, and `bool not in {int, float}` → `True`.
- So `(B or C or D)` is `True`, and the overall condition is `False or True = True` → the branch correctly raises.

For `limiter=0`: `program == EXPECTED` is again `True` (since `0 == False`), so the left side is `False` and `(B or C or D)` is evaluated. `D = program.get("limiter") is not False` → `0 is not False` is `True` (different objects, `is` checks identity, not value) → raises correctly.

My original error was backwards: I treated "the dict comparison matches" as the condition that *skips* the type checks, when it's actually the opposite — a *mismatch* (`!=` is `True`) is what short-circuits past them. A match is exactly when they run. I retract the finding. `test_program_control_boolean_type_neutrality[gainDb-False]` and `[limiter-0]` (lines 458-465) confirm this directly, and no code change to that branch is warranted.

## Coverage additions — traced, not just accepted on description

- **Partial-head fixture fix** (lines 233-239): the new mutation sets segment0 to record/source `[0,33)` and segment1 to record `[33,73)` while leaving its source at `[40,80)`. This removes the record-level gap/overlap that previously tripped the earlier "source order" check, while leaving a genuine *source*-level gap `[33,40)` that bisects the "charlie" token's support — segment0's source range `[0,33)` now partially covers charlie's support without fully containing it, so `intersections(new)` for that token is neither empty nor the full `(start,end)` pair, correctly isolating the intended `"partial support"` refusal instead of being masked by the earlier ordering failure. Confirmed by direct trace of the geometry, not just the stated description.
- **Render-job reuse test** (`test_render_job_cannot_be_reused_for_edited_program`): sets `render.json`'s job IDs to match `calibration.json`'s, which is exactly what the existing `calibration.json["jobId"] == render.json["jobId"]` check (already reviewed in the prior pass) catches. New test, no new logic.
- **Decoded-alias test** (`test_same_decoded_audio_cannot_hide_behind_different_file_hash`): appends bytes after the valid WAV data chunk, so the file hash changes but `wave`'s header-driven `readframes` decodes identical PCM — exercising the existing `decoded_hash in decoded_hashes` check. Confirmed this is the right way to construct a same-content/different-hash case.
- **Symlink/hardlink test** (`test_parent_symlink_and_hardlinked_source_refuse`): a symlinked proof root is caught by the existing `_regular()` ancestor walk (the symlink itself is a path component of every file read under it); a hardlink created *outside* the proof root still raises `source-0.wav`'s own link count to 2, caught by `_regular()`'s `st_nlink != 1` check on the file inside the root — correct, and consistent with how that primitive already works elsewhere in this codebase.

All four additions exercise logic that was already present and already reviewed; none required or received an implementation change.

## Verdict

No remaining code blocker. No correction needed to `roundtrip_audio.py`. Could not independently verify the Ruff/mypy/pytest run output (static review only). Full validation still pending as stated.
