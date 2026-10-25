# Guarded Studio runs beyond the caller window

On 2026-10-25, a fresh attested disposable target from the retained verified
#275 package completed the normal `VERA Delivery v2.py` build on the Intel Mac
with Resolve Studio 21.1.1. No provider, aligner, rendering or upload was run.

| Check | Observed result |
| --- | --- |
| Parent reservation to worker exit | **250.95 seconds** |
| Reconnection after the old 60-second window | Same operation observed live at 71.85, 102.70 and 204.74 seconds |
| Final normal product result | `verified`, `verified: true`, zero discrepancies |
| Save/close/reopen | Passed the normal UID, settings, media and event readback guards |
| Independent final readback | One matching timeline, 11 timeline events, 11 imported media entries, no render active |
| Repeating parent start after completion | Same terminal result and elapsed time; no new target |

The elapsed time includes the child's connection, guarded bootstrap, package
rechecks, assembly and save/reopen verification. Attestation/release/request
preparation and developer work are excluded. No competing tests or media
workload ran during this successful operation. This is one observation for the
selected short package, not a full-video forecast or the three-case #275
benchmark.

The existing machine's local scripting connection is explicitly declared by
`--external-scripting-local`; preferences were unchanged. The original injected
request route continues to declare `--external-scripting-none`. New-project v2
preflight now accepts an empty current project on the Edit page; the target's
actual timeline APIs and contents are checked during creation and verification.

An earlier parent attempt stopped safely in preflight after 26.04 seconds:
Resolve had opened on the Media page with no timeline. It created no target;
its refusal and evidence are retained. The two legacy #275 attempts were also
preserved. On inspection, one had eventually produced a mutation-failure result
about 275 seconds after its native start; the other retained only its start
record. Neither is counted as a successful run or silently resumed.

See [the supported invocation and state meanings](../resolve-parent-delivery-v2.md).
The parent reserves a request once, uses worker-held file locks for liveness,
and matches the dispatch identity plus normal start/result/hash records before
reporting terminal completion. A host-wide active reservation refuses another
request while the previous outcome is live or unresolved. Waiting and status
never dispatch or retry a mutation. Private source text, media, paths, target
identities, request digests and detailed records remain outside the repository.

#275 retains ownership of its separate benchmark and remains open until its
own acceptance criteria are met.
