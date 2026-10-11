from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import workflow_delivery
from vera_timeline_agent.studio_spike import PublicResolveAdapter
from vera_timeline_agent.workflow_delivery_cli import (
    LAUNCHER_NAME,
    RELEASE_NAME,
    build_release,
)
from vera_timeline_agent.workflow_package import (
    read_object,
    sha256,
    write_immutable_json,
)


def _request(release: Path, evidence: Path, package: Path) -> Path:
    return write_immutable_json(
        release / RELEASE_NAME / "request.json",
        {
            "schemaVersion": "vera-injected-delivery-request/v1",
            "releaseSha256": sha256(release / RELEASE_NAME / "release.json"),
            "attestationPath": str(package.parent / "missing-attestation.json"),
            "attestationSha256": "0" * 64,
            "packageDir": str(package),
            "projectName": "missing-target",
            "timelineName": "missing-target",
            "evidenceDir": str(evidence),
            "action": "preflight",
            "authorizeNewNonproduction": False,
            "externalScripting": "None",
        },
    )


def _launch(release: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-S", str(release / LAUNCHER_NAME)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_release_is_reproducible_and_refuses_replacement(tmp_path: Path) -> None:
    one = build_release(tmp_path / "one")
    two = build_release(tmp_path / "two")
    assert one.read_bytes() == two.read_bytes()
    with pytest.raises(FileExistsError):
        build_release(tmp_path / "one")
    assert one.read_bytes() == two.read_bytes()


def test_installed_launcher_retains_unique_missing_attestation_reports(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    package = tmp_path / "package"
    package.mkdir()
    _request(release, evidence, package)
    first = _launch(release)
    second = _launch(release)
    assert first.stdout != second.stdout
    reports = list(evidence.glob("result-*.json"))
    assert len(reports) == 2
    for path in reports:
        result = read_object(path)
        assert result["status"] == "stopped_safely"
        assert result["verified"] is False
        assert result["partialTargetRetained"] is False
        assert result["injectedObjectAvailable"] is False
    hashes = [read_object(path) for path in evidence.glob("hashes-*.json")]
    assert {item["resultSha256"] for item in hashes} == {sha256(p) for p in reports}
    assert list(package.iterdir()) == []


def test_request_package_mismatch_cannot_write_evidence_into_ready_input(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    package = tmp_path / "ready-package"
    package.mkdir()
    declared = tmp_path / "wrong-package"
    request = _request(release, package, declared)
    value = read_object(request)
    write_immutable_json(Path(value["attestationPath"]), {"packageDir": str(package)})
    result = json.loads(_launch(release).stdout)
    assert result["status"] == "workflow_launcher_failed"
    assert result["reportRetention"].startswith("unavailable")
    assert list(package.iterdir()) == []


@pytest.mark.parametrize("tamper", ["source", "release", "extra", "bytecode"])
def test_bootstrap_integrity_refuses_before_import(
    tmp_path: Path,
    tamper: str,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    package = tmp_path / "package"
    package.mkdir()
    _request(release, evidence, package)
    runtime = release / RELEASE_NAME / "python" / "vera_timeline_agent"
    if tamper == "source":
        with (runtime / "workflow_delivery.py").open("a") as stream:
            stream.write("\nraise AssertionError('unverified code executed')\n")
    elif tamper == "release":
        path = release / RELEASE_NAME / "release.json"
        path.chmod(0o600)
        path.write_text("{}")
    elif tamper == "extra":
        (runtime / "unexpected.py").write_text("raise AssertionError('extra source')")
    else:
        (runtime / "stale.pyc").write_bytes(b"stale")
    result = json.loads(_launch(release).stdout)
    assert result["status"] == "workflow_launcher_failed"
    assert list(evidence.glob("bootstrap-refusal-*.json"))
    assert not list(evidence.glob("started-*.json"))
    assert list(package.iterdir()) == []


def test_readback_checks_unused_media_paths_and_extra_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(PublicResolveAdapter, "verify", lambda *_: ())

    class Media:
        def __init__(self, identity: str, path: str) -> None:
            self.identity, self.path = identity, path

        def GetMediaId(self) -> str:
            return self.identity

        def GetClipProperty(self, key: str) -> str:
            assert key == "File Path"
            return self.path

    media = [Media("used", "/package/used.mov"), Media("unused", "/wrong/path.mov")]

    class Folder:
        def GetClipList(self) -> list[Media]:
            return media

    class Pool:
        def GetRootFolder(self) -> Folder:
            return Folder()

    class Timeline:
        def GetMediaPoolItem(self) -> Media:
            return Media("timeline", "")

        def GetMarkers(self) -> dict[int, dict[str, Any]]:
            return {3: {}, 4: {}}

    adapter = workflow_delivery.PublicResolveAdapter(object())
    adapter.pool, adapter.timeline = Pool(), Timeline()
    adapter.media_id_by_source = {"used-source": "used", "unused-source": "unused"}
    adapter.expected_paths = {
        "used-source": "/package/used.mov",
        "unused-source": "/package/unused.mov",
    }
    manifest = {
        "sources": [{"id": "used-source"}, {"id": "unused-source"}],
        "markers": [{"frame": 3}],
    }
    assert adapter.verify(manifest) == (
        "marker inventory differs from manifest",
        "source unused-source: reopened media identity differs",
    )
    media[1].path = "/package/unused.mov"
    media.append(Media("timeline", ""))
    assert adapter.verify(manifest) == ("marker inventory differs from manifest",)
    media.append(Media("extra", "/package/extra.mov"))
    assert "package media count differs from manifest" in adapter.verify(manifest)


def test_readback_verifies_source_endpoint_in_source_rate_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(PublicResolveAdapter, "verify", lambda *_: ())

    class Item:
        source_end = 30

        def GetStart(self, _: bool) -> int:
            return 0

        def GetSourceEndFrame(self) -> int:
            return self.source_end

    item = Item()

    class Timeline:
        def GetItemListInTrack(self, *_: object) -> list[Item]:
            return [item]

        def GetMarkers(self) -> dict[int, object]:
            return {}

        def GetMediaPoolItem(self) -> None:
            return None

    class Folder:
        def GetClipList(self) -> list[object]:
            return []

    class Pool:
        def GetRootFolder(self) -> Folder:
            return Folder()

    adapter = workflow_delivery.PublicResolveAdapter(object())
    adapter.timeline, adapter.pool = Timeline(), Pool()
    manifest = {
        "sources": [],
        "markers": [],
        "tracks": [{"id": "v1", "kind": "video", "index": 1}],
        "events": [
            {
                "id": "event-1",
                "trackId": "v1",
                "recordRange": {"startFrame": 0, "durationFrames": 24},
                "sourceRange": {"startFrame": 2, "durationFrames": 30},
            }
        ],
    }
    assert adapter.verify(manifest) == ("event event-1: source end mismatch",)
    item.source_end = 31
    assert adapter.verify(manifest) == ()
