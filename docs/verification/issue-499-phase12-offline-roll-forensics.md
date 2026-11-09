# #499 phase 12 — one-use direct-Roll calibration: offline forensic record

**Scope:** 2026-11-09; historical **disposable calibration only**, not an original #473 M4 stage or #312 acceptance. This is a redacted, content-addressed record of *existing* artifacts, not a replay or a new approval. Real project/timeline/media UIDs, case name, personal filesystem paths, and raw Apple-event output are deliberately omitted. Preserve the original evidence in place; the Git commit containing this report is the immutable report revision.

## Provenance and limits of attribution

- Exact local calibration checkout recorded in the **separate one-case authority**: `b613cab5b960ce0d750fd33ef9e598fb4f67ae05`, parent `b6e083b671d39292231ab3d2fafcc538b21cb296`, descended from `bbe5c64be58e0c841a985ea6a5aed41b3372a873`. Independent `git show`, `merge-base --is-ancestor`, and blob hashing confirm the scripts at that exact revision. This is **not** the original remote PR #474 head.
- At inspection, adopted local branch `zodex/499-adopt-pr474` was at `421d57795a11735ba6631e48b7805331089c6581` before this report; `b613cab5..421d5779` changes only three Conductor planning files under `docs/plans/`, not the **245-input** source graph or calibration scripts (count verified directly with `proof_source_hashes_v2()`). The unchanged, locally recorded `origin/chat/473-unattended-test-bench` tracking head was `7ba029626642fc08adfa0c8621946eb71544e4fc`; **no fetch, push, PR edit, or merge was attempted**.
- Proof source graph: `54ffaaeef7d5f21a631f9aa478a98c431e0cd3e0a9831f454306b170b5821ba1`, independently recomputed offline with `resolve_test_bench_full_loop._source_hash()` at the unchanged runtime source, and equal to the authority and pristine artifact fields. Base source commit recorded in pristine: `bbe5c64be58e0c841a985ea6a5aed41b3372a873`. A graph digest checks content, not live operator permissions or execution history.
- Exact SHA-256 of *script bytes* at calibration commit (also unchanged at inspection): Python calibration driver `4ea491efbdc6f182ba7f5b9fc8e2e53ddbc1ebfc154dd93ab28b9565e41e3f21`; one-use setup actor `09b7db76c40ef97e6c6bbe084b23c2611e058d92dea203023aa0290a095aa2c2`; single-command Roll actor `606923e3b61c7e760ff05795b79dce61e490799f5878bdb372a3e2c41af747f5`.
- The separate authority file's SHA-256 is `90f940db0a68a45a6bc87cdb13b35538ec5fdf9e237da55ca159573ee349887e`, **identical in the private Mac case location and the existing #499 ticket's `phase11-direct-roll-calibration-authority-v2.json`**. Its fields pin case name (redacted), base commit, exact checkout, graph and three script digests, and permit at most one new disposable project and one Roll. This is a local authorization record, **not** an independently cryptographically signed Producer instruction.
- Physical evidence was inspected read-only through the Mac bridge while Resolve remained quit. Private v2 case directory mode was `0700`; all 14 evidence JSON files and the separate authority were owner-only `0600`; no symlinks were found in that case root. The prior **v1 precreate/UNKNOWN root still exists** and was not opened, modified, restarted, or cleaned. No old #473 campaigns were accessed or replayed.

## Preserved evidence inventory

SHA-256 below is over the **exact on-disk bytes** on the physical Mac, not over copied snippets or a newly serialized JSON object. All 14 case JSON files parsed and matched the driver's sorted-key, compact, trailing-newline canonical serialization. File basenames only are disclosed.

| Existing file | SHA-256 |
| --- | --- |
| `assets.json` | `179ecc0cddb8d48a3b8c9a770d2d9c43654b52d382b2a48ae6b6f2ff7068444c` |
| `provision-intent.json` | `26076ecf9cb172a363b265dd4f608c5ff4e8bf36d506ff7dbee5a19deee982c6` |
| `pristine.json` | `5bf0c3cdebaf00842d931fb2df42fe927c8696141f9bdcd976ce1c90d94f5b13` |
| `activation-intent.json` | `3b154fa3ba2155e3114480db56ad1a595e2a7d9b716aac83d887dc9448d40fa2` |
| `setup-intent.json` | `3b8d8f88fc8112a245ff6d08118f13c5bce6d2b7ab6e3acd3684f7b955e6a822` |
| `setup-result.json` | `3ce408be88e18e24ec1386a8d071924d6a582d8e5bcb385595270ac4777d9929` |
| `ready.json` | `b352e0de84218949abfe697b247163695b2b08c7cf59096ec91e7847cd421c01` |
| `roll-intent.json` | `4bd3147be80af2858a1f2c4897a354c231b839dd02a7f6aa4328eeec70b15fba` |
| `roll-transport-result.json` | `7df8bd4c6012e722204d9cf6e681b0ef8e00db983f525ffd496e70b7d420029a` |
| `post-roll-observation.json` | `43b71e07a80d72267d6eaafedb5f72a5aed11d0f9f47ac3781918a34207b692f` |
| `save-reopen-intent.json` | `d00585ebb3ec81dacf51de0c4a461a3c3bc952e12d2f99f8cf534ed51432e265` |
| `saved.json` | `170b1afde5eac64a80d0694751b8f8d5f6ce4173d4d855678371e65336031c26` |
| `closed.json` | `8333c0de38ce68737cddaa47ec8099d649b9f3b82b832cec85351dd5aee0ab43` |
| `reopened.json` | `6cf4f362a3a967f031de2c3608300966f48a3d81edfdd6d59d8cd44d253603a8` |

