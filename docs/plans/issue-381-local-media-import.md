# #381 — Verified local media import backend: boundary and phase plan

**Scope:** Phase 5.1B backend only. The approved #85/#147 default is to clone
writer-owned stills/B-roll into the owning script project, or make a **verified
independent full copy** if the CoW clone is unsupported. This plan implements the
four-phase pipeline against `origin/main` without changing public schemas,
creating a browser UI, writing to Resolve, deleting an original, calling a
service, or importing the Producer's real media. No authenticated companion
pairing/import API exists merely because #158's diagnostic is installed.

## Authority and existing contract map

| Producer/technical authority | Consequence for #381 |
| --- | --- |
| Issue #381; dependent issues **#156 and #158** | Both are closed; no dependency on #125 or #377. #85 owns browser selection/result UI. Do not dispatch other work from this issue. |
| `docs/Script-to-Timeline Product Spec - Fable Rev2.md` §§7/8.2 | Media IDs and immutable hashes determine identity; paths determine *location*. Script owns `Media/Local Images/<asset-uuid>/<filename>` or `Media/Local Clips/<asset-uuid>/<filename>`. Default clone then verified independent copy; never hardlink, move or delete source. |
| `docs/companion-setup-readiness.md`, `companion_readiness.py` (#158) | A read-only installed-integration diagnostic. `approvedRoots` and a reported `paired` or `connected` are **not** authenticated import authority. A new trusted **in-process local operator** boundary must inject approval. No new HTTP listener, pairing assertion, or network service. |
| `contracts/script-document-v2.schema.json` / `packages/contracts/src/authoring-v2-validation.ts` (#156) | `pictureKind:image/clip` can explicitly refer to `{kind:"media_reference",mediaReferenceId:<UUID>}`. A receipt does not mutate the document or bypass `validateScriptDocumentV2`. Image usage remains still/muted; clips require independently verified source bounds. |
| `contracts/compiler-dependencies-v2.schema.json`, `packages/contracts/src/compiler-core-v2.ts`, `build_media_stage.py` | A later independently frozen occurrence resolution may use `sourceSnapshot.system:"local_import"` and exact content/probe hashes; the *existing* source sufficiency, preparation, original-source hash and requirement checks still apply. Do not invent a frame map, `preparedMedia`, CFR compliance or build-readiness from this receipt. |
| `packages/project-authorization/src/{policy,service}.ts`, `packages/project-documents/src/{service,api}.ts` | Existing `edit_document` is authorized only for verified Editor/Producer project actors and must be rechecked for future document CAS attachment. Viewer and untrusted identity are denied. The existing JSON API is **not** a binary importer; this phase adds no HTTP route, upload, PostgreSQL migration, or permission. |
| `media_preparation.py` (#174), `workflow_package.py`, `shoot-registration.ts` (#43) | Reuse decoded/probe findings and write-once receipt techniques only in their qualified envelopes. Path-based `stat`-then-open and `sha256(path)` do not resist hostile source races; registered presenter masters are separate. |
| `docs/RESOLVE_KNOWLEDGE_GUIDE.md` RK-01–RK-03 | No new native scripting or Resolve placement in this backend import. No new native finding or Resolve test is required by the pure phase. |

## Phase 1 — exact pure model and two privacy surfaces

`python/vera_timeline_agent/local_media_import_model.py` is standard-library,
side-effect-free, and holds the sole initial Python contract. It is **not an
authentication, filesystem verification, or media qualification library**.

- `LocalImportApproval` (private, repr-suppressed): four distinct canonical
  nonnil RFC-4122 UUIDs (`project_id`, `import_id`, `asset_id`,
  `media_reference_id`); a trusted, named source root ID and two absolute
  config-only `Path` roots; source *segments* relative to that root; an
  independently approved `sha256:<lowercase hex>` content hash and exact
  positive byte count; max bytes and minimum free-space floor; `kind` image
  or clip; `requested_mode="clone"` only; and a clip's selected half-open
  source-frame interval plus nonnegative before/after handles. No arbitrary
  path-string/URL source is accepted. The fingerprint includes every field,
  including **private** root paths, to prevent replay under altered authority.
- Pure refusal: canonical IDs, hash, safe-integer (max 2⁵³−1), safe filename/
  root-relative segments, lexical source/project overlap, mode and clip
  selection validation. Reject absolute input names, traversal, separators,
  confusable separators, colon, Cc/Cf controls, hidden names, ambiguous Unicode
  normalization, oversized names, duplicate IDs and too many path segments.
  These are *preliminary* guards: phase 2 must also reject actual symlinks,
  aliases, root overlap, insecure FS capabilities and changed source inodes.
- `DecodedMediaFacts` holds only an *independent decoder's* canonical probe
  SHA-256, positive dimensions and (for video only) positive decoded frame
  count; `ClipUse.check_decoded_frames` proves approved range **and** handles
  fit that independently observed count. No inferred source rate/frame map.
- `PrivateAttemptRecord` has request fingerprint, root ID and relative source
  segments and an explicit pending/failed/inspection/completed state. It has
  **no portable serializer**. Its storage in phase 2 must be private,
  append/write-once with restrictive permissions, and not auto-synced.
- `PortableImportResult` contains **no source root, source segments, absolute
  path, actor claim, credential, or nested private approval** even when
  converted using `dataclasses.asdict`. It can be produced from an already
  verified approval+decoder result and includes four IDs, kind, one safe
  display filename, SHA-256s, byte count, dimensions, optional verified clip
  bounds/handles, completed mode `clone|copy`, the derived project-relative
  locator, UTC verification time, `originalRemovalStatus:"not_requested"`,
  `requestedMode:"clone"`, and `buildQualification:"unqualified"`.
  This formatting method **does not independently authenticate evidence**.
- `ImportModelError` emits one fixed machine code and non-interpolated text;
  portable refusals omit all private paths and token data. Never print Python
  exception `repr`/tracebacks, dataclass approval, ffprobe raw output, or
  private request JSON in a user-facing interface.

## Phase 2 — descriptor-safe verification and durable materialization

Introduce `local_media_import.py` with injected, trusted
`LocalImportApproval` + private state root. No client-provided identity or
`companion_readiness` report authorizes it. Use `openat`/`dir_fd`, `O_NOFOLLOW`
and `O_DIRECTORY` where supported, fstat of opened descriptors, no symlinks,
directories, FIFOs, devices, traversal or root-alias overlap. Refuse platforms
that cannot guarantee these checks. Hash from the **opened file**, not a path
reopened after an initial stat; check expected size, device/inode/mtime before
and after, bounded stream, disk floor and supplied SHA-256. Maintain a tight
source `fd` authority scope and never read outside it.

Decode only a separately staged, already-verified independent temporary copy,
not a mutable user path. Accept bounded independently decoded PNG/JPEG single
stills or supported video; reject corrupt, ambiguous, VFR/unsupported media
for any build-ready claim. Clip selection must remain within decoded source
bounds with requested handles; preserve original bytes/rate (no implicit
transcode or retime). Incompatible target CFR goes to #174 later.

Stage privately and exclusively **on the project filesystem**. Try narrowly
qualified injected macOS CoW clone to an independent new destination; verify
source and clone file identity, size and content. If unsupported, full stream
copy to a 0600 exclusive temporary file, fsync, hash the opened destination.
Never use `link()` to create a media clone, shell `cp`, or `rename()` to move
the source. Atomically no-overwrite publish only into
`Media/Local Images|Clips/<asset-id>/<safe-filename>`, then reopen and verify
destination bytes and provenance again before success; fsync parent dirs.
Original is always unchanged and never unlinked or moved.

For each import ID, serialize claims and keep a private append/write-once
request fingerprint and an immutable successful receipt. Exact replay must
revalidate actual project bytes/decoder and return a duplicate without
writing. Same ID with different fingerprint = conflict. Stage crash, missing
receipt, destination already occupied, source drift, or stale/altered output =
`needs_inspection` or `incomplete_attempt`, never overwrite/remove/relabel.
Only a separate explicit inspected recovery may adopt exact matching bytes;
never clean up uncertain state automatically. A project-scoped lock and
exclusive create must prevent two competing imports claiming the same asset
or ID. Unrecognized failure = safe generic refusal, not a ready asset.

## Phase 3 — developer-only harness and future service seam

Provide `local_media_import_cli.py` for **disposable local fixture roots**;
explicit approved project/source roots/expected bytes and intent come from
a trusted local operator, not a browser field or diagnostic JSON. Present only
portable result/refusal JSON, keep private state out of synced output and
logs. Document an optional pure `LocalImportStore` interface for a future
project-service adaptation; no new endpoint or migration here. Only after a
fresh project-authorized `putDocument` CAS call may #85 attach a stable
`mediaReferenceId`. Future frozen build consumers must independently bind
`local_import` source snapshot/probe identities and verify bytes, requirements,
source frames and prepared-media hash. No work from #43, #125 or #377.

## Phase 4 — evidence and acceptance

Run synthetic real-filesystem still and video examples on the available host
(and explicitly label any Mac-specific clone test as unrun unless on Mac).
Record clone versus independent full-copy fallback, source-before/after SHA,
unsafe path/symlink/FIFO/device, tampering, mismatched bytes/size, insufficient
space, unsupported decode/bounds, conflicts/concurrency, interrupted stage and
resume/no-overwrite, privacy canaries and downstream qualification refusal.
Run focused tests, `npm run validate:fast`, reversible guard mutations and
independent review as available; retain only sanitized
`docs/verification/issue-381-local-import.md` evidence. Final technical
acceptance still belongs to the named issue authority; synthetic tests or a
local import result do not close #381 themselves.

## Refusal matrix (fixed codes, no private input in error text)

| Reason | Code / safe action |
| --- | --- |
| No trusted local approval, bad roots/limits, invalid UUID/hash or name | `approval_required`, `invalid_approval`, `invalid_identity`, `invalid_locator` — refuse before I/O |
| Unsupported requested move/reference/unknown media, missing clip selection or insufficient verified handles | `unsupported_mode`, `unsupported_media`, `invalid_bounds` — no implicit fallback beyond clone-to-copy |
| Source missing/nonregular/link/escaped/changed/hash mismatch/over limit | `source_unavailable`, `source_unsafe`, `source_changed`, `content_mismatch`, `size_limit` — preserve source |
| Overlapping roots, missing fd no-follow guarantees, insufficient storage or permission | `root_overlap`, `unsafe_filesystem`, `insufficient_space`, `permission_denied` — no unsafe import |
| Media undecodable or unsupported on installed decoder | `undecodable_media`, `unsupported_media` — not build-qualified |
| Existing unrelated destination/ID, crash/partial/replay drift | `publication_conflict`, `import_conflict`, `incomplete_attempt`, `needs_inspection` — inspect; never overwrite |
| Other bounded local I/O failure | `io_failure` — generic details only in protected local evidence |

All temporary fixtures are synthetic and privately located. Phase 1 creates
**only** this plan, the pure model and its focused tests; later engine, harness,
verification evidence and delivery are separate conductor phases.
