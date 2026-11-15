# Resolve 21.2 API and release changes relevant to VERA

Evidence captured 2026-11-14. This appendix records vendor documentation and installed SDK declarations. It is not a behavioral qualification: neither Resolve version was launched for this research, the scripting module was not imported, and no edit was exercised.

## Versions, support and comparison limits

Installed bundles report Resolve Studio **21.1.1 (build 21.1.10010)** and **21.2.0 (build 21.2.00006)**. This Mac is a MacBookPro16,1 with an Intel Core i9. The official 21.2 Studio ReadMe requires an Apple Silicon based computer for macOS, so the 21.2 app’s universal executable slice does not make this Intel host supported. This appendix itself contains read-only documentation/declaration evidence only; any live result on this Intel Mac would describe observed compatibility on unsupported hardware, not vendor-supported operation.

The shared SDK folder at `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting` now contains 21.2's SDK. The installed 21.1.1 bundle supplies no separate complete README, stub and changelog. Thus a literal full `.pyi` diff is unavailable. The prior 21.1.1 declarations are preserved in [#477’s feasibility report](https://github.com/mbelinkie/vera-script-to-timeline/blob/main/docs/plans/issue-477-native-roll-feasibility.md) and [#489’s static audit](https://github.com/mbelinkie/vera-script-to-timeline/blob/main/docs/plans/issue-489-resolve-nongui-static-audit.md). They show no `GetPosition`, `SetPosition`, `SetLeftOffset`, `SetRightOffset` or `Timeline.MoveItems` in 21.1.1. The installed 21.2 SDK `CHANGELOG.md` documents additions and fixes, but no removals. This supports “no documented removals,” not a claim that every undocumented symbol is unchanged.

Both installed app bundles contain ResolvePython 3.14. The current vendor README says 21.1 and later use a custom Python 3.14 distribution; Python 2 was removed in 21.1. The 21.2 app’s embedded wrapper is reported byte-identical to 21.1.1, while Python library/runtime files differ and 21.2 adds `sitecustomize.py`. This is an internal runtime rebuild, not a Python major/minor change. The README says pip, Tk and IDLE are unsupported in the bundled interpreter; external Python 3.6+ remains documented. The shared SDK folder can describe whichever version was installed most recently, rather than the app currently under test.

## Documented scripting additions after 21.1.1

The release buckets below come from the installed Blackmagic `CHANGELOG.md` (last updated 2026-11-04). Signatures are transcribed from the installed 21.2 `DaVinciResolveScript.pyi`; a declaration proves what the SDK documents, not that a call works correctly in a running host.

### First appeared in 21.1.2

**Photo albums and stills.** The changelog adds album enumeration, selection, creation, updating/deletion, photo-item properties, color/composition actions and still rendering. Key declarations include:

```python
Project.GetPhotoAlbumCount() -> int
Project.GetPhotoAlbumByIndex(idx: int) -> PhotoAlbum | None  # 1-based
Project.GetCurrentPhotoAlbum() -> PhotoAlbum | None
Project.SetCurrentPhotoAlbum(photoAlbum: PhotoAlbum) -> bool
MediaPool.CreateEmptyPhotoAlbum(name: str) -> PhotoAlbum
MediaPool.CreatePhotoAlbumFromPhotos(name: str, photos: list[MediaPoolItem]) -> PhotoAlbum
MediaPool.DeletePhotoAlbums(photoAlbums: list[PhotoAlbum]) -> bool
MediaPool.AddToPhotoAlbum(photos: list[MediaPoolItem]) -> list[PhotoAlbumItem]
Project.GetPhotoQuickExportRenderPresets() -> list[str]
Project.SetPhotoRenderSettings(settings: PhotoRenderSettings) -> bool
Project.RenderPhotosWithQuickExport(
    quickExportPresetName: str, presetInfo: PhotoQuickExportRenderSettings
) -> QuickExportRenderStatus
```

