# #477 — Supported non-GUI same-UID picture roll: feasibility evidence

## Phase 1: read-only SDK evidence (2026-11-08)

**Status: no supported same-UID roll has been proved.** This is a declaration and
documentation inventory, **not** an execution, readback, native acceptance or
permission to edit. The installed Studio version is **21.1.1 build 10**. Its
official, installed SDK does not declare the newer trim/position setters.
Published *secondary* 21.1.2 and 21.2 documentation introduces candidate
setters but describes no atomic two-item roll or UID-preservation guarantee.

### Acquisition, identity and evidence classes

- Repository baseline: `origin/main` commit `56f09372` in the isolated #477
  worktree. Scope and acceptance: [#477](https://github.com/mbelinkie/vera-script-to-timeline/issues/477),
  with #473 a blocked parent, **not** an added dependency.
- Acquired by **read-only Mac bridge shell commands** against the Mac's actual
  `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/`
  directory. Only `find`, `shasum -a 256`, `wc -l`, `head`, `grep`, and `sed`
  were used on the SDK, and `ls`/`plutil`/`shasum` on the app's on-disk
  `Info.plist`. No SDK imports, Resolve process connection, `scriptapp`, `dir()`
  calls, project selection, target inspection or native mutation were made.
- App identity came from the existing on-disk
  `/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Info.plist`:
  `CFBundleShortVersionString = 21.1.1`, `CFBundleVersion = 21.1.10010`.
  This is evidence about the installed **bundle**, not a live process/version
  handshake. No running-app version, runtime method availability, or edition
  was independently queried. The VERA knowledge guide records previous runs
  of Studio 21.1.1 build 10, but those are distinct historical evidence.
- Per `docs/RESOLVE_KNOWLEDGE_GUIDE.md`, **API** documentation, **synthetic**
  tests, **native** authenticated readback and **product** delivery are distinct
  evidence classes. Everything below is API/static evidence, except the
  explicitly labeled third-party anecdote. `sameUidRollNativeVerified = false`
  and `mayExecuteNativeEdit = false` for **every** row.

### Source ledger — official installed files

All three files are the *installed local vendor SDK* under the Scripting root
above; these hashes are SHA-256 of **actual Mac file bytes**, not hashes of a
web mirror or of an unspecified downloaded release:

| ID | Installed official file (absolute path suffix under Scripting root) | SHA-256 | Relevant text / limitations |
| --- | --- | --- | --- |
| I1 | `DaVinciResolveScript.pyi` | `2755259ef5f57b5d477786f799892e5b86ed3945db84bf88fb69bf751b36e651` | 2,848 lines; `class Timeline` line 2184, `class TimelineItem` line 2379, getter signatures below. No declared `SetLeftOffset`, `SetRightOffset`, `SetPosition`, `GetPosition`, `Timeline.MoveItems`. Stub itself has no independently explicit build string. |
| I2 | `README.md` | `5f58c94da8ec3c1f390d77ad9c60675263591dc101159b302e50b5774513830b` | 628 lines; `Last Updated: 31 Aug 2026`, lines 1–6; scripting modes and configuration lines 11–50. Contains no listed 21.1.2/21.2 or same-UID roll mechanism. |
| I3 | `CHANGELOG.md` | `b12c961176d79a5fc87757a21dc7ce2e147f13fb4dab927ed9154943c7de1491` | 132 lines; `Last Updated: 1 Sep 2026`, lines 1–8; newest section `21.1` starts line 9. No later `21.1.2`/`21.2` section and no in-place roll setter. |

App `Info.plist` SHA-256:
`7539507115e554d8b936253934c394d9ded2b8f509eb5edd1cb58b047391a2f4`.
Source path:
`/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Info.plist`.

**Installed official `.pyi` declarations (verbatim signatures):**

| Object | Signature | Local `.pyi` line | Semantics documented locally |
| --- | --- | --- | --- |
| `TimelineItem` | `GetStart(self, subframePrecision = False) -> float` | 2393 | Timeline record start |
| `TimelineItem` | `GetEnd(self, subframePrecision = False) -> float` | 2396 | Timeline record end |
| `TimelineItem` | `GetSourceStartFrame(self) -> int` | 2399 | Source frame at the clip's in-point |
| `TimelineItem` | `GetSourceEndFrame(self) -> int` | 2402 | Source frame at the clip's out-point |
| `TimelineItem` | `GetDuration(self, subframePrecision = False) -> float` | 2411 | Clip duration |
| `TimelineItem` | `GetLeftOffset(self, subframePrecision = False) -> float` | 2414 | **Maximum available left extension**, not a setter |
| `TimelineItem` | `GetRightOffset(self, subframePrecision = False) -> float` | 2417 | **Maximum available right extension**, not a setter |
| `TimelineItem` | `GetUniqueId(self) -> str` | 2570 | Native item identity |
| `Timeline` | `GetStartFrame(self) -> int` | 2192 | Timeline start frame |
| `Timeline` | `GetEndFrame(self) -> int` | 2195 | Timeline end frame |
| `Timeline` | `GetTrackCount(self, trackType: TrackType) -> int` | 2198 | Track count for type |
| `Timeline` | `GetItemListInTrack(self, trackType: TrackType, index: int) -> list[TimelineItem]` | 2201 | Item inventory per track |

The entire installed `.pyi` was searched for the exact new method names;
none occurs. This supports **"not declared in installed 21.1.1.10 SDK"**,
*not* a runtime `dir()` result or universal impossibility theorem. Conversely,
the presence of getters is not proof of a supported setter or a native edit.

### Version comparison — published documentation is *not* an installed SDK

The following [community-hosted BMD documentation mirror](https://wheheohu.github.io/bmd_doc/ResolveAPI/intro)
labels versions 21.1.1, 21.1.2 and 21.2. It is **secondary published evidence**,
not a local vendor SDK artifact, a Blackmagic-authenticated hash or a live
Mac capability test. No 21.1.2/21.2 SDK was found among the *installed* three
files. We have **not installed** or upgraded Resolve to compare versions.

| Capability | Installed official 21.1.1.10 | Published 21.1.2 (secondary) | Published 21.2 (secondary) |
| --- | --- | --- | --- |
| `TimelineItem.GetUniqueId`, record/source getters, left/right offset getters | Declared | Listed | Listed |
| `TimelineItem.GetPosition(subframePrecision=False)` | **Not declared** | **New**: position dict `{trackType, trackIndex, startFrame}` | Carried forward |
| `TimelineItem.SetPosition({position}, moveLinkedItems=True, subframePrecision=False)` | **Not declared** | **New**: moves item on timeline; linked items optionally move | Carried forward |
| `TimelineItem.SetLeftOffset(offset, subframePrecision=False, updateLinkedItems=True)` | **Not declared** | **New**: adjusts *available left source offset* per `GetLeftOffset` | Carried forward |
| `TimelineItem.SetRightOffset(offset, subframePrecision=False, updateLinkedItems=True)` | **Not declared** | **New**: adjusts *available right source offset* per `GetRightOffset` | Carried forward |
| `Timeline.MoveItems([timelineItems], {position}, moveLinkedItems=True, subframePrecision=False)` | **Not declared** | **New**: moves selected items as a relative group | Carried forward |
| Explicit atomic roll of one adjoining cut, with **both existing item UIDs** retained | **No declared API or proof** | **No documented operation or proof** | **No newly listed operation or proof** |

Version-specific, directly browsed secondary references:

1. [21.1.1 TimelineItem](https://wheheohu.github.io/bmd_doc/ResolveAPI/21.1.1/resolve_api/TimelineItem)
   and [21.1.1 Timeline](https://wheheohu.github.io/bmd_doc/ResolveAPI/21.1.1/resolve_api/Timeline)
   (cross-check; **not** the installed-official source I1–I3).
2. [21.1.2 TimelineItem](https://wheheohu.github.io/bmd_doc/ResolveAPI/21.1.2/resolve_api/TimelineItem)
   and [21.1.2 Timeline](https://wheheohu.github.io/bmd_doc/ResolveAPI/21.1.2/resolve_api/Timeline)
   (published signatures and semantics).
3. [21.2 update matrix](https://wheheohu.github.io/bmd_doc/versions),
   [21.2 TimelineItem](https://wheheohu.github.io/bmd_doc/ResolveAPI/resolve_api/TimelineItem)
   and [21.2 Timeline](https://wheheohu.github.io/bmd_doc/ResolveAPI/resolve_api/Timeline).
   The **listed 21.2 delta** adds thumbnail export, auto-color controls,
   `GetCDL`, extras-package APIs and other non-roll capabilities; it does
   **not list** a new roll setter. A changelog omission does not rule out
   undocumented behavior, and a listed setter does not prove native UID
   preservation.

**Why the new signatures are not a verified roll:** `SetLeftOffset` and
`SetRightOffset` are described in terms of source extension availability,
not a paired, transactional reallocation of exactly 24 frames between two
adjoining native clips. `SetPosition` and `MoveItems` move items, not their
source trim by definition. None guarantees unchanged adjacent item UIDs,
linked audio, other tracks, a fixed right end, or correct save/reopen state.

### Community behavior report (warning, neither official nor VERA proof)

[davinci-resolve-mcp issue #336](https://github.com/samuelgursky/davinci-resolve-mcp/issues/336)
reports Studio **21.1.2.10 on Windows 11**: a `SetLeftOffset(5.0, False,
True)` call returned `True` while drastically moving and lengthening a clip.
The reporter **did not re-run** this destructive call. In a later correction,
they found the test timeline was malformed: clips were written at absolute
record frames `0/200/400` while its `StartFrame` was `86400`. Other original
failure claims were withdrawn after repairing that fixture. This remains a
**caution about reliance on returns and malformed geometry**, not proof that
`SetLeftOffset` is wrong on properly formed timelines. The report's separate
`SetPosition`/`MoveItems` observations also cannot substitute for a valid
VERA native experiment. Do not replay this test on any existing project.

### Current classification and handoff to later phases

| Build/context | Static classification | Native same-UID roll proved? | Can #477 run native edit? |
| --- | --- | --- | --- |
| Actual installed **21.1.1.10** official SDK | `not_available_on_installed_build` **at declaration level** (no setter declaration) | **No** | **No** |
| Published **21.1.2** mirror, not installed | `candidate_unverified` **documentation only**; future runtime check also needed | **No** | **No** |
| Published **21.2** mirror, not installed | `candidate_unverified` inherited setters; **no new documented roll** | **No** | **No** |

**Interim NO-GO for a supported non-GUI, identity-preserving native edit on
the installed build.** An upgrade or documented setter is not itself a GO.
Do not claim #473 acceptance, release PR #474, advance #312/#313, replay the
expired M4 campaign or create/edit/save/reopen any Resolve timeline under
#477. No same-UID change, native result or modified media was observed here.

Phase 2 will add a **pure, bounded, no-SDK-import** declaration inventory
and fake-only regressions. Phase 3 will finish the feasibility decision and
**document only** a one-use, separately Producer-approved **NEW** synthetic
experiment with source/version pins, ownership, UID/media/link/audio/6-track
identity, 24000/1001, 1,407 frames, the exact 327→351 boundary,
independent signed before/after plus save/close/reopen readback and fail-stop
with no retry. `verify_supported_boundary` in
`python/vera_timeline_agent/resolve_test_queue_reverse.py` (lines 25–147)
specifies the minimum geometry delta, not a standalone signed native proof.
