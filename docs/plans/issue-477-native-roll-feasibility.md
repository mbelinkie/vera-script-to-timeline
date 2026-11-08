# #477 — Supported non-GUI same-UID picture roll: feasibility evidence

## Phase 1: read-only SDK evidence (2026-11-08)

**Status: no supported same-UID roll has been proved.** This is a declaration and
documentation inventory, **not** an execution, readback, native acceptance or
permission to edit. The installed Resolve **app bundle** reports **21.1.1
build 10**; this was not corroborated by a live Studio edition/version
handshake. Its official, installed SDK does not declare newer trim/position setters.
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

**Final #477 feasibility verdict: NO-GO for a supported non-GUI,
identity-preserving native roll on the installed build; candidate-only for
21.1.2/21.2.** An upgrade or documented setter is not itself a GO.
Do not claim #473 acceptance, release PR #474, advance #312/#313, replay the
expired M4 campaign or create/edit/save/reopen any Resolve timeline under
#477. No same-UID change, native result or modified media was observed here.

Phase 2 added the **pure, bounded, no-SDK-import** declaration inventory
and fake-only regressions described below. Phase 3's final assessment and
**unexecuted** sacrificial protocol follow. `verify_supported_boundary` in
`python/vera_timeline_agent/resolve_test_queue_reverse.py` (lines 25–147)
specifies the minimum geometry delta, not a standalone signed native proof.

### Phase 2: offline declaration scanner (no native access)

`python/vera_timeline_agent/issue477_sdk_inventory.py` reads only selected
local text files, with a 2,000,000-byte limit **per file** and no SDK import,
Resolve connection, or filesystem output. For example, with a separately
obtained, existing `.pyi` (do not download or install anything as a side effect):

```sh
uv run --frozen python -m vera_timeline_agent.issue477_sdk_inventory \
  /path/to/DaVinciResolveScript.pyi --version-label 21.1.2
```

Optional `--readme` and `--changelog` arguments inventory local Markdown byte
hashes too. The AST-only parser records method signatures and exact input SHA-256;
it rejects invalid syntax, non-UTF-8, duplicate classes/methods, repeated file
identities, symlinks, non-regular files and oversize text. `versionLabel` is
**caller-supplied and unverified**; even `candidate_unverified` never attests
the running/installed SDK or edit semantics. Every result hard-sets
`installedBuildVerified=false`, `sameUidRollNativeVerified=false` and
`mayExecuteNativeEdit=false`. Fake fixtures cover 21.1.1, 21.1.2, 21.2 and
contradictory/malformed/negative cases; no fake is native evidence.

## Phase 3: feasibility verdict and future sacrificial protocol — NOT executed

### What the evidence supports, and what it cannot establish

**NO-GO, today, for strict #473 acceptance.** The installed **21.1.1 build
10** bundle and official local SDK provide read-only trim extent getters but
**no declared API** for the proposed in-place edit. This is a supported-
surface assessment, **not** a live `dir()` inventory or a proof that every
unpublished internal feature is absent. The 21.1.2 and 21.2 version-specific
references above are **secondary**, uninstalled evidence: they document
individual trim-offset and placement operations, *not* an atomic adjacent
two-item roll with stable native UIDs. In particular:

| Candidate | Documented operation | Missing evidence for this acceptance |
| --- | --- | --- |
| `GetLeftOffset` / `GetRightOffset` (installed) | Query available source extension | No mutation at all |
| `SetLeftOffset` / `SetRightOffset` (21.1.2+, published only) | Set **available** source offset at one item edge; optionally update linked items | Do not document paired +24/−24 frame cut transfer, stable UID/links, right end, six tracks, persistence or atomicity; `offset=24` must **not** be assumed to mean “roll +24” |
| `SetPosition` / `Timeline.MoveItems` (21.1.2+, published only) | Move one item or a relative group on a timeline | Neither guarantees the source trim required to preserve the adjacent cut and fixed right-hand end; moving items can create gaps/collisions |
| `SetProperties` / other generic property methods | Set documented clip properties, where writable | No published exact, supported same-UID cut-transfer contract; never infer an undocumented trim property |
| Rebuild, OTIO/FCPXML import, create/copy/append timeline items | Assemble new timeline/native items | Original `TimelineItem.GetUniqueId()` equality across the edit is unproved or lost; not the same-target roll |
| Historical menu/keyboard/GUI roll | Editor visibly rolled a cut in an earlier, retired M4 envelope | Violates **non-GUI** automation requirement; historical proof is not a new authorized native receipt |

