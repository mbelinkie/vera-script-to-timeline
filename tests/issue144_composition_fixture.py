from __future__ import annotations

import copy
import gzip
import hashlib
import uuid
from pathlib import Path
from typing import Any

from issue144_omission_fixture import FrameProvider, OmissionBoundary, inputs
from test_issue144_row_narration import _compile
from vera_timeline_agent.narration.service import NarrationService
from vera_timeline_agent.roundtrip_build import (
    ROOT,
    _digest,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.roundtrip_proof import ProofSession


def setup(
    tmp_path: Path,
) -> tuple[ProofSession, CompositionBoundary, FrameProvider, NarrationService]:
    root = tmp_path / "proof"
    service, provider, row_id = inputs(root)
    doc = load_operator_json(root / "script-document.json")
    deps = load_operator_json(root / "compiler-dependencies.json")
    row = next(b for b in doc["activeDraft"]["blocks"] if b["id"] == row_id)
    move = row["visualEvents"][1]
    move["range"].update(
        startTokenId=row["tokens"][3]["id"],
        endTokenId=row["tokens"][4]["id"],
        quotedText="Delta Echo",
    )
    trim = copy.deepcopy(move)
    trim["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "composition/trim"))
    trim["layer"] = 4
    trim["range"].update(
        startTokenId=row["tokens"][6]["id"],
        endTokenId=row["tokens"][7]["id"],
        quotedText="Golf Hotel",
    )
    reference = str(uuid.uuid5(uuid.NAMESPACE_URL, "composition/trim/reference"))
    trim["source"]["mediaReferenceId"] = reference
    row["visualEvents"].append(trim)
    publication = load_operator_json(
        ROOT / "docs/investigations/issue-141/publication-manifest.json"
    )
    origins = {}
    for name in ("cutaway.mov", "a2_numbers.wav"):
        logical = f"out/issue149-workflow-reruns-20261002-kit-01/media/{name}"
        record = next(r for r in publication["records"] if r["source"] == logical)
        raw = (ROOT / record["published"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["publishedSha256"]
        decoded = gzip.decompress(raw) if record["compressed"] else raw
        assert hashlib.sha256(decoded).hexdigest() == record["decodedPublishedSha256"]
        origins[name] = root / name
        origins[name].write_bytes(decoded)
    resolved = copy.deepcopy(deps["resolvedVisuals"][0])
    resolved["mediaReferenceId"] = reference
    resolved["source"]["audioChannels"] = 0
    for source, name, path in (
        (resolved["source"], "cutaway.mov", "Media/Resolved/trim.mov"),
        (
            resolved["sourceAudio"]["source"],
            "a2_numbers.wav",
            "Media/Resolved/trim.wav",
        ),
    ):
        source.update(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"composition/{name}")),
            path=path,
            contentHash=_digest(origins[name].read_bytes()),
        )
    deps["resolvedVisuals"].append(resolved)
    (root / "script-document.json").write_bytes(_receipt_bytes(doc))
    (root / "compiler-dependencies.json").write_bytes(_receipt_bytes(deps))
    manifest = _compile(root, "node")
    plan = load_operator_json(root / "materialization-plan.json")
    for source in manifest["sources"]:
        for name, path in (
            ("cutaway.mov", "Media/Resolved/trim.mov"),
            ("a2_numbers.wav", "Media/Resolved/trim.wav"),
        ):
            if source["path"] == path:
                plan[source["id"]] = {
                    "artifactId": source["id"],
                    "origin": str(origins[name]),
                    "policy": "copy",
                }
    (root / "materialization-plan.json").write_bytes(_receipt_bytes(plan))
    boundary = CompositionBoundary(row_id, move["id"], trim["id"])
    session = ProofSession(
        root,
        native_provider=boundary.native,
        capture=boundary.capture,
        omission_evidence=boundary.evidence,
        narration_service=service,
    )
    built = session.run("build")
    assert built["status"] == "complete", built
    session.run("bind-baseline")
    (root / "omission-request.json").write_bytes(
        _receipt_bytes(
            {"schemaVersion": "issue-144-composed-request/v1", "rowId": row_id}
        )
    )
    return session, boundary, provider, service


class CompositionBoundary(OmissionBoundary):
    def __init__(self, row_id: str, move_id: str, trim_id: str) -> None:
        super().__init__(row_id)
        self.move_id, self.trim_id = move_id, trim_id

    def capture(self, request: dict[str, Any]) -> dict[str, Any]:
        change = self.change
        self.change = None
        try:
            result = super().capture(request)
        finally:
            self.change = change
        if (
            self.edit
            and request["schemaVersion"] == "issue-144-omission-capture-request/v1"
            and request["purpose"] != "bind-omission-evidence"
        ):
            manifest = load_operator_json(Path(request["manifestPath"]))
            identity = load_operator_json(Path(request["identityPath"]))
            items = result["observationA"]["items"]
            for event in manifest["events"]:
                authored = event["provenance"]["authoringId"]
                if authored not in (self.move_id, self.trim_id):
                    continue
                uid = identity["occurrences"][event["id"]]["itemUid"]
                item = next(i for i in items if i["itemUid"] == uid)
                if authored == self.move_id:
                    item["recordRange"]["startFrame"] += 25
                else:
                    item["recordRange"]["durationFrames"] -= 25
                    item["sourceRange"]["durationFrames"] -= 25
        if (
            change
            and request["schemaVersion"] == "issue-144-omission-capture-request/v1"
        ):
            change(result["observationA"])
        return result


def decisions(session: ProofSession, report_hash: str, choice: str = "accept") -> None:
    (session.root / "omission-decisions.json").write_bytes(
        _receipt_bytes(
            {
                "schemaVersion": "issue-144-composed-decisions/v1",
                "reportHash": report_hash,
                "choice": choice,
            }
        )
    )