The current stub declares `PhotoAlbum.GetName/SetName/GetUniqueId/GetPhotoList/GetCurrentItem/DeletePhotos/GetNodeGraph/GetMediaPoolItem/GrabStill/GrabAllStills`. `PhotoAlbumItem` declares name/ID; Fusion composition count/list/index/name access, add/delete/load/rename/import/export; media-pool access; flags and clip color; grade copy; version read/rename/delete/load/add/list; CDL and node-graph access; node-color reset; LUT export; color-group assignment/removal; burn-in preset; ratings; effects; frame export; and typed property read/write. Key signatures include `PhotoAlbumItem.ExportFrame(exportFrameOptions: ExportFrameOptions | None = None) -> ExportFrameResult`, `GetProperties() -> PhotoAlbumItemProperties`, `SetProperties(properties: PhotoAlbumItemProperties) -> bool`, `GetNodeGraph(layerIdx: int | None = None) -> Graph`, `GetVersionNameList() -> list[str]`, and `SetRatings(stars: int) -> bool`. The property type covers source transform, crop and look fields. These are a separate still/photo surface, not timeline-clip operations.

**Effects and attribute copy.**

```python
Resolve.GetEffectsList(mediaType: str | None = None) -> list[EffectInfo]
TimelineItem.AddEffect(category: str, id: str) -> Effect | None
TimelineItem.GetEffects(category: str) -> list[Effect]
TimelineItem.DeleteEffects(effects: list[Effect]) -> bool
TimelineItem.CopyAttributes(targetItems: list[TimelineItem], options: CopyAttributesOptions) -> bool
```

`mediaType` may restrict effect discovery to `video`, `photo` or `audio`; categories are `fusion`, `ofx` and `audio` where applicable. `Effect` exposes `GetInfo()`, `GetIsEnabled()`, `SetIsEnabled(enabled)`, `GetIndex()`, `SetIndex(index)` and `GetFusionComp()`. `CopyAttributesOptions` selects clip/video/audio fields and keyframe timing; its existence does not promise arbitrary third-party effect or grade preservation. Photo-album items also expose Add/Get/Delete effect calls.

**Position, offsets and timeline editing.**

```python
TimelineItem.GetLeftOffset(subframePrecision=False) -> float
TimelineItem.GetRightOffset(subframePrecision=False) -> float
TimelineItem.SetLeftOffset(offset: float, subframePrecision=False,
                           updateLinkedItems=True) -> bool
TimelineItem.SetRightOffset(offset: float, subframePrecision=False,
                            updateLinkedItems=True) -> bool
TimelineItem.GetPosition(subframePrecision=False) -> TimelineItemPosition
TimelineItem.SetPosition(position: TimelineItemPosition,
                         moveLinkedItems=True, subframePrecision=False) -> bool
Timeline.MoveItems(timelineItems: list[TimelineItem], position: TimelineItemPosition,
                   moveLinkedItems=True, subframePrecision=False) -> bool
```

The offset getters already existed in 21.1.1; the setters and position/movement calls are the additions. `TimelineItemPosition` is a `TypedDict(total=False)` with `trackType: str`, optional 1-based `trackIndex: int`, and optional `startFrame: float`; the stub says `trackType` is returned by `GetPosition` but ignored by `SetPosition` and `MoveItems`. Offset getters return maximum source extension available in frames. Setters assign the requested available handle value; the value is not an edit delta. Linked items are updated by default. `MoveItems` places the leftmost item at the requested position and moves the others relative to it; it fails if an item cannot reach its destination. Subframe precision is conditional on audio alignment preferences.

Other timeline additions are `Timeline.DeleteGaps() -> bool`, `Timeline.GetIsEnabled() -> bool`, `Timeline.SetIsEnabled(enabled: bool) -> bool`, and `TimelineItem.RippleDeleteSilence(removeSilenceOptions: RemoveSilenceOptions | None = None) -> bool`. Audio/transcription additions are `TimelineItem.AnalyzeAudioLevels(standard: str) -> AudioLevelsInfo` and `MediaPoolItem.SetTranscription(transcription: Transcription) -> bool`. `AutoCaptionSettings` adds extended-language support; languages requiring additional models can fail if those models are absent.

**Graph, frame, folder and transition additions.** The changelog lists `Graph.SetNodeLabel(nodeIndex, label)`, `GetNodeColor(nodeIndex)` and `SetNodeColor(nodeIndex, colorName)`. It lists an `applyType` extension to existing `Graph.ApplyGradeFromDRX` for all/color/sizing-only application. **The installed 21.2 stub does not declare `applyType`**; it declares `ApplyGradeFromDRX(path, gradeMode, applyToAllLayers=False, keyframeMode=Resolve.KEYFRAME_MODE_ALL)`. Treat this as a documentation/declaration mismatch and do not rely on `applyType` without a version-specific vendor signature.

