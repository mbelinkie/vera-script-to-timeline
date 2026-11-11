"""Offline real-file selection faults for the accepted #312 A rebuild.

No Resolve host, signed historical proof, package writer or native operation is
stubbed into a falsely passing flow: these tests exercise the exact media
selection and independent hash/path refusal boundary in isolation.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_bench_revision_stage as stage
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import v2_package


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@pytest.fixture
def source_and_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, dict[str, Path], dict[str, Any]]:
    original = tmp_path / "source"
    build = original / "Builds/original-build"
    (build / "Preparation/original").mkdir(parents=True)
    (original / "Media/Resolved").mkdir(parents=True)
    (original / "Media/Narration").mkdir(parents=True)
    sources = []
    events = []
    paths: dict[str, Path] = {}
    for number in range(6):
        identifier = f"visual{number}"
        delivered = b"delivered-media-" + bytes([number])
        orig = b"original-media-" + bytes([number])
        sources.append(
            {
                "id": identifier,
                "deliveredHash": digest(delivered),
                "originalHash": digest(orig),
            }
        )
        events.append(
            {
                "eventId": f"e{number}",
                "kind": "primary_visual",
                "provenance": {"sourceId": identifier},
                "recordStart": number,
            }
        )
        path = original / "Media/Resolved" / f"{identifier}.mp4"
        path.write_bytes(delivered)
        paths[f"source:{identifier}"] = path
        path = build / "Preparation/original" / f"{identifier}.mp4"
        path.write_bytes(orig)
        paths[f"original:{identifier}"] = path
    for number in range(3):
        identifier = f"narration{number}"
        raw = b"narration-" + bytes([number])
        sources.append({"id": identifier, "narrationAudio": {"audioHash": digest(raw)}})
        events.append(
            {
                "eventId": f"n{number}",
                "kind": "narration",
                "provenance": {"sourceId": identifier},
            }
        )
        path = original / "Media/Narration" / f"{identifier}.wav"
        path.write_bytes(raw)
        paths[f"source:{identifier}"] = path
    for number in range(2):
        identifier = f"placeholder{number}"
        png = b"trusted-placeholder-png-" + bytes([number])
        treatment = {"kind": "reference", "reference": {"contentHash": digest(png)}}
        events.append(
            {
                "eventId": identifier,
                "kind": "placeholder",
                "pictureTreatment": treatment,
            }
        )
        path = original / "Media/Resolved" / f"{identifier}.png"
        path.write_bytes(png)
        paths[f"event:{identifier}"] = path
    manifest = {
        "buildId": "original-build",
        "sources": sources,
        "events": events,
        "timeline": {"width": 1920, "height": 1080},
    }
    (build / "timeline-manifest.json").write_text(json.dumps(manifest))
    revision = copy.deepcopy(manifest)
    revision["buildId"] = "new-revised-build"
    revision["events"][0]["recordStart"] = 24
    revised_path = tmp_path / "revision-manifest.json"
    revised_path.write_text(json.dumps(revision))
    monkeypatch.setattr(
        v2_package,
        "verify_v2_package",
        lambda _package: v2_package.V2PackageVerification("original-build", 11, 0, 11),
    )
    return original, revised_path, paths, revision


def test_revised_a_reuses_only_17_exact_verified_source_media(
    source_and_revision: tuple[Path, Path, dict[str, Path], dict[str, Any]],
) -> None:
    original, revised, expected, _ = source_and_revision
    assert (
        stage._revised_media_paths(original, revised, case_id="synthetic-312")
        == expected
    )


@pytest.mark.parametrize(
    "fault",
    [
        "delivered_bytes",
        "original_bytes",
        "narration_bytes",
        "changed_source_hash",
        "changed_placeholder",
        "changed_kind",
        "duplicate_media",
        "source_symlink",
        "unsupported_case",
    ],
)
def test_revised_media_rejects_wrong_tampered_or_ambiguous_source(
    source_and_revision: tuple[Path, Path, dict[str, Path], dict[str, Any]],
    fault: str,
) -> None:
    original, revised_path, paths, manifest = source_and_revision
    if fault == "delivered_bytes":
        paths["source:visual0"].write_bytes(b"mutated")
    elif fault == "original_bytes":
        paths["original:visual0"].write_bytes(b"mutated")
    elif fault == "narration_bytes":
        paths["source:narration0"].write_bytes(b"mutated")
    elif fault == "changed_source_hash":
        manifest["sources"][0]["deliveredHash"] = digest(b"other-media")
    elif fault == "changed_placeholder":
        manifest["events"][-1]["pictureTreatment"]["reference"]["contentHash"] = digest(
            b"other"
        )
    elif fault == "changed_kind":
        manifest["events"][0]["kind"] = "source_audio"
    elif fault == "duplicate_media":
        (original / "Media/Resolved/visual0.avi").write_bytes(b"other")
    elif fault == "source_symlink":
        path = paths["source:visual0"]
        destination = original / "Media/Resolved/other.mp4"
        destination.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(destination)
    if fault in {"changed_source_hash", "changed_placeholder", "changed_kind"}:
        revised_path.write_text(json.dumps(manifest))
    with pytest.raises(
        (queue.QueueError, v2_package.V2PackageError),
        match=r"media|source|event|case|placeholder|kind|ambiguous",
    ):
        stage._revised_media_paths(
            original,
            revised_path,
            case_id="wrong" if fault == "unsupported_case" else "synthetic-312",
        )
