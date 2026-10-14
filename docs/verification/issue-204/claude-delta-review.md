# Verdict: **GO** for the delta at `724a829`

GO means one thing: B1 and B2 from the `560a44e` review are resolved well enough to proceed to the held operator, UID and install gate. It does not mean:

- External acceptance,
- final full validation,
- or any authority, UID, installation, or native action.

I ran nothing; tools were disabled. The fast receipt (520 passed, exit 0, with no skips reported) is your evidence, not a rerun of mine.

---

## Prior blockers

### B1 — resolved

**Clip gaps.** `native_qualification_v2.py:629-642` now requires all of the following before a clip gap can be `supported`:

- exactly one supported `timeline:audio.GetTrackCount` row;
- one `GetItemListInTrack` row per counted track;
- every one of those rows `supported`.

An inventory row only becomes `supported` at `:961`, after every item has been read. Rows read after the last successful guard are downgraded at `:1011-1016`, before `_gaps` runs, so an interrupted track cannot feed a `supported` claim. Parent rows now appear in each gap's sources (`:717`).

`tests:347-362` reproduces both the missing-inventory and overflow triggers. It would have failed against `560a44e`.

**Render candidates.** At `:761-783`, codecs and resolutions now require supported, non-empty rows for every parent enumeration. Truncated or invalid format lists mark the format row `ambiguous` (`:976-979`), which propagates to the gap. `tests:365-386` covers this. I found no remaining path to a false `supported` result.

### B2 — resolved, with one coverage gap (N1)

The installed qualification branch now runs in subprocess tests for:

- the clean pre-import provenance record, which is read-only (`tests:399-417`);
- authority bytes, authority binding, approval drift, extra key and wrong action, each keeping a refusal record;
- closed-authority checks, including `readOnly: 1`. In Python `1 == True` makes the dict comparison at `VERA Delivery v2.py:200-205` pass, but the explicit `is True` checks at `:206-207` catch it.

The CLI wiring for `capability-authorize` and `capability-request` is exercised. The trap now records forbidden attempts, so stopped-path tests can no longer swallow a mutation.

I also checked the other changes the brief asked about:

- **Hardlinks:** refused in `_read` (`:112`) and in the bootstrap's `provenance_bytes`, which binds the opened file's identity and checks size and mtime before and after the read.
- **macOS aliases:** case and firmlink aliases are caught by comparing device and inode identity, and tested against the real filesystem.
- **Input drift during getters:** tested for source, authority and approval.
- **Partial reports:** the result is printed before it is written, a single oversized getter is now kept as an `ambiguous` row, and unverified rows are marked.
- **Channel map:** the parser now matches the documented object shape.
- **Issuer provenance:** the plan now describes issuer metadata honestly as self-declared.

---

## Nonblocking findings

None of these can produce a false `supported` result or a native effect. The source-pin consequences are explained in the next section.

**N1 — The bootstrap "overlap" tests never reach the overlap checks.**
- **Where:** `tests:444-449`. The test edits `evidenceDir` only in the request binding.
- **What happens:** `VERA Delivery v2.py:212`, the check that the authority binding equals the request binding, refuses first. The overlap clauses at `:215-222` are never true in any test.
- **Second effect:** the failure handler at `:272-277` then writes the refusal to the authority's safe evidence directory. That is the only reason the test's assertion of exactly one refusal file passes.
- **Disposition overstates:** `review-disposition.md:23-24` claims protected-root overlap coverage.
- **Risk is low:** a CLI-issued authority cannot overlap, because `_binding` refuses it, and the controller independently refuses before any getter.
- **Remedy (test-only, does not change source pins):**
  1. Hand-craft an authority whose `evidenceDir` is inside the repository, then the plugin root, then the release, as `tests:539-546` does for the controller.
  2. Rehash it into the request and launch.
  3. Assert there is no `bootstrap-started-*` file under the protected directory, no `result-*`, and that stdout reports `reportRetention` unavailable.
  4. Correct the disposition text.

