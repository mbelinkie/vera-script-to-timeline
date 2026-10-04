from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_issue144_native_build import InjectedStudio, _local
from test_issue144_prepared_build import _inputs
from vera_timeline_agent.build_jobs import NeedsAction, publish_immutable_output
from vera_timeline_agent.roundtrip_build import (
    COMPILER_ENTRY,
    ROOT,
    PreparedBuild,
    _digest,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.roundtrip_native import NativeStages
from vera_timeline_agent.roundtrip_proof import ProofSession


def _visual_inputs(root: Path) -> None:
    _inputs(root)
    document = load_operator_json(root / "script-document.json")
    dependencies = load_operator_json(root / "compiler-dependencies.json")
    block = document["activeDraft"]["blocks"][1]
    block["hostVisibilitySpans"][0]["state"] = "on_camera"
    visual = block["visualEvents"][0]
    reference = "14400000-0000-4000-8000-000000000020"
    visual.update(
        source={
            "kind": "local_media",
            "mediaReferenceId": reference,
            "mediaKind": "video",
            "label": "Public synthetic W1 source",
        },
        status="ready",
        layer=2,
        audioPolicy="use_source",
    )
    dependencies["build"]["timeline"]["frameRate"] = {
        "numerator": 25,
        "denominator": 1,
    }
    dependencies["narration"][0]["timing"]["marks"][1]["timeMs"] = 1000
    publication = load_operator_json(
        ROOT / "docs/investigations/issue-141/publication-manifest.json"
    )
    files: dict[str, Path] = {}
    for name in ("base.mov", "a1_alpha.wav"):
        logical = f"out/issue149-workflow-reruns-20261002-kit-01/media/{name}"
        record = next(row for row in publication["records"] if row["source"] == logical)
        raw = (ROOT / record["published"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["publishedSha256"]
        decoded = gzip.decompress(raw) if record["compressed"] else raw
        assert hashlib.sha256(decoded).hexdigest() == record["decodedPublishedSha256"]
        files[name] = root / name
        files[name].write_bytes(decoded)
    dependencies["resolvedVisuals"] = [
        {
            "mediaReferenceId": reference,
            "source": {
                "id": "14400000-0000-4000-8000-000000000021",
                "kind": "video",
                "path": "Media/Resolved/visual.mov",
                "contentHash": _digest(files["base.mov"].read_bytes()),
                "durationFrames": 400,
                "frameRate": {"numerator": 25, "denominator": 1},
                "width": 640,
                "height": 360,
                "audioChannels": 1,
            },
            "sourceStartFrame": 0,
            "sourceAudio": {
                "source": {
                    "id": "14400000-0000-4000-8000-000000000022",
                    "kind": "audio",
                    "path": "Media/Resolved/source.wav",
                    "contentHash": _digest(files["a1_alpha.wav"].read_bytes()),
                    "durationFrames": 400,
                    "sampleRate": 48000,
                    "channels": 1,
                },
                "sourceStartFrame": 0,
            },
        }
    ]
    (root / "script-document.json").write_bytes(_receipt_bytes(document))
    (root / "compiler-dependencies.json").write_bytes(_receipt_bytes(dependencies))
    build = PreparedBuild(root)
    process = subprocess.run(
        [
            build.node,
            str(COMPILER_ENTRY),
            str(root / "script-document.json"),
            str(root / "compiler-dependencies.json"),
        ],
        capture_output=True,
        check=True,
    )
    compiled = json.loads(process.stdout)
    manifest = json.loads(compiled["manifestJson"])
    plan = load_operator_json(root / "materialization-plan.json")
    for source in manifest["sources"]:
        if source["kind"] in {"video", "audio"} and source["path"].startswith(
            "Media/Resolved/"
        ):
            origin = files["base.mov" if source["kind"] == "video" else "a1_alpha.wav"]
            plan[source["id"]] = {
                "artifactId": source["id"],
                "origin": str(origin),
                "policy": "copy",
            }
    (root / "materialization-plan.json").write_bytes(_receipt_bytes(plan))


class Boundary:
    """Fake native objects/capture, with actual compile/package/job/assembly code."""

    def __init__(self) -> None:
        self.studios: dict[str, InjectedStudio] = {}
        self.edit = False
        self.stale = False
        self.fail_rebuild = False
        self.wrong_occurrence = False
        self.requests: list[dict[str, Any]] = []

    def native(self, build: PreparedBuild) -> NativeStages:
        studio = self.studios.setdefault(build.snapshot_id, InjectedStudio(build))
        studio.lost_response = self.fail_rebuild and len(self.studios) > 1

        def inspect(package: Path, manifest: dict[str, Any]) -> dict[str, Any]:
            observed = studio.inspect(package, manifest)
            observed["projectUid"] += manifest["buildId"]
            observed["timelineUid"] += manifest["buildId"]
            return observed

        return NativeStages(
            build,
            adapter_factory=lambda _: studio,
            local_facts=_local(),
            inspector=inspect,
        )

    def capture(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        manifest = load_operator_json(Path(request["manifestPath"]))
        identity = load_operator_json(Path(request["identityPath"]))
        sources = {source["id"]: source for source in manifest["sources"]}
        items = []
        for event in manifest["events"]:
            source = sources[event["sourceId"]]
            path = (
                f"Media/Placeholders/{source['id']}.png"
                if source["kind"] == "placeholder"
                else source["path"]
            )
            mapped = identity["occurrences"][event["id"]]
            items.append(
                {
                    "eventId": event["id"],
                    **mapped,
                    "sourcePath": path,
                    "sourceHash": _digest(
                        (Path(request["packageRoot"]) / path).read_bytes()
                    ),
                    "trackId": event["trackId"],
                    "trackKind": event["trackKind"],
                    "recordRange": dict(event["recordRange"]),
                    "sourceRange": dict(event["sourceRange"])
                    if "sourceRange" in event
                    else None,
                    "available": True,
                    "enabled": True,
                    "speed": 100,
                    "linkedUids": [],
                }
            )
        pair = [
            item
            for item in items
            if next(row for row in manifest["events"] if row["id"] == item["eventId"])[
                "provenance"
            ]["authoringKind"]
            == "visual_event"
        ]
        pair[0]["linkedUids"] = [pair[1]["itemUid"]]
        pair[1]["linkedUids"] = [pair[0]["itemUid"]]
        if self.edit and request["purpose"] in {"propose", "decide", "rebuild"}:
            for item in pair:
                item["recordRange"]["durationFrames"] -= 25
                item["sourceRange"]["durationFrames"] -= 25
        observation = {
            "schemaVersion": "issue-144-observation/v1",
            "evidenceLevel": "synthetic_injected",
            "projectUid": identity["projectUid"],
            "timelineUid": identity["timelineUid"],
            "timeline": manifest["timeline"],
            "tracks": manifest["tracks"],
            "items": items,
        }
        if self.wrong_occurrence:
            items[0]["itemUid"] += "-replacement"
        return {
            "schemaVersion": "issue-144-capture-response/v1",
            "nonce": "old-nonce" if self.stale else request["nonce"],
            "requestHash": _digest(_receipt_bytes(request)),
            "observationA": observation,
            "observationB": observation,
        }


def _session(tmp_path: Path) -> tuple[ProofSession, Boundary]:
    root = tmp_path / "proof"
    _visual_inputs(root)
    boundary = Boundary()
    session = ProofSession(
        root, native_provider=boundary.native, capture=boundary.capture
    )
    assert session.run("build")["status"] == "complete"
    assert session.run("bind-baseline")["status"] == "bound"
    return session, boundary


def _accept(session: ProofSession, boundary: Boundary) -> dict[str, Any]:
    boundary.edit = True
    proposed = session.run("propose")
    report = load_operator_json(Path(proposed["reportPath"]))
    decisions = {
        "schemaVersion": "issue-144-decisions/v1",
        "reportHash": proposed["reportHash"],
        "choices": [{"proposalId": report["rows"][0]["id"], "decision": "accept"}],
    }
    (session.root / "decisions.json").write_bytes(_receipt_bytes(decisions))
    return session.run("decide")


def test_file_session_runs_actual_visual_roundtrip_and_promotes_only_after_verify(
    tmp_path: Path,
) -> None:
    session, boundary = _session(tmp_path)
    original = (session.root / "script-document.json").read_bytes()
    prior = (session.root / "baseline.json").read_bytes()
    decision = _accept(session, boundary)
    assert decision["status"] == "revised"
    assert (session.root / "baseline.json").read_bytes() == prior
    assert session.run("decide") == decision
    rebuilt = session.run("rebuild", decision_key=decision["decisionKey"])
    assert rebuilt["status"] == "complete"
    assert (session.root / "baseline.json").read_bytes() == prior
    promoted = session.run("promote", decision_key=decision["decisionKey"])
    assert promoted["status"] == "promoted"
    assert (session.root / "baseline.json").read_bytes() != prior
    assert session.run("promote", decision_key=decision["decisionKey"]) == promoted
    assert (session.root / "script-document.json").read_bytes() == original
    assert len(boundary.studios) == 2
    assert all(studio.create_count == 1 for studio in boundary.studios.values())


def test_failed_rebuild_retains_authoritative_baseline_and_old_inputs(
    tmp_path: Path,
) -> None:
    session, boundary = _session(tmp_path)
    prior = (session.root / "baseline.json").read_bytes()
    decision = _accept(session, boundary)
    boundary.fail_rebuild = True
    assert (
        session.run("rebuild", decision_key=decision["decisionKey"])["status"]
        == "waiting"
    )
    with pytest.raises(RuntimeError, match=r"verified|complete|waiting"):
        session.run("promote", decision_key=decision["decisionKey"])
    assert (session.root / "baseline.json").read_bytes() == prior
    assert all(studio.create_count == 1 for studio in boundary.studios.values())


def test_stale_nonce_cannot_authorize_proposal(tmp_path: Path) -> None:
    session, boundary = _session(tmp_path)
    prior = (session.root / "baseline.json").read_bytes()
    boundary.edit = True
    boundary.stale = True
    with pytest.raises(RuntimeError, match=r"nonce|request"):
        session.run("propose")
    assert (session.root / "baseline.json").read_bytes() == prior


def test_missing_boundary_creates_no_native_target_or_baseline(tmp_path: Path) -> None:
    root = tmp_path / "proof"
    _visual_inputs(root)
    session = ProofSession(root)
    assert session.run("build")["status"] == "waiting"
    with pytest.raises(RuntimeError, match=r"complete|verified"):
        session.run("bind-baseline")
    assert not (root / "baseline.json").exists()


def test_first_baseline_must_retain_verified_native_occurrence_identity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "proof"
    _visual_inputs(root)
    boundary = Boundary()
    session = ProofSession(
        root, native_provider=boundary.native, capture=boundary.capture
    )
    assert session.run("build")["status"] == "complete"
    boundary.wrong_occurrence = True
    with pytest.raises(RuntimeError, match=r"identity|occurrence"):
        session.run("bind-baseline")
    assert not (root / "baseline.json").exists()


def test_file_staged_capture_resumes_one_request_and_cached_response_is_not_fresh(
    tmp_path: Path,
) -> None:
    session, boundary = _session(tmp_path)
    boundary.edit = True
    session.capture = None
    with pytest.raises(NeedsAction, match="capture required"):
        session.run("propose")
    paths = [
        path
        for path in (session.root / "captures").rglob("request.json")
        if not (path.parent / "consumed.json").exists()
    ]
    assert len(paths) == 1
    request = load_operator_json(paths[0])
    response = boundary.capture(request)
    publish_immutable_output(
        paths[0].parent / "response.json", _receipt_bytes(response)
    )
    assert session.run("propose")["status"] == "proposed"
    with pytest.raises(NeedsAction, match="capture required"):
        session.run("propose")
    pending = [
        path
        for path in (session.root / "captures").rglob("request.json")
        if not (path.parent / "consumed.json").exists()
    ]
    assert len(pending) == 1
    assert load_operator_json(pending[0])["nonce"] != request["nonce"]


def test_changed_completed_decision_receipt_cannot_authorize_replay(
    tmp_path: Path,
) -> None:
    session, boundary = _session(tmp_path)
    decision = _accept(session, boundary)
    receipt = session.root / "decisions" / decision["decisionKey"] / "receipt.json"
    changed = load_operator_json(receipt)
    changed["priorIdentity"]["timelineUid"] += "-changed"
    receipt.write_bytes(_receipt_bytes(changed))
    with pytest.raises(RuntimeError, match=r"decision|receipt|binding"):
        session.run("decide")
    assert len(boundary.studios) == 1


def test_capture_reservation_refuses_symlink_parent_without_external_write(
    tmp_path: Path,
) -> None:
    from vera_timeline_agent.roundtrip_proof import _exclusive

    outside = tmp_path / "outside"
    outside.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match=r"symbolic|symlink"):
        _exclusive(alias / "capture" / "request.json", b"{}")
    assert list(outside.iterdir()) == []


def test_operator_status_has_a_successful_cli_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from vera_timeline_agent.roundtrip_proof import main

    root = tmp_path / "proof"
    _visual_inputs(root)
    monkeypatch.setattr(
        "sys.argv", ["roundtrip_proof", "status", "--proof-root", str(root)]
    )
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "unbound"


def test_missing_file_capture_reports_action_required_in_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from vera_timeline_agent.roundtrip_proof import main

    session, _ = _session(tmp_path)
    monkeypatch.setattr(
        "sys.argv", ["roundtrip_proof", "propose", "--proof-root", str(session.root)]
    )
    assert main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "needs_action"
    assert "request.json" in result["reason"]


def test_changed_observation_before_rebuild_creates_no_second_target(
    tmp_path: Path,
) -> None:
    session, boundary = _session(tmp_path)
    prior = (session.root / "baseline.json").read_bytes()
    decision = _accept(session, boundary)
    boundary.edit = False
    with pytest.raises(RuntimeError, match="observation changed"):
        session.run("rebuild", decision_key=decision["decisionKey"])
    assert len(boundary.studios) == 1
    assert (session.root / "baseline.json").read_bytes() == prior


def test_interruption_after_pointer_publish_finishes_same_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vera_timeline_agent.roundtrip_proof as proof

    session, boundary = _session(tmp_path)
    decision = _accept(session, boundary)
    session.run("rebuild", decision_key=decision["decisionKey"])
    old_pointer = (session.root / "baseline.json").read_bytes()
    replace = proof._replace_pointer

    def interrupted(path: Path, value: dict[str, Any]) -> None:
        replace(path, value)
        raise RuntimeError("interrupted after pointer publication")

    monkeypatch.setattr(proof, "_replace_pointer", interrupted)
    with pytest.raises(RuntimeError, match="interrupted"):
        session.run("promote", decision_key=decision["decisionKey"])
    new_pointer = (session.root / "baseline.json").read_bytes()
    assert new_pointer != old_pointer
    monkeypatch.setattr(proof, "_replace_pointer", replace)
    promoted = session.run("promote", decision_key=decision["decisionKey"])
    assert (session.root / "baseline.json").read_bytes() == new_pointer
    assert session.run("promote", decision_key=decision["decisionKey"]) == promoted
    assert len(boundary.studios) == 2
    assert all(studio.create_count == 1 for studio in boundary.studios.values())


@pytest.mark.parametrize("failure", ["timeout", "abnormal_exit"])
def test_cli_process_fault_cannot_masquerade_as_semantic_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    import subprocess

    from vera_timeline_agent.roundtrip_proof import ENTRY, main

    root = tmp_path / "proof"
    _visual_inputs(root)
    session = ProofSession(root)
    inputs = root / "fault-inputs.json"
    inputs.write_bytes(b"{}")
    real_run = subprocess.run

    def failed_process(args: Any, **kwargs: Any) -> Any:
        if str(ENTRY) in args:
            if failure == "timeout":
                raise subprocess.TimeoutExpired(args, 300)
            return subprocess.CompletedProcess(args, 70, b"", b"synthetic child fault")
        return real_run(args, **kwargs)

    def evaluate(self: ProofSession, action: str, **kwargs: Any) -> dict[str, Any]:
        return session._semantic("propose", [inputs])

    monkeypatch.setattr(subprocess, "run", failed_process)
    monkeypatch.setattr(ProofSession, "run", evaluate)
    monkeypatch.setattr(
        "sys.argv", ["roundtrip_proof", "propose", "--proof-root", str(root)]
    )
    assert main() == 70
    assert json.loads(capsys.readouterr().out)["status"] == "fault"
