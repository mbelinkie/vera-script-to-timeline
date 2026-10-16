# Claude checkpoint 4 — finished host stages and audio boundary findings

Continue the independent #144 review. Read-only repository files only; no edits,
claims, tests, native actions, credentials, private media, providers, connectors
or additional agents. Producer authorized direct Claude reviews through the CLI.
Do not treat the review as Producer or external acceptance.

Read the pinned finished segment:

- `python/vera_timeline_agent/roundtrip_build.py`
- `tests/test_issue144_prepared_build.py`
- `docs/investigations/issue-144/checkpoint-03-disposition.md`
- `docs/investigations/issue-144/measure-retained-w1.py`
- `docs/investigations/issue-144/retained-w1-boundary-measurements.json`
- Current `docs/plans/issue-144-roundtrip-harness.md` and accepted #34/#35/package
  APIs as needed. Earlier completed reviews are retained alongside this prompt.

Host segment: 18 new tests pass on Node24.19.0/Python3.12.14. Initial combined
35-test run passed, including 23 unchanged package/Studio/job regressions; then
two new tamper cases passed. Ruff and strict mypy pass. Full validation outstanding.
Five real core stages use literal strict operator files, immutable snapshots,
verify-only speech/media, actual compiler entry and exact output hashes, actual
package writer/verifier and unchanged durable job API. No default native adapter.
Native stages wait explicitly for #145; render/upload rows are skipped. New
revision preparation must generate fresh build IDs before rebuild. It is not a
finished harness, and no positive omission rebuild occurred.

Review concrete failures around:

1. Strict parsing, immutable snapshot and source/media/lock binding, output
   tampering and interrupted/replayed stages. Can a changed input, malformed
   compiler response, stale intermediate or different existing package pass?
2. Verify-only speech mapping, hash/text/revision/PCM extent checks, missing or
   duplicate materializations; any path that could reach a paid provider?
3. Existing job semantics: all five core stages, precise successful receipts,
   evidence labels, skipped render/upload and explicit native wait. Do receipts
   overclaim any verification? Suggest only bounded corrections.

Audio: new boundary probes show quarter-word head/tail and native-frame-boundary
residue, near-threshold quiet half-word overlays and 10 samples. Some injected
residue passes proposed RMS limits, so those limits alone cannot establish
arbitrary speech absence. Do not tune thresholds until these pass as negatives.
Original W1 supports are fixture-generator declared. The overlay in your prior
review was half-word, not full-word; its precise indices are in the reports.

Proposed bounded next gate: only public hash-bound W1 sources and supports under
known constant supported routing/normal speed; complete rendered PCM + full
observed route inventory; exact full-target support excision and neighbor
preservation; original-reference gains reused; numeric reconstruction is a
consistency check, not a general speech classifier. Unknown routes/effects/gain
automation/new quiet speech input or incomplete support/calibration remains
uncertain. The linked-cut retained file is a positive; picture-only/disabled-A1
and partial-support cases must refuse. Synthetic adulterated renders cannot be
accepted merely because residual is within tolerance.

Is this genuinely sufficient for #144's retained-positive gate, or does it still
leave a material unsupported inference? Give the smallest concrete gate that
handles the retained positive and required negatives honestly. If source/render
hash allowlisting would merely replay a known verdict without a real gate,
call that out. Actual #145 input needs a separately proved supported profile;
no automatic generalization or lower-coverage positive substitute.

Next native segment (plan review): explicit injected adapter_factory/local_facts
for tests invokes unchanged run_studio_assembly on the real verified package.
Persist intent before effects; retain assembly result and verification facts;
missing result plus existing intent stays waiting. Fresh native verification can
reuse the current adapter immediately; process recovery must use a separate
read-only rehydration/UID/manifest map, not creation-time maps. No retry of lost
creation response. WI capture/link/render must validate target and only expose
bounded named actions on a disposable proof. Confirm the smallest safe seam
before we wire this segment. Your previous reference to media-pool
GetSubFolderList/GetClipList does not prove project-manager tree traversal APIs;
keep recovery waiting unless actual project-manager APIs are verified.

Return severity, concrete location/failure example and smallest fix. Clearly
state whether host native injection can proceed, and which audio claims/tests
must wait. Note what you could not verify. Don't rewrite the entire architecture.