The 21.1.2.10 community `SetLeftOffset` success-with-wrong-geometry
report is explicitly **inconclusive** because its timeline start-frame
metadata was inconsistent. Do not generalize the failure to valid timelines;
also do not treat its `True` return as a clean test. The 21.2
changelog's silence on a new roll method is negative *documentary* evidence,
not a claim about all possible runtime behavior. No 21.1.2/21.2 SDK bytes,
21.2 installation, runtime `dir()`, live method result, or save/reopen
observation was acquired in this ticket.

**Disposition by evidence level:** the phase-2 scanner can say
`not_declared_in_supplied_stub`, `candidate_unverified`, or `unknown`; it can
**never** say `sameUidRollNativeVerified=true` or
`mayExecuteNativeEdit=true`. An authenticated new native result on a separately
approved target would be a different evidence class. Merely changing the
version label, witnessing callable methods, passing fake tests, a setter
returning `True`, or creating a visually matching imported timeline does not
change this verdict. #477 has produced **no** `accepted` M4 receipt, signed
Studio output, new native project or edit, and **does not** unlock #473,
PR #474, #312 or #313.

### Producer decision — alternatives, none implicitly authorized

1. **Recommended now: NO-GO / keep existing Studio host unchanged.** Finish
   this read-only report, keep #473 strict non-GUI same-UID acceptance
   **blocked**, and make no Resolve or Producer-project changes. There is no
   reason to upgrade merely to discover method declarations.
2. **Conditional research GO, *only after a new, explicit Producer approval*:**
   approve a separately tracked, single-use **NEW** sacrificial test on a
   reviewed suitable newer installed build (21.1.2 or 21.2), with a named
   source-pinned, documented **non-GUI** candidate sequence and all gates
   below. Any installation/upgrade requires its own permission and release
   review; approving research alone grants neither an upgrade nor an edit.
   **Even a successful experiment proves only that specified build/fixture**;
   #473 still needs its own complete authenticated parent acceptance.
3. **Product/design alternative, separately reviewed:** the Producer may
   explicitly revise #473 so an editor performs the roll while VERA
   automatically **observes, identifies and reconciles** changes on the
   original native items. This avoids inventing unsupported API writes but
   changes the present “one-start, unattended, non-GUI roll” contract. It must
   be approved as a **new requirement/acceptance design**, including what
   becomes manual, how it is authenticated and what remains automated; it is
   **not** acceptance under the existing requirement. A manual editor check
   may demonstrate observation, not unattended native roll creation.
4. **Rejected as substitutes:** CLI keyboard/menu/`osascript`, undocumented
   methods, unreviewed offset combinations, a fresh import with new UIDs,
   synthetic JSON pretending to be a host result, reusing M4 receipt IDs, or
   silently waiving identity/non-GUI verification. These cannot produce the
   mandated #473 result. Escalate for design rather than retrying unsafe calls.

### Proposal for a future **separately approved** one-use native experiment

This section is an **unexecuted test specification, not an implementation
recipe or authorization**. No operator or Conductor phase may execute any
step below merely because #477 is merged. Start a distinct, chat-reviewed
ticket with explicit Producer **GO** covering *native creation, exactly one
mutation attempt, save/close/reopen*, the app version and any upgrade, the
resource limits, and a description of the actual proposed scripting API
sequence. The default answer remains **NO-GO**. No work may touch the
expired `~/.local/state/vera/issue-473-studio-05` campaign, its operation
IDs, the historical #312 native target, the frozen #473 host, PR #474 or
Producer media. Use no second Resolve worker.

**Authorization envelope and resource limits to propose for approval:**