`Timeline.ExportFrame(frameOffset, exportFrameOptions=None)`, `TimelineItem.ExportFrame(frameOffset, exportFrameOptions=None)` and `MediaPoolItem.ExportFrame(frameOffset, exportFrameOptions=None)` export one frame (timeline/media offsets are 0-based). The 21.1.2 `ExportFrameOptions` supports file or encoded-string output, JPG/PNG, and output path; 21.2 later extends this type with ROI, size and quality fields (below). `MediaPoolItem.GetParentFolder()` and `Folder.GetParentFolder()` expose folder hierarchy. Transition support uses existing `TimelineItem.GetProperty` / `SetProperty` with `TransitionType`, `TransitionCategory`, `TransitionDuration` and `TransitionAlignment` keys; the changelog does not add a separate transition API method here.

The 21.1.2 changelog also records fixes for keyframe-mode access from any page, `AppendToTimeline` frame ranges for OGraf/Lottie clips, `Project.RenderWithQuickExport`, and `ProjectManager.ArchiveProject`. The 21.1.2 product ReadMe separately notes improved edit-point selection, template controls, up to 4× OGraf playback and improved Intel-graphics IntelliSearch/AI performance.

### First appeared in 21.2

**Extras Download Manager.**

```python
Resolve.GetExtrasPackages() -> list[ExtrasPackageInfo]
Resolve.InstallExtrasPackage(name: str) -> bool
Resolve.UninstallExtrasPackage(name: str) -> bool
```

`ExtrasPackageInfo` includes name, description, status, progress, download size and installed size. Install/uninstall queue work and may involve downloads, disk use, licensing or optional models; the calls are not read-only. A read-only package inventory could inform readiness checks, but VERA should not install or remove packages automatically.

**Contact sheets and frame options.** The new methods are:

```python
Timeline.ExportThumbnails(frames: list[int | ThumbnailFrame],
                          exportThumbnailsOptions=None) -> ExportThumbnailsResult
TimelineItem.ExportThumbnails(frames: list[int | ThumbnailFrame],
                              exportThumbnailsOptions=None) -> ExportThumbnailsResult
MediaPoolItem.ExportThumbnails(frames: list[int | ThumbnailFrame],
                               exportThumbnailsOptions=None) -> ExportThumbnailsResult
PhotoAlbum.ExportThumbnails(photoIndices: list[int],
                            exportThumbnailsOptions=None) -> ExportThumbnailsResult
```

Timeline/item/media frame offsets are 0-based. Photo-album indices are 1-based. `ThumbnailFrame` supports `frameOffset` plus a visible label. `ExportThumbnailsOptions` supports file/encoded-string output, JPG/PNG, `filePath`, JPEG quality and `maxDimension`; the latter limits the **whole sheet**, with its pixel budget split across cells. Results can include success/error, encoded image data, sheet dimensions and grid cell counts.

The 21.2 `ExportFrameOptions` type adds normalized `roiX`, `roiY`, `roiWidth`, `roiHeight`, plus `maxDimension` and JPEG `quality`. ROI is documented for JPG/PNG, with per-axis fractions. These APIs export still images/contact sheets; they are not timeline render APIs.

**Auto-color and color readback.** `TimelineItem` and `PhotoAlbumItem` each add `ApplyAutoColor() -> bool`, `SetAutoColorEnabled(enabled: bool) -> bool`, `GetAutoColorEnabled() -> bool | None` and `ClearAutoColor() -> bool`. The docs say applying auto-color replaces a previous auto-color result and clears legacy auto-color values; it can alter grades, so it is not a default preservation operation. Both item types add `GetCDL(nodeIndex: int) -> CDL`. `Graph.GetNodeEnabled(nodeIndex: int) -> bool` adds node enabled-state readback.

**Project playback frame-rate setting.** The changelog says `timelinePlaybackFrameRate` can be queried/set through the existing `Project.SetSetting` and `Project.SetSettings` calls. Setting `timelineFrameRate` now also updates `timelinePlaybackFrameRate`, matching UI behavior. This is a behavior/settings expansion, not a new method.

No 21.2 changelog entry adds a roll or paired-edit method.

## Native roll: actual Blackmagic support response