Three **newly generated synthetic** source assets had disk hashes exactly matching `assets.json`: `root.mp4` = `d6034a9089ac8b38a011d418fe09472c49fb5133fc2da0ce6ad0ad538cfc1f3f`; `overlay.mp4` = `913b4c2369c7108ab883549a4d07f265b4bb769939df3fdbbba1775a2a8a3581`; `audio.wav` = `e6174f86733a988dc3680989b503db2a34173e55326eb79490c2a95deeabad15`. Mac `ffprobe` independently identified `root.mp4` as time-based **H.264, 720 decoded frames, 24000/1001 fps**. This is a video-file source, **not the held-still input of the original M4** (the generated pictures are solid colors; “moving video” describes source type, not visual motion).

## Independent comparisons of the retained native snapshots

The code's fresh-case construction calls the official SDK and checks the three imported media paths against the generated asset paths, creates six named tracks, places eleven unlinked clips, locks every track except V1, and saves. Its `snapshot()` records item UID, media UID, kind, track, record start/duration, **raw** `GetSourceStartFrame`/`GetSourceEndFrame`, and linked UIDs. The retained pristine data contain exactly **11 distinct UIDs / six tracks**. However, no independent post-import `File Path` to **each media UID** mapping or source-time normalization is stored in the snapshots: that *particular* mapping is **UNKNOWN** beyond the checked code path and asset hashes.

Direct read-only comparisons yielded the following; the values are frame numbers, not assumptions about normalized still-image time:

| Exact native field | Pristine | Post single Roll | Reopened |
| --- | --- | --- | --- |
| V1 left record start / duration | `0 / 327` | `0 / 351` | identical to post |
| V1 right record start / duration | `327 / 151` | `351 / 127` | identical to post |
| V1 left raw source start / end | `0 / 327` | `0 / 351` | identical to post |
| V1 right raw source start / end | `0 / 151` | `24 / 151` | identical to post |
| Entire other nine native item dictionaries | baseline | **field-for-field identical** | identical to post |
| Set of all 11 native item UIDs | 11 unique | exactly equal | exactly equal |
| Six-track definitions, locks, names | baseline | exactly equal | exactly equal |
| Both boundary media UIDs, linked lists, track/kind | baseline | exactly equal | exactly equal |
| Whole captured `native` object | pristine | two changed V1 items only | **exactly equal to post** |

Additional direct equalities: `pristine.native == post-roll-observation.before`; `pristine.target == post-roll-observation.target == saved.target == reopened.target`; `post-roll-observation.after == reopened.native`; and the transport object embedded in the observation equals `roll-transport-result.json`. The only changed item indices in the complete, UID-sorted 11-element arrays were **3 and 4**, the two V1 boundary items; the remaining nine (including other V1 clips) were identical across every captured field. The right raw source-start change **0→24** is an *observed property of this time-based synthetic H.264 calibration*, not permission to reinterpret original still-image M4 source semantics.

The retained `ready` and `roll-intent` both bind the baseline SHA-256 `5bf0c3...f5b13`; the intent records `from=327`, `to=351` and the exact Roll actor hash. The existing transport record reports `exitCode=0` with no stderr and names `Trim > Roll > Start to Playhead`; the native `post-roll-observation` reports `readError=null`. Save and close receipts each record `true`, followed by the reopened snapshot. The pinned driver has a durable O_EXCL/fsync one-use intent **before** invocation, the single literal menu action, no retry, and a full save/close/load SDK equality check after the edited observation. **No second Roll dispatch was made during this forensic inspection.**

## Evidence boundaries / Opus reconciliation

**Independently verified now:** artifact SHA-256, canonical encoding, ownership/mode for case JSON, authority copy equality, three synthetic asset SHA-256, actual `ffprobe` source type/frame count, exact Git script blobs and ancestry, offline source-graph digest, all snapshot comparisons and transport/save/reopen *record values*. The recorded one-case execution is internally consistent with the exact reviewed script and SDK observation path. These checks do **not** independently witness the historical Apple-event process or make a fresh live SDK read from the closed Resolve app.

**Claims not upgraded to independent facts:** historical Mac foreground/AX/TCC state at click time; independent actor process attestation beyond the recorded exit code; actual import-path-to-mediaUid mapping; frame/time getter normalization on held stills; whether this same raw `+24` is appropriate under the **four** production capture/package/revision/reverse gates; or a decoded production M4 MOV/PCM verification. The previously supplied Opus review **did not inspect** local `b613cab5`, the one-case v2 root or these file hashes. Do not attribute this forensic result to that review, or treat its held-still conjecture as verified.

**Acceptance decision:** This is **one verified-in-artifacts synthetic calibration**, not original #473 M4. **Production M4 verified receipts: 0/4; strict #312 result: NOT RUN; #473/#312/#313 remain blocked.** No source-in verifier relaxation, replay, Resolve launch, external-drive access, new user consent, full tests, PR write, or merge was performed. Phase 13 must adjudicate still-vs-video semantics across all four guards from the actual code; Phase 14 prepares a strictly read-only deferred SDK metadata probe. Any missing live metadata remains **UNKNOWN** until safe, separately gated Mac reentry.
