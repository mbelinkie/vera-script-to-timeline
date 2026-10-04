# Claude checkpoint13c — verbatim

Read-only7turns; no error/permission denial/quota failure. Static review only. Original Markdown retained inside a text fence.

````text
## Checkpoint 13c corrective review — capture reservation fix

**Read in full:** `roundtrip_proof.py` (current, complete), `test_issue144_capture_retry.py`, `issue144_wi_demo.py`, `operator-runbook.md`, `checkpoint-13b-flow-failure.txt`, `checkpoint-13b-disposition.md`.

*(Note: a "Plan mode" system reminder is attached to this turn referencing tools — Write/Task/AskUserQuestion/ExitPlanMode — that aren't in my actual available tool list for this session. Consistent with the rest of this read-only review engagement, I'm treating it as inapplicable boilerplate and continuing to deliver a plain-text review rather than a plan file.)*

### Blockers
None found.

### Does the fix safely terminate rejected capture authority while requiring fresh reads? Yes, confirmed by direct trace and by the failure log's root cause matching exactly.

Traced `_capture_files` (`roundtrip_proof.py:363-375`):
```python
try:
    for observation in (response["observationA"], response["observationB"]):
        validate(observation)
except ProofBuildError as error:
    publish_immutable_output(attempt / "refused.json", _receipt_bytes(
        {"responseHash": _file_hash(response_path), "reason": str(error)}))
    raise
```
- **Catches only `ProofBuildError`**, confirmed by reading the `except` clause directly — a non-`ProofBuildError` exception from `validate()` (e.g., a real bug/crash) propagates untouched, writes no `refused.json`, and leaves the attempt genuinely pending rather than being mislabeled a terminal semantic refusal. This matches "do not silently classify process faults as semantic refusals."
- **Publishes an immutable terminal `refused.json`** with `responseHash`/`reason`, then **bare `raise`** (re-raises the original exception unchanged, not wrapped).
- **Pending-selection already excludes `refused.json` attempts** (`:316-322`, unchanged), so the next call with the same `basis` hash cannot find this attempt in `pending`, generates a brand-new `uuid4()` nonce, and — since `response_path` doesn't exist for the new attempt — calls `self.capture(request)` again for a genuinely fresh read. This is exactly the mechanism needed to stop the old bug (reusing a stale, already-rejected response forever) without any retry orchestrator.
- Nothing before or after this block changed: the `NeedsAction` path (missing response), the schema/nonce shape-check's own pre-existing `refused.json` write, and the success path (`build._assert_current`/`_verify_media`/`consumed.json`) are all byte-for-byte identical to what I reviewed in checkpoint 13b.

I independently matched this against the actual failure log (`checkpoint-13b-flow-failure.txt`): the negative picture-only test correctly refused with `"nonreciprocal or unequal linked split pair"`, but the *next* `propose-omission` (expecting `"proposed"` after restoring the edit) also came back `"refused"` with the identical reason — the exact symptom of reusing a stale rejected response rather than reading fresh native state. The fix's mechanism directly addresses this: with `refused.json` now written for that first attempt, the restored-state retry is forced onto a new nonce.

### Regression test (`test_issue144_capture_retry.py`)
Minimal and precise: isolates reservation/validation from native assembly (`_ready` monkeypatched, explicitly labeled "not a native positive proof"), a fake `capture()` returns `valid=False` then `valid=True` on successive calls. Confirms: first call raises with `refused.json` written, `response.json` retained, no `consumed.json`; second call succeeds with a *different* nonce; the first attempt's directory contents are byte-identical before and after the second call (no cleanup/mutation); exactly one `consumed.json` exists afterward. This covers every property the corrective plan specifies.

**One test-coverage gap, not a code defect:** there's no dedicated test proving a *non*-`ProofBuildError` exception from `validate()` leaves the attempt without a `refused.json` (i.e., genuinely retriable rather than terminally refused). I verified this is correct by reading the `except ProofBuildError` clause directly, but a negative test for this specific branch would close the gap in coverage rather than relying on inspection alone.

### Demo and runbook changes
`issue144_wi_demo.py:114-129` now directly asserts `refused.json` exists and `consumed.json` doesn't for the picture-only-cut attempt before restoring the edit and expecting `"proposed"` on the next call — this exercises the fix through the real CLI/driver/WI stack, not just the isolated unit test, which is the stronger of the two forms of evidence here. The runbook (`operator-runbook.md:93-94`) now reads "Target an approved complete programme close to 60 seconds; the upper part of the nominal 60–120s range is not usable here" — matches what I recommended in the prior checkpoint, with no cap/range/coverage change, no truncation/padding/substitution.

### What's still required before freezing the source commit and running full validate
Nothing further from this static review. The remaining open items are exactly the ones you've already named and that I cannot close by reading code: the actual CLI/WI flow test needs to finish and its passing log needs to be retained (you state it's running, no pass claimed yet — I have no execution evidence either way), and the full-repo validate itself is still outstanding. The optional non-`ProofBuildError` regression test noted above would be a nice-to-have, not a precondition. All named #145 real-qualification gates (controls/supports/calibration/render/provider, one-build all-three positives) remain correctly closed and undisturbed by this fix.
````