**N2 — Render candidate states are over-coupled (conservative, not false).**
- **Coupling:** at `:761-769`, the video `GetRenderCodecs` gap requires `GetAudioRenderFormats` rows, and the reverse. If either audio getter is absent on 21.1.1, the video candidate gaps report `ambiguous` for an unrelated reason.
- **Empty lists:** `bool(r["value"])` at `:782` means an empty resolution list for an audio codec, plausibly the normal result for `wav`/`lpcm`, makes `GetRenderResolutions` permanently `ambiguous`.
- **Remedy:** classify video and audio chains separately, and treat a supported empty list as observed-empty. Otherwise, explain this when reviewing the report.

**N3 — Remaining stop points created by the code, not the API.**
- `:986-993` still hard-stops on a single malformed codec dictionary. This is the same pattern that was fixed for formats, and the disposition's claim that "no … regex silently stops all later getters" is only true for formats.
- The value budget at `:531-536` also applies to the required identity getters in `_context` (`:566-579`). Once it is exhausted, the next guard fails.
- The 2000-row cap at `:513` likewise stops the run.

All three stop truthfully, but would cost an operator rerun. I estimate a small disposable target fits within the limits. Recommendation: leave the code as is and treat any hit as a runtime fix under the agreed sequence.

**N4 — The result's size is no longer checked before it is written.**
- **Trigger:** `write_immutable_json` indents the result. Nested values within the about 699 KB budget can expand past `_read`'s 2 MiB bound when the result is re-read for hashing at `:1029`.
- **Effect:** `result-*` is kept and printed, `hashes-*` is missing, and a bootstrap refusal follows.
- **Remedy:** hash the exact bytes written instead of re-reading the file.

**N5 — The item-inventory row breaks the stated "raises means ambiguous" rule.**
- **Where:** `:888-898`. A `GetItemListInTrack` that exists but raises, or returns a non-list, stays `unsupported`.
- **Remedy:** set `ambiguous` once the getter is confirmed callable, or correct the disposition at `:47`.

**N6 — The ordinary refusal handler line changed.**
- **Where:** `VERA Delivery v2.py:304`, in the ordinary #177 branch.
- **Behaviour:** equal or stricter for existing roots. The one weaker edge case is an evidence path containing `..` beneath a package directory that does not exist. The ordinary launcher's own check (`workflow_v2_launcher.py:76-79`) is unchanged.
- **Remedy:** stop describing the ordinary path as "untouched"; it is "refusal-retention only".

**N7 — CLI test gaps.**
- `tests:496` tests all three confirmation flags missing at once, not each separately.
- `source_pins` is monkeypatched (`:470-472`), so the real checkout's pin reading is first exercised at the operator's authorize step. That step fails closed if anything is wrong.

**N8 — Smaller items.**
- Plan `:111`, "No commands have run for this stage yet", is stale.
- `track.enabled` (`:652-667`) depends on the parent inventory rows but does not list them in its sources.
- The alias tests skip on Linux. This only matters if cloud substitution is attempted, and the Resolve-boundary diff points to a local full run anyway.
- `RUNTIME_FILES` is still duplicated in two modules; if the copies drift, it fails closed.

---

## Sequencing consequence

Any change to a file listed in `SOURCE_FILES` changes the release and authority bindings. That covers the controller, the CLI, the launcher, the bootstrap and the change note. So:

- **Source changes (N2–N5):** make them before the release is prepared and the authority issued, with focused and fast checks and a brief delta review. Or defer them as recorded limitations.
- **Test and doc changes (N1, the N5 doc option, N8 doc items):** these do not change source pins. They can be folded in before final full validation.

My recommendation is to proceed without further source changes and apply N1 and the doc corrections now.

---

## Held gates (unchanged)

- **Trusted target UIDs** must come from an existing, audited handoff. UIDs observed by this preflight would be circular trust. This needs a coordinator or Producer decision before any authority is prepared.
- **The authority** is issued personally by the operator through `capability-authorize`. That receipt is local and procedural, not a signed credential.
- **The installed run** follows the #109 quit/archive/copy/restart flow on Studio 21.1.1 build 10 with External Scripting set to None. It must produce one actual read-only report and evidence that the target was left unchanged.
- **After the real report:** any runtime fixes get a delta review, then a complete `VITEST_MAX_WORKERS=1 npm run validate` runs on the final delivered state.
- **Scope:** #204 cannot close #178. No `qualify_build`, render, setter, creation, save, export or queue action is authorized.
