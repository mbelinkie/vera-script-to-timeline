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
