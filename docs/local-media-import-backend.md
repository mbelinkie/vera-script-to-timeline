# #381 — Private local-media import backend (developer harness)

This is **not** the #85 browser import screen, an authenticated local companion
API, or a source of prepared media for Resolve. Run it locally, deliberately,
on **synthetic disposable files only**. The #158 readiness diagnostic is not a
file-import permission or pairing grant. No real Producer media should be used
without separate operator authorization. The CLI exposes no listener, does not
accept a root from the proposed request, and never deletes/moves the original.

## Security and ownership

* The operator creates a **private, owner-only policy** independently of the
  proposed request. It specifies canonical absolute no-symlink source, project
  and state roots and one **exact** grant. The policy is a local development
  capability, **not actor authentication**; do not run this command on a
  browser, API, queue or other untrusted user's behalf. The process invoking
  the CLI must itself be trusted and locally authorized by the operator.
* Both JSON files must be regular, owner-owned, single-link, mode 0600, with
  non-symlink parent directories, at most 64 KiB. The state directory must
  already exist, mode 0700, owner-owned, separated from the source and project
  roots. A request can select only the operator-granted bytes/identity; altered
  IDs, digest, segments, bounds, mode or quota are rejected.
* The engine opens approved source segments under descriptor-pinned roots,
  compares size/hash/handle identity, writes a verified independent project
  clone (or full-copy fallback), decodes the private staged bytes and performs
  exclusive publication. It retains write-once private attempts and receipts
  under the state root. No hardlinks to media, no overwriting existing
  destinations, no source deletion, and no automatic crash cleanup.
* Standard output is **only** a small JSON object with safe `status`,
  `importId` on success, and `buildQualification:"unqualified"`, or a fixed
  refusal `code`. No root, relative source segments, ffmpeg stderr or JSON
  contents are printed. Exit code 0 = completed/duplicate/read-only verified,
  2 = refused, 3 = pending/inspection required, 4 = bounded infrastructure
  error. Neither stdout nor a historical receipt grants editing permission.

## Local synthetic run

Use pinned Node/Python/uv from README and an installed FFmpeg/FFprobe. This
creates a tiny **synthetic** still and private empty project, writes the
operator's exact-byte policy separately, and invokes the real decoder. It does
not execute any Resolve or server calls.

```sh
# From the #381 worktree root; create policy/request yourself as the local operator.
uv run --frozen python - <<'PY'
import hashlib
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

base = Path(tempfile.mkdtemp(prefix="vera381-synthetic-")).resolve()
source = base / "approved"
project = base / "project"
state = base / "private-state"
for folder in (source, project, state):
    folder.mkdir(mode=0o700)
still = source / "still.png"
subprocess.run([
    "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
    "color=c=blue:s=64x64", "-frames:v", "1", "-update", "1", str(still)
], check=True)
content = still.read_bytes()
ids = [str(uuid.uuid4()) for _ in range(4)]
request = {
    "schemaVersion": "vera-local-import-request/v1",
    "projectId": ids[0], "importId": ids[1],
    "assetId": ids[2], "mediaReferenceId": ids[3],
    "sourceRootId": "synthetic_operator",
    "sourceSegments": ["still.png"],
    "expectedContentHash": "sha256:" + hashlib.sha256(content).hexdigest(),
    "expectedSizeBytes": len(content), "maxSizeBytes": 1000000,
    "minimumFreeBytes": 0, "kind": "image", "requestedMode": "clone",
}
policy = {
    "schemaVersion": "vera-local-import-local-policy/v1",
    "sourceRootId": "synthetic_operator", "sourceRoot": str(source),
    "projectRoot": str(project), "stateRoot": str(state),
    "operatorApproved": True, "grant": request,
}
for name, value in (("request.json", request), ("policy.json", policy)):
    path = base / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream)
print("Synthetic private fixture created; directory:", base)
print("Source SHA256:", request["expectedContentHash"])
PY
# Replace DIR with the canonical directory printed above (keep it private):
DIR=/absolute/canonical/vera381-synthetic-...
uv run --frozen python -m vera_timeline_agent.local_media_import_cli \
  --policy "$DIR/policy.json" --request "$DIR/request.json"
uv run --frozen python -m vera_timeline_agent.local_media_import_cli \
  --policy "$DIR/policy.json" --request "$DIR/request.json" --verify-existing
```

