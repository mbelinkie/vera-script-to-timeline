# Issue 141 — operator record

## Attempt 1, September 30

The operator confirmed launching the installed integration and reported:
“Doesn't seem like anything happened.” The actual injected journal/result is
retained in `evidence/attempt-1/`, with full originals retained locally.
Studio 21.1.0 build 14 / injected Python 3.14.7 created only the named project
within the recorded API sequence, then the probe's settings check failed.
No media import or timeline creation appears in that sequence.

External Scripting None and existing-project/source-state attestations are
**pending**; this operator message did not explicitly confirm them. No viewer,
listening, routing or editorial observation is inferred.

## Attempt 2, September 30

The operator again reported no visible result. The timestamped injected run
at 17:20:18 UTC retained the same project ID and application build. Its journal
contains one settings request and a refusal, with no imports or timeline
creation. The agent had included the API's read-only playback-rate property.
Other requested settings may have partially applied; no post-failure settings
readback exists for this attempt. Preserve that uncertainty until the next
read-only settings capture. Originals and public redacted evidence are retained
under `evidence/attempt-2/`. None and untouched-existing-state attestations
remain pending.

## Later entries

Do not fill entries from expected values, synthetic checks or accepted #110's
prior operator confirmation.

For each stage retain:

- Operator/date; actual Resolve product/version/build; External Scripting None.
- Exact project/timeline IDs, before/after capture filenames and SHA-256 values.
- Ordered action, selected occurrence/source bounds, exact settings/timecodes.
- Actual viewer/listening/Fairlight routing result or limitation/error.
- Repeat capture/action and differences, including custom-data/marker survival.
- Confirmation of synthetic-only scope and whether existing source state was untouched.

Full local readbacks remain immutable. Publication uses path-redacted copies
with original raw hashes; private local paths never enter GitHub evidence.

## Successful baseline preparation, September 30

The operator reported “It worked!” The injected run at 17:39:43 UTC recorded
DaVinci Resolve Studio 21.1.0 build 14 / CPython 3.14.7; project
`VERA Issue 141 Synthetic Probe 20260930-01a0f318`
(`97037b5a-aab6-48a9-b7e4-4c5697ae10a0`); baseline timeline
`88f7923d-55a7-471f-b09b-cf10f9fae8ad`. Preparation setter/import/link/marker/save
calls returned success. The retained capture has identical adjacent passes, no
getter errors, six distinct occurrence IDs, matching source hashes, timeline
and playback 25 fps, 48 kHz, and storage under probe output. See
`evidence/baseline-preparation/` for journal, capture, settings, identity and
hashes.

Raw duration readbacks differ from requested durations: base, repeated speech
(twice) and bed each report duration 199, start 0, end 199 (requested 200);
cutaway reports duration 49, start 50, end 99 (requested 50); overlay reports
duration 125, start 75, end 200 (requested 50). Preserve these raw bounds; no
endpoint convention is assumed and no baseline correction is implied.

The operator subsequently confirmed: “Yes, None stayed set; synthetic project
only.” For this successful run, External Scripting remained None and only the
named synthetic project/generated media were touched. No R1–R5 editorial result
is recorded. Equal adjacent reads provide only bounded initial consistency
evidence.

## Native repeat preflight refusal, September 30

The installed launcher result at 18:12:39 UTC reports
`launcher-failed`: `RuntimeError: Current project is not the prepared
baseline-only state`. The full comparison differed; whether this reflects a
metadata change or edit is unknown. This is a harness preflight refusal, not
evidence of unsupported Resolve behavior. It stopped before mutation, so no
native journal exists. The preflight current-observe readback was not retained
by the code, an evidence-retention gap that prevents reconstruction of the exact
before state. A sanitized result copy and raw/published hash are retained in
`evidence/native-preflight-refusal/`.

The staged next action is read-only at stage
`baseline-state-discrepancy-read-only`; no Resolve mutation is planned for that
launch.
