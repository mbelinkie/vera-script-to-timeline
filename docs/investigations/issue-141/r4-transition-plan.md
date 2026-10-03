# Issue 141 — bounded R4 unlink/relink transition plan

## Scope and current status

Plan one unlink and one relink of the newly imported, same-byte synthetic
`relink/base.mov` item in the isolated `VERA 141 R4 availability` timeline.
The setup must have retained verified native evidence. This draft is not
run-ready and does not implement a module. No source replacement, wrong-byte locator,
clip/timeline deletion, import retry, media-pool cleanup, or change to the
original shared base item is in scope.

The setup result—not this plan—must provide the exact new media-pool item UID,
availability timeline UID, and appended occurrence UID. Require that the new
pool UID differs from the original shared base UID
`9202163a-8381-43e6-9157-3a60f35c6f79` and appears exactly once in a complete
recursive pool inventory. If the retained setup result does not prove those
identities and the expected path, stop without calling either transition API.

## Preconditions

1. Require the operator's External Scripting `None` and synthetic-only
   attestation; Studio 21.1.0 build 14; project UID
   `97037b5a-aab6-48a9-b7e4-4c5697ae10a0`; and the accepted saved checkpoint
   `capture-20260930T223313.312609Z-saved.json` with raw SHA-256
   `a29402d405ab8cf1bc1abedd4c1ed0c479e983e2ef3ba6fc41d1c2389d6d36d2`.
   Require two equal fresh captures before each state transition. Compare the
   three original timelines in the same selected context against the retained
   setup capture; preserve the saved Matrix checkpoint as the historical source
   of IDs/markers/ranges rather than equating getters across selection contexts.
   Require the newly added availability timeline/item/occurrence and the full
   post-setup inventory to match the verified setup result exactly. The setup
   result's exact new UIDs are mandatory inputs to this plan's execution.
2. Resolve the imported item by its exact UID from that retained result, then
   verify name `base.mov`, expected media path under the approved
   `relink/` directory, and the complete `GetClipProperty()` map. Verify the
   on-disk `relink/` directory is owned and non-symlinked, and contains exactly
   the approved regular non-symlink `base.mov` candidate. Require that file to
   have SHA-256
   `c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942` and
   792,989 bytes, as pinned by the manifest. Do not use `wrong/base.mov`.
3. Traverse every Media Pool folder using `GetRootFolder()`,
   `GetSubFolderList()`, and `GetClipList()`. Retain the full folder and item
   inventory, including every UID, name, and full `GetClipProperty()` map.
   Require the new UID occurs once, the original shared base UID remains
   present with its original properties, and the isolated timeline contains
   exactly the one expected V1 occurrence referencing the new UID. Capture all
   three original timelines and the isolated timeline; no other occurrence or
   project may change.
4. Capture and journal the project identity, selected timeline, exact item and
   occurrence identities, source locator, `File Name`, `File Path`, `Online
   Status`, and source hash. Do not infer availability from a method return or
   from matching file bytes alone. If `Online Status` is absent, ambiguous, or
   inconsistent with an retained Resolve availability evidence, stop before unlinking.

## Two transitions and verified return

For each call, journal the exact UID list, folder path if applicable, timestamp,
return value or exception, and two adjacent post-call captures. Recheck project,
build, selected isolated timeline, and exact item UID immediately before the
call. The only allowed transition calls are:

1. Call `MediaPool.UnlinkClips([new_item])` once, with a one-element list
   containing only the distinct new item. Do not include the original UID.
   Read back the complete recursive pool inventory, every timeline's
   occurrences/contents, and the new item's identity/properties. Claim an
   offline transition only if Resolve's `Online Status` explicitly reports
   offline with any separately retained output/UI evidence identified, while the same new pool
   UID and same timeline occurrence UID remain present. The boolean return and
   unchanged source-file hash are recorded but are not proof of offline state.
   If the item or occurrence identity changes, the original item changes, or
   offline state is not established, stop and retain the partial evidence.