| Field | Required immutable future intent (fill with actual values before GO) |
| --- | --- |
| Scope / identity | New issue, Producer-approved rationale and named operator; `caseId`, unique `campaignId`, one new `operationId`/idempotency key, named non-GUI API call plan, **one permitted mutation sequence**; never a preexisting M4 ID |
| Source provenance | Full Git commit SHA of code/release/host controller, artifact SHA-256 and trusted signing identity, original and delivered fixture/media SHA-256 and manifest/frame-map hashes; reject changed inputs |
| App & SDK | Exact installed Studio edition, `GetVersionString` and build corroborated with on-disk app/SDK `.pyi` SHA-256; the intended version must be approved **before** any install/upgrade; reject version drift |
| Target | Create **a new named disposable synthetic** project and timeline from approved fixture bytes; persist their exact native `projectUid` and `timelineUid`, source graph and all **11** initial `TimelineItem.GetUniqueId()` values **before editing**; never accept a new target as a post-edit substitute |
| Owner / isolation | Exclusive existing `resolve_native_owner` host flock/owner preflight, idle and no unresolved operation; same user/host identity and owner scope through capture, mutation and save/reopen; fail if lock cannot be obtained or another worker is active |
| Intent / expiry | Immutable authenticated **pre-effect intent**, SHA-pinned, path-private and write-once, with one nonce/operationId and exact target/method/argument plan; suggested **60-minute TTL** from admission; expiry before an operation means fail closed; no renewal/replay |
| Budget | Suggested **4 GiB maximum newly allocated scratch/media/results combined**, checked before and after each stage; **one** native mutation attempt, no render or paid API, **zero** unapproved upgrades; if fixture needs more, request a new Producer limit first; no automatic retries or extra campaigns |
| Receipts | Separate authenticated append-only intent, pre/candidate/post/reopened host observations with sequence, UTC timestamps, build/source/target/owner fingerprints, artifact SHA-256 and an existing approved host-verification/signing mechanism; **plain self-reported JSON/hash is not a signature** |

**Fixture and geometry, established before mutation:** create the synthetic
source package only after approval. It must match the approved #312 case:
frame rate **24000/1001**, total programme **1,407 frames**, **six actual
Resolve tracks** with recorded type/index/order and metadata, and **exactly
11 real native timeline items**. Use source-pinned synthetic video, still,
graphics and audio contents according to the approved six-track manifest;
do not guess track names or silence from fake test data. Read back a
complete, host-authenticated inventory for *each* item: `eventId`,
native `itemUid`, `trackId`/type/index, `kind`, record start/end/duration,
source ID, source in/out/time and duration, delivered media-pool UID,
source-to-delivered mappings and content SHA-256, online/enabled state,
speed, transformations/settings and all `linkedItemUids`. Capture track
enable/mute/automation and audio channel/routing/links plus original media
and independently probed source duration/rate. Capture the audio programme's
decoded PCM identity/comparison baseline where the #473 parent requires it.
Read-only calls themselves must be bounded and target-authenticated; neither
a fake fixture nor a visual snapshot certifies this baseline.

Identify by admitted event/source IDs, not list position, the **two adjacent
picture items on one video track**. Baseline left item `L` ends at record
frame **327**; right held-picture item `R` begins at **327**, has a duration
strictly exceeding 24 frames and has an independently recorded exclusive
right edge `E`. Preflight a valid timeline start-frame coordinate system,
source handles, six-track topology, UID uniqueness and fixed 1,407-frame
programme; compare actual record frames relative to the timeline's real
`GetStartFrame`, *never* assume a zero or 86400 absolute start. Require
`L.sourceDuration` can grow by 24 and `R.sourceDuration` can shrink by 24
without invalid source bounds. Source-end integer getter quirks at full
decoded-video EOF (see `docs/plans/issue-472-native-video-eof.md`) must be
checked against the signed frame map, true decoded duration and source-time
edges rather than silently normalizing 212/214 or changing source identity.
Save/close/reopen the **pristine** approved new fixture and independently
recapture this baseline first; reject any drift or new item UIDs.

**Exact desired native delta, never substitute a new import:**

