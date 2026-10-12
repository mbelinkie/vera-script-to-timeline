# #174 acceptance evidence

Exact implementation commit is recorded in `acceptance.json`. Tested source
hashes are retained in `checks-source-hashes.json`; every current candidate
source hash matches. `checks-final.json` records all sequential stage exits 0.

| Criterion | Actual retained evidence | Result |
| --- | --- | --- |
| Accepted-rate matrix, same-rate reuse, O/P0/H, endpoints/handles, AAC/PCM mono/stereo 44.1/48k | `focused-final.log`: 64 passed; URI/reuse follow-up: 8 passed; 15 installed-tool cases in `qualification.json`, per-case receipts under `out/issue174/r2/qualification` | Pass |
| Refusals: VFR/false labels, unsupported media, stale hashes, tool/profile policy, shortage | Real-tool refusal/recovery tests included in focused/full gates | Pass |
| Atomic interruption/cancellation/retry/leases/reuse, deterministic bytes | Recovery tests; independently prepared picture/audio hashes and exact reuse in qualification records | Pass |
| Exact picture sampling/count/cadence and half-open endpoints; ≤one 48k sample audio endpoints; ≤1ms sync residual/drift | Actual decoded ordinal oracle, full decoded PTS probes, rational geometry, sample counts and signed source/output peak measurements; verifier checked 63 artifact hashes. Maximum residual 0.06264172335600907ms; maximum drift 0.0677437641723356ms | Pass |
| Tool/build/platform/profile/source/output hashes, mappings, commands, measured filter route | Immutable per-case receipts, qualification index, `sampling-route.json`; adapter source/binary/direct-library hashes pinned | Pass |
| Issue-owned synthetic evidence; frozen bytes; required repository gate | Baseline diff unchanged for contracts, generated types, fixtures/goldens/accepted tests and package/locks. Fast gate 323 Python tests; final full gate 563 in 3061.49s, all lint/types/generated/TypeScript checks pass | Pass |
| Mandatory exact-revision Claude antagonist review | Retain review output, exit, revision, findings/dispositions and any re-review beside `acceptance.json` | Pending |
| External operator visible judder/quality and audible artifact judgment | Concrete playback artifacts and operator checklist in `README.md`; actual FFmpeg evidence does not supply subjective perception | Pending human judgment |

No original/private media was read or modified. No native Studio qualification,
acquisition, composition, upload or production-project operation occurred.
CI clean installation repair remains separately owned by #193; #174 did not
alter its package or lockfile.
