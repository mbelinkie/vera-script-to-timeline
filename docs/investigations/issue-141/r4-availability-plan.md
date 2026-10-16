# Issue 141 — bounded R4 availability setup plan

## Scope

Prepare one isolated availability experiment using only the approved generated `relink/base.mov` copy. Create one pool item only if Resolve returns a new, provably distinct MediaPool UID; create one `VERA 141 R4 availability` timeline and append exactly one V1 occurrence. This is setup only: no unlink, relink, wrong-byte replacement, occurrence removal, or restoration in this action. External Scripting stays `None`; use only the existing injected Workflow Integration path in the named disposable project.

No production contract, fixture, golden, generated type, dependency, source file, existing timeline, or editorial case changes. No new dependency. Acceptance is external evidence from Resolve, not an agent report alone.

## Exact checkpoint and source guards

Require the operator's existing None/synthetic-only attestation and the exact open project identity `97037b5a-aab6-48a9-b7e4-4c5697ae10a0`, Studio 21.1.0.14. Require the saved matrix checkpoint `capture-20260930T223313.312609Z-saved.json`, raw SHA-256 `a29402d405ab8cf1bc1abedd4c1ed0c479e983e2ef3ba6fc41d1c2389d6d36d2`. It contains exactly these timelines:

- `VERA 141 Batched Matrix`, UID `29ae8331-b86e-4041-a548-960695cc7b24` (114 occurrences, 19 sections)
- `VERA 141 Baseline`, UID `88f7923d-55a7-471f-b09b-cf10f9fae8ad`
- `VERA 141 R1 identity`, UID `aa2b8e36-83bd-4292-9e33-217c00ca192f`

The existing base pool item UID is `9202163a-8381-43e6-9157-3a60f35c6f79`; it is shared by existing timelines. The approved source manifest records both `base.mov` and `relink/base.mov` at SHA-256 `c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942` and 792,989 bytes. Verify only this allowlisted file against that manifest. Do not use the wrong-byte candidate.

## Guarded sequence

1. Resolve current project, version, timeline set, settings, folder tree and all media-pool items read-only. Recursively traverse `MediaPool.GetRootFolder()` using each `Folder.GetClipList()` and `GetSubFolderList()`; collect every folder UID and every item UID, name and `GetClipProperty()` map/path. Hash-check the pinned saved checkpoint file, then compare the live preflight semantically with that checkpoint while ignoring only `capturedAt`; require pinned project/timeline IDs and source UIDs and no pre-existing timeline named `VERA 141 R4 availability`. Keep a complete two-pass pre-capture; stop on missing, changed, inconsistent, or unbounded reads.
2. Before calling `ImportMedia`, journal its exact request. `MediaPool.ImportMedia([allowlisted_relink_path])` must return exactly one item. Read back its UID, name and file path/properties; re-enumerate all folders. Require its UID was absent from the complete before set and now appears exactly once, the resolved path is the expected generated copy, and the source file hash still matches the manifest. If the returned item is the existing shared UID, any UID collides, result count differs, or the path/hash/readback is ambiguous, retain the partial state and stop before timeline creation. Import deduplication behavior is undocumented and untested; never assume a new UID from a different path.
3. After the new UID passes, journal and call `MediaPool.CreateEmptyTimeline("VERA 141 R4 availability")`. Require non-null return, exact unique name, new timeline UID, and selection readback via `Project.SetCurrentTimeline(timeline)` / `GetCurrentTimeline()`. Capture and verify the same original three timelines remain present with their prior IDs and captured contents. Selection may move to the new timeline; do not edit the originals.
4. Journal one `MediaPool.AppendToTimeline` request with the new pool-item object only: `{mediaPoolItem: imported, startFrame: 0, endFrame: 199, mediaType: 1, trackIndex: 1, recordFrame: 0}`. Require exactly one returned TimelineItem, one V1 item in the new timeline, source UID equal to the newly imported UID, and source/record range readback of 0–199 and duration 199 (the already calibrated base-video getter convention). If the imported clip duration/bounds are not exactly 200 frames at the captured 25 fps, stop; do not shorten, extend, or guess. No other track/item is allowed.
5. Save only after all guards pass, journal the `SaveProject` request/return, and retain two equal-adjacent after reads, full folder/pool inventory and timeline captures. Verify the three old timelines' contents are unchanged, apart from any explicitly attributable API `Usage` counters; the new item must not alter the old source UID's state. Retain raw captures locally, publish path-redacted evidence with raw hashes, and record every request/return/failure in order. Preserve partial results; no automatic cleanup/retry.

## API evidence and limits

Installed Resolve 21.1 stubs document `MediaPool.ImportMedia(clipInfos: list[ImportClipInfo]) -> list[MediaPoolItem]`; `ImportClipInfo.FilePath` is the source path. They also document `Folder.GetClipList() -> list[MediaPoolItem]`, `Folder.GetSubFolderList() -> list[Folder]`, `MediaPool.GetRootFolder() -> Folder`, `MediaPool.CreateEmptyTimeline(name: str) -> Timeline`, `Project.SetCurrentTimeline(timeline: Timeline) -> bool`, `Project.GetCurrentTimeline() -> Timeline`, `MediaPool.AppendToTimeline(clipInfos: list[AppendClipInfo]) -> list[TimelineItem]`, `MediaPoolItem.GetUniqueId() -> str`, `MediaPoolItem.GetClipProperty(propertyName: str | None = None) -> str | ClipProperties`, `TimelineItem.GetUniqueId() -> str`, and `TimelineItem.GetMediaPoolItem() -> MediaPoolItem | None`. README says ImportMedia imports paths into the current Media Pool folder and returns created MediaPoolItems. It does not promise deduplication, unique identity, a particular online-status key, or hash validation. The probe must independently check these conditions before further mutations.

## Later actions stay separate

Only after this setup has been accepted, plan separate before/after snapshots and separately reviewed audited native actions and the authorized fixed-menu launch for: unlink the new, distinct pool item; relink that same item to its matching generated folder and verify its UID/path/hash; and remove the one timeline occurrence only on a separate duplicate. Never unlink the shared original UID. Do not stage the checklist's same-locator wrong-byte replacement until its own audited, reversible mechanism and evidence exist. A track disappearance proves neither pool-item nor logical-row deletion.

## Minimal fake acceptance scope

One stdlib-only fake harness should assert (a) exact-checkpoint/project/timeline/hash refusal before mutations, (b) recursive pool UID enumeration and refusal when import is empty, multiple, deduplicated, colliding, or path/hash-mismatched, (c) no CreateEmptyTimeline/AppendToTimeline/SaveProject call after any refusal, (d) successful exact sequence `ImportMedia → CreateEmptyTimeline → SetCurrentTimeline → AppendToTimeline → SaveProject` with one imported UID and one V1 occurrence, and (e) preservation of all three original timeline IDs/content. Keep fixtures inline and limited to the fake API boundary; no new test framework or production helper abstraction.

## Native import-form refusal and read-only postflight

The documented FilePath-dictionary import form returned no item on the exact
21.1.0 build14 project, before any timeline creation. Retained read-only
postflight proves both pool inventories and all three timeline contents exactly
unchanged. The next separately bound setup uses the README path-list form,
already successfully exercised in this project preparation. This is not
automatic retry or a general import-unavailable conclusion. Timeline pool
proxies are mapped by Timeline.GetMediaPoolItem UID, not timeline UID or name.