| Invariant | Verified pristine | Required edited, then **saved/reopened** |
| --- | --- | --- |
| Target and all item identities | One new project/timeline UID pair; 11 distinct native item UIDs | **Exactly the same project/timeline UIDs and all 11 item UIDs**, including original `L` and `R`; no duplicates/replacements |
| Left picture `L` | `[L.start, 327)` | `[L.start, 351)`; same start/source-in/event/media/settings/track/links, record and source durations **+24** |
| Right held picture `R` | `[327, E)` | `[351, E)`; record/source duration **−24**, unchanged source-in, right end `E`, media/event/settings/track/links |
| Programme / track layout | 24000/1001, extent 1,407, six ordered tracks | Identical rate, extent and six **real** tracks; no new gaps, overlap, shifts, deleted/added items, track enable/mute or routing changes |
| Other nine items | Frozen complete native inventory | **Byte-equivalent canonical per-item readback**, UID/media/source/geometry/settings/link parity; only the two specified picture geometry fields may differ |
| Media / audio / links | Original/delivered hashes, media-pool UIDs, source map, linked UIDs, PCM/channel observations | Same media bytes, frame maps/paths, online state, audio tracks and channels, volume/automation, link symmetry and comparable decoded PCM; no detached, resampled, shifted or replaced audio |
| Receipt authenticity | One authenticated signed pristine capture after reopen | Distinct authenticated edited/reopened result, same pinned target/owner/source/build, complete saved/reopened readback and independent verification; `True` from any setter is insufficient |

**Future effect boundary (only after preflight and approval):** reviewer must
first produce a *literal*, version-matched SDK method-and-argument call plan
for a non-GUI transfer of +24 frames to `L` and −24 from `R` **without**
changing `R.sourceStart` or end `E`, and demonstrate that the documented
semantics are appropriate. `SetLeftOffset(24)` and `SetRightOffset(24)` are
**not** such a justified plan: offset values mean *available source handles*,
not necessarily timeline delta, and there is no documented atomic group
commit. If no supported, bounded exact call plan can be justified, **stop
before touching the timeline and record NO-GO**—do not guess an API sequence.
If an exact reviewed candidate exists, consume **one** pre-effect intent,
execute its **single** approved non-GUI sequence on the new fixture and
immediately perform independent read-only geometry/UID/media/audio checks.
On `False`, `None`, exception, timeout, partial state, `True` with wrong
geometry, ambiguity, owner loss or failed receipt authentication: **fail-stop**,
preserve immutable evidence, leave the sacrificial project isolated and do
not run a compensating write, reverse edit or second attempt. No automatic
correction, replay, GUI fallback or “try the other setter”.

**Persistence and independent verdict:** only if the one attempt yields
exact candidate geometry and all invariants, save, close and reopen that
**same** new project/timeline under the same exclusive authorized owner;
independently authenticate the reopened target and recapture every six-track,
11-UID and audio/media observation. Compare **three distinct** immutable
host captures: pristine after reopen; immediate edited; final edited after
reopen. Verify source/release/bundle/SDK hashes and owner/intent/result chain,
canonicalize frame clocks, rerun
`resolve_test_queue_reverse.verify_supported_boundary` on authentic
pristine/final native geometries, compare the immediate/final geometry and
PCM, and separately invoke applicable parent signed provenance and output
verifiers. This **minimum geometry comparator alone** is not an
authenticated M4 acceptance receipt: `verify_reverse_receipts` additionally
requires its *own* valid accepted-revision proof and distinct fresh rebuild,
which this isolated feasibility experiment cannot fabricate or shortcut.
If any capture or comparison is missing, expired, wrong-target or ambiguous,
the experiment is **NO-GO** with complete retained evidence, not “passed”.

The only conditional research **GO** result is a documented supported
non-GUI edit on that explicitly approved version and **new** fixture with
verified same-native-target, same-UID saved/reopened state and independent
signed host evidence. That does **not** automatically approve a production
adapter, an upgrade of the pinned host, #473 final acceptance, PR #474 merge,
or restarting #312/#313. Those require their own reviewed acceptance path.

### Phase boundaries / verification record

- **Phase 1:** read-only official installed SDK and app bundle metadata
  inspected; absolute path/SHA ledger and limited 21.1.2/21.2 secondary
  comparison above. No live Resolve call or target readback.
- **Phase 2:** bounded offline scanner + fake-only tests; source SHA is a
  provenance handle, **not** vendor or native result authentication. Method
  presence is never treated as GO.
- **Phase 3:** documentation-only decision and proposed single-use trial;
  no native operation created, modified, accepted or replayed. Focused test
  verification belongs to the local phase log; the final full fast gate,
  reversible negative-control mutation and review are phase **4**.