Timeline [#390](https://github.com/mbelinkie/vera-script-to-timeline/issues/390) concerns Research snapshots. The roll history is #477/#489 and [#490's Nov. 12 support reply](https://github.com/mbelinkie/vera-script-to-timeline/issues/490#issuecomment-6826230215): Blackmagic case **DEV-12324**, from Brendan Dower.

Blackmagic confirms no supported in-place sequence in 21.1.1; the new setters/movers start in 21.1.2. Offsets are absolute available handles. For positive `n`, its proposed sequence is `R.SetLeftOffset(R.GetLeftOffset() + n)`, then `L.SetRightOffset(L.GetRightOffset() - n)`: shrink before extending to avoid overlap. Both IDs should persist, subject to save/reopen verification. B's source-in advances normally; preserving it would be a different edit. Reverse-direction arithmetic needs independent verification rather than assuming the signed example is correct.

`AppendToTimeline` creates new items/IDs; `FinalizeTake` changes selected media rather than position. Still/placeholder handle behavior remains conditional. This is vendor guidance, not native proof. #490 remains closed/not planned; #564's direct Producer request authorizes this investigation.

## VERA relevance

The current product build path in [#517](https://github.com/mbelinkie/vera-script-to-timeline/issues/517) uses `build_compiler_bridge.py`, `v2_package.build_v2_package`, and `studio_spike.PublicResolveAdapter` with `workflow_v2` overrides; it targets a new project or new timeline in a named project. [#519](https://github.com/mbelinkie/vera-script-to-timeline/issues/519) owns per-row readback outcomes of unchanged, changed with proposal, or edit not understood. The vendor offset recipe may inform a future product decision; it does not itself implement VERA's update/readback contract.

Most promising declared additions for future work are per-edge offsets/position, effect discovery and selective attribute copying, and CDL/node-enabled readback. Album, auto-color and optional-model APIs cover workflows VERA may not use. Frame/contact-sheet export is preview/evidence support only. No API declaration alone establishes source retention, linked-item behavior, persistent UIDs or saved geometry.

## Release-note summary (21.2 product features, under 200 words)

Blackmagic’s 21.2 Studio ReadMe adds MacBook Pro PROLED XDR touch-screen support; Gen 6 LUTs and ResolveFX False Color updates; source timecode retention for extracted audio; multicam/source-viewer editing improvements; timeline edit-selection and compound-clip actions; persistent edit-menu choices; and PNG EXIF metadata. AI assistant changes add improved color/Fusion capability, optional Extras downloads, frame exports and thumbnail grids, but do not by themselves expose unattended VERA operations. Fixes cover network-drive MXF audio, MP3-only render speed, AAF clip/timecode issues, OGraf loading/timeouts/memory, XDCAM and H.265 issues, collaboration source-track changes, OpenFX and MultiText behavior, render-in-place handles, audio preferences, WAV metadata/channel ordering, DNG decoding, Text+ controls, Fusion scripting references, and general performance/stability. Relevance depends on VERA’s actual media and workflow; none changes the documented roll API or proves timeline-edit behavior.

## Sources

- Blackmagic Design, [DaVinci Resolve Studio 21.2 ReadMe](https://www.blackmagicdesign.com/support/content/readme/630fd2cb208a46df9493de661a76628a), online date 2026-11-04; installed copy updated 2026-11-05. Includes macOS hardware requirements and product release changes.
- Blackmagic Design, [DaVinci Resolve Studio 21.1.2 ReadMe](https://www.blackmagicdesign.com/support/content/readme/1dcfa6f38ebc4031a3a8561eea3aeee3), updated 2026-10-23.
- Blackmagic Design, [official Resolve release-note index](https://www.blackmagicdesign.com/support/partial/llm-release-notes-summary).
- Installed vendor SDK: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/CHANGELOG.md`, `README.md`, and `DaVinciResolveScript.pyi` (21.2 copy).
- Blackmagic Developer Support response DEV-12324, preserved on [VERA issue #490 comment](https://github.com/mbelinkie/vera-script-to-timeline/issues/490#issuecomment-6826230215), Nov. 12, 2026.
- Prior 21.1.1 declarations/context: [#477 report](https://github.com/mbelinkie/vera-script-to-timeline/blob/main/docs/plans/issue-477-native-roll-feasibility.md) and [#489 report](https://github.com/mbelinkie/vera-script-to-timeline/blob/main/docs/plans/issue-489-resolve-nongui-static-audit.md).