2. Only after the offline state and unchanged context are verified, call
   `MediaPool.RelinkClips([new_item], relink_folder)` once, where
   `relink_folder` is the exact approved parent directory containing
   `relink/base.mov`. The API targets media-pool clips and takes a folder path;
   it does not take a file path. Read back the exact same item UID, the expected
   `File Name` and full `File Path`, `Online Status == "Online"`, full item
   properties, timeline occurrence ID/source UID/ranges, and complete pool
   and timeline inventory. Independently re-hash the approved file and require
   the pinned hash and byte length. Do not infer successful relink from the
   return value or file hash alone.

If unlink errors or returns false, do not claim the unlink succeeded or
continue the planned test. If readback proves the same item is offline and the
context is still exact, one explicitly journaled recovery relink may be used to
restore it; if readback proves it remains online, stop without relinking. If
state is ambiguous, make no further API call. If the planned relink errors or
returns false, do not retry; record its post-call state, and claim restoration
only if explicit online/path/UID/timeline readbacks prove it. A recovery
`RelinkClips` call is allowed only if the exact imported UID, project, selected
isolated timeline, pinned preflight locator, on-disk manifest hash, and
operator context still match. The offline item's property path may be blank;
it must not identify a different locator. Journal recovery separately. If
those guards fail, make no further API call and leave the partial project
intact for operator recovery. Never delete the imported item or its occurrence
as cleanup.

After both transitions are verified, recheck project, build, and selected
availability timeline, then save only this synthetic project with
`ProjectManager.SaveProject(project)` and verify its return. Retain two equal
adjacent final captures proving the isolated item is online again at the
approved relink-copy path, the same one V1 occurrence still references it, the
original shared base UID and the three original timelines are unchanged, and
the full pool inventory differs from accepted setup only by the expected
availability/path fields for the distinct imported item. If save or final
verification fails, preserve the evidence and do not claim restoration.

## API basis and limits

Installed Resolve 21.1 `DaVinciResolveScript.pyi` documents:

- `MediaPool.UnlinkClips(clips: list[MediaPoolItem]) -> bool`, described as
  unlinking specified pool clips.
- `MediaPool.RelinkClips(clips: list[MediaPoolItem], folderPath: str) -> bool`,
  described as updating the specified pool clips' folder location.
- `MediaPoolItem.GetUniqueId()`, `GetName()`, and `GetClipProperty()`; its
  `ClipProperties` includes `File Name`, `File Path`, and `Online Status`.
- `Folder.GetClipList()`, `GetSubFolderList()`, and `GetUniqueId()` for full
  inventory traversal.

The signatures and brief descriptions do not promise how unlink affects the
timeline occurrence, how relink chooses among same-named files, or what a true
return says about actual availability. The explicit identity, path, online
status, occurrence, inventory, and hash readbacks above are required evidence;
anything Resolve does not expose remains unsupported.

## Retained evidence and acceptance

Keep a timestamped ordered journal, complete before/unlinked/relinked/final
pool inventories and timeline captures, exact request/return/error records,
manifest and media hashes, and path-redacted copies plus raw-file hashes. Retained native
readbacks must prove the distinct imported item alone was targeted, the shared
original stayed unchanged, and the final state is restored. The standing
None/synthetic-only operator attestation persists; do not ask it again. An agent
self-report alone does not accept this External slice.

Sources: installed stubs at `/Library/Application Support/Blackmagic
Design/DaVinci Resolve/Developer/Scripting/DaVinciResolveScript.pyi` (SHA-256
`00078fa1256851b9807621a4eea5e670f4266b0e7003763cba4a62655543f0ec`; methods
near lines 1939–1943, clip properties near 179–193 and 2050–2057, folder methods
near 2597–2612); `docs/investigations/issue-141/r4-availability-plan.md` for
the accepted setup boundary and media hash; and
`docs/investigations/issue-141/operator-checklist.md` R4 for the intended
unlink/relink evidence and distinction between offline and deleted.

No Resolve calls were made while preparing this plan. No source, fixture,
contract, or accepted test was changed.