On a compatible decoder/filesystem the first command returns `completed`;
otherwise it safely refuses. Running a completed import again may return
`duplicate` only after fresh receipt + bytes/probe checks. `--verify-existing`
is **read-only**: it independently reopens the project-owned file using
no-follow descriptors, verifies target bytes, inode evidence and the unchanged
private receipt, then decodes the project-owned source again. It does not
require the original source file to remain present, does not heal/reconcile
incomplete attempts and does not create missing project media. Its success
status is `verified-unqualified`, **never build-ready**. Any missing/replaced
project target, stale receipt or changed decoder facts refuses instead of
accepting the historical result.

For clips, use `kind:"clip"`, a supported synthetic local video, and add
`clipUse` to both request and exact grant:

```json
{
  "startFrame": 10,
  "endFrame": 40,
  "handleBeforeFrames": 5,
  "handleAfterFrames": 5
}
```

The decoder checks these source-frame bounds against decoded frames, but
**does not** establish target CFR mapping or a prepared-media attestation.
No source-frame-rate guessing, no automatic motion/retiming, no reference in
place, and no move operation are permitted. The exact output locator is
`Media/Local Images/<asset-id>/<original-filename>` or
`Media/Local Clips/<asset-id>/<original-filename>`, always below the
operator-pinned project root.

## Crash/inspection procedure

If a staged import is interrupted, the subsequent ordinary run refuses with
`incomplete_attempt`; its private attempt, mode record, stage and published
bytes remain untouched. A local trusted engineer must inspect source/dest
bytes, file identities, lease and attempt records before calling the
in-process `reconcile_inspected_import` API with explicitly reauthorized
approval. **The CLI intentionally has no recovery/repair switch.** Never
manually overwrite a destination or delete evidence as a routine retry.

## Frozen build handoff — unqualified until independently bound

The portable receipt is `vera-local-import-result/v1`, not a public v2
schema. It carries stable `projectId`, `assetId`, `importId`,
`mediaReferenceId`, content/probe SHA-256, owner-relative locator and
`buildQualification:"unqualified"`. The original source root, private
segments and operator grant must **never** be attached to a script document.
For future #85 authoring, a verified editor's project-document CAS may attach
only `{kind:"media_reference",mediaReferenceId}` with the appropriate
`pictureKind`. It cannot infer a clip's prepared frames or a ready binding.

For the downstream compiler, `sourceSnapshot.system:"local_import"` is an
existing allowed identity **only after separate frozen-build source/probe
binding** against present actual project media, plus the existing independent
media-preparation / requested-range / prepared-hash checks. Reverification
alone is not that binding; its result must still be treated as unqualified.
We deliberately do **not** add a TypeScript mapper that manufactures
`occurrenceResolutions`, `sourceTimeMapping`, `preparedMedia` or build
attestations from an import receipt. Frozen public schemas/goldens are
unchanged. Presenter assets (#43), UI (#85/#377), provider acquisition and
service endpoints are outside #381.

## Repeatable focused checks

```sh
uv run --frozen pytest -q tests/test_local_media_import_model.py \
  tests/test_local_media_import.py tests/test_local_media_import_cli.py
uv run --frozen pytest -q tests/test_companion_readiness.py \
  tests/test_build_media_stage.py
uv run --frozen pytest -q tests/test_issue174_media_preparation.py -m "not slow"
npm exec --workspace @vera/contracts -- vitest run \
  test/authoring-v2-schema.test.ts test/compiler-v2-bindings.test.ts \
  test/compiler-v2.test.ts
```

All file fixtures in the automated CLI tests are synthetic. Injected fake
decoders prove refusal/verification guards, **not** that FFmpeg or macOS CoW
clones work on the Producer's machine. Phase 4 owns real synthetic-machine
evidence, mutation audit, and the full fast local gate.
