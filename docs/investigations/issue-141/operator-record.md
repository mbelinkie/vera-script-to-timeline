# Issue 141 — operator record

## Standing operator confirmation

After the successful native duplication, the operator confirmed the requested
None/synthetic-only scope and directed us to stop repeated scripting-mode
questions: “yes, you can stop asking. I'm never gonna switch it from none.”
Retain this standing confirmation for the authorized investigation. Do not ask
the mode question after each launch. Config attestation is not API readback.

## Native cache restoration and duplication, September 30

At 20:44:38 UTC the injected action succeeded. The operator reported that the
project remained open. The cache-restoration capture matches both pinned raw
baseline passes exactly. DuplicateTimeline created `VERA 141 R1 identity`, ID
`aa2b8e36-83bd-4292-9e33-217c00ca192f`; selection readback matches that ID and
SaveProject returned true. Four complete captures have equal adjacent reads.
See `evidence/native-duplicate-success/` for immutable raw hashes, redacted
captures, journal, launcher result and comparison.

All six copied occurrence UIDs are new; the five distinct media UIDs are shared.
Track/range/media/item-enable/marker signatures and marker custom data match.
This is one observed duplicate, not editorial lineage or universal ID survival.

The baseline's subsequent readback differs: all six track-enabled getter values
are false rather than true, Usage values increased, and eight audio-property
keys are absent on each of three audio items. No explicit track-enable or
audio-property setter appears in the journal. Cause remains unknown; absence
does not establish disabled effects or changed audio. Compare selected versus
inactive timeline context before accepting those getters as edit evidence.

## Duplicate-only named-project refusal, September 30

The operator reported, “I ran VERA Issue 141 Observation, it didnt seem to do
anything.” The 20:11:04 UTC launcher result reports the named-project guard
refusal, before capture or native mutation. See
`evidence/native-duplicate-project-refusal/` for the result and hashes. Whether
the exact synthetic project was manually reopened with its baseline visible is
awaiting operator clarification. None/synthetic-only attestation for this launch
is pending. No reopened-state or duplication observation is inferred.

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


## Read-only quiet repeat, September 30

At 18:22:47 UTC, the installed observation captured the named project without
mutation. `evidence/quiet-repeat/` retains the redacted capture, interpretation,
and raw/published hashes. Both adjacent reads were equal, with no getter errors
or capture failure; each raw pass matches the corresponding baseline pass
exactly; only the outer `capturedAt` and `stage` envelope values differ between
launcher runs. The launcher result path is redacted in the retained publication.
The 18:12:39 preflight refusal remains unexplained because it had no retained capture. This
quiet repeat does not prove atomicity, close/reopen behavior, or any R1–R5 edit.
The installed action is now staged for the native repeat batch; no later result
is recorded here.


## Native close refusal, September 30

At 19:42:33 UTC, the retained journal records `SaveProject` and `CloseProject`
returning true. After close, `GetCurrentProject` returned
`fedceab7-8706-4b83-9ffe-fb77c65f0dbe`, different from the approved synthetic
project ID `97037b5a-aab6-48a9-b7e4-4c5697ae10a0`. The launcher refused before
`LoadProject` or `DuplicateTimeline`. No inspection or mutation of the unexpected
project is recorded. The preflight capture has two equal adjacent passes, no
getter errors or capture failure, and each raw pass exactly matches the
corresponding baseline pass.

The operator reported: “It closed the project but did not seem to reopen
anything.” The operator also confirmed: “Yes, None stayed set; synthetic project
only.” Evidence and sanitized result are retained in `evidence/native-close-refusal/`.
This establishes neither automatic reopen nor that `LoadProject` works; the
unexpected project is not assumed empty/default. The earlier 18:12:39 refusal
remains separately unexplained. The next attempt requires manually reopening
only the exact synthetic project, with the baseline unchanged, before launching
once when the parent stages `native-duplicate`. That result is not yet live.


## Manual reopen capture and cache-setting refusal, September 30

At 20:17:34 UTC, the operator said: “I reopened Synthetic Probe project and ran
it but no effect. Check it?” The pre-duplicate capture has two equal adjacent
reads, no getter errors or capture failure, and the approved synthetic project
ID. Against the original baseline, only `perfCacheClipsLocation` differs in both
passes: the project-level and timeline-level settings return the string
`CacheClip` instead of the baseline-owned cache path. Its resolved target is unknown.
IDs, ranges, markers/custom data, other item properties and source hashes match
in the full raw comparison. The identity guard refused before duplication, and no native journal
or mutation resulted. See `evidence/native-reopen-cache-refusal/` for the
redacted capture/result and raw/published hashes.

This retains one manual reopen readback, not proof that the scripting API's
`LoadProject` works. The operator confirmed for this run: “Yes, None stayed set;
synthetic project only.” Exact-cache-only restoration subsequently ran
successfully in the native duplicate batch above. The earlier 18:12 and 19:42 refusals remain separately
recorded and unexplained where applicable.
