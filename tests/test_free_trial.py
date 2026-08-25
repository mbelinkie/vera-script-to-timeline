from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent.free_trial import (
    FCPXML_FILENAME,
    FCPXML_INPUT_DIRECTORY,
    OTIO_INPUT_DIRECTORY,
    build_free_trial,
    verify_fcpxml_input,
)
from vera_timeline_agent.otio_package import PackageBuildError, verify_otio_package

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/data/slice_0_2/timeline-manifest.json"
MEDIA_ROOT = ROOT / "fixtures"


def load_manifest() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(MANIFEST.read_text(encoding="utf-8")))


def write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def bytes_by_path(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_dual_trial_is_verified_self_contained_and_deterministic(
    tmp_path: Path,
) -> None:
    one = build_free_trial(MANIFEST, MEDIA_ROOT, tmp_path / "one")
    two = build_free_trial(MANIFEST, MEDIA_ROOT, tmp_path / "two")

    assert (one.event_count, one.marker_count, one.media_count) == (5, 1, 5)
    verify_otio_package(one.otio_input_dir)
    assert verify_fcpxml_input(one.fcpxml_input_dir) == (5, 1, 5)
    assert bytes_by_path(one.output_dir) == bytes_by_path(two.output_dir)
    assert len(list(one.otio_input_dir.glob("*.otio"))) == 1
    assert len(list(one.fcpxml_input_dir.glob("*.fcpxml"))) == 1
    assert not any(path.is_symlink() for path in one.output_dir.rglob("*"))
    root = ET.parse(one.fcpxml_input_dir / FCPXML_FILENAME).getroot()
    spine = root.find("./library/event/project/sequence/spine")
    assert spine is not None and [child.tag for child in spine] == ["gap"]
    clips = root.findall("./library/event/project/sequence/spine/gap/asset-clip")
    assert [clip.get("lane") for clip in clips] == ["3", "-1", "3", "3", "3"]
    assert all(
        asset.get("src", "").startswith("media/")
        for asset in root.findall("./resources/asset")
    )
    assert len(root.findall("./library/event/project/sequence/spine/gap/marker")) == 1


def test_fcpxml_preserves_alternate_settings_and_track_map(tmp_path: Path) -> None:
    manifest = copy.deepcopy(load_manifest())
    manifest["timeline"].update(
        {
            "frameRate": {"numerator": 24, "denominator": 1},
            "width": 1280,
            "height": 720,
            "audioSampleRate": 44100,
        }
    )
    for source in manifest["sources"]:
        if source["kind"] == "video":
            source["frameRate"] = {"numerator": 24, "denominator": 1}
    manifest["tracks"] = [
        {"id": "voice-custom", "kind": "audio", "index": 4, "name": "Voice"},
        {"id": "picture-custom", "kind": "video", "index": 7, "name": "Pictures"},
    ]
    for event in manifest["events"]:
        event["trackId"] = (
            "picture-custom" if event["trackKind"] == "video" else "voice-custom"
        )
    adjusted = write_manifest(tmp_path / "adjusted.json", manifest)

    result = build_free_trial(adjusted, MEDIA_ROOT, tmp_path / "adjusted")

    assert verify_fcpxml_input(result.fcpxml_input_dir) == (5, 1, 5)
    xml = (result.fcpxml_input_dir / FCPXML_FILENAME).read_text()
    assert 'frameDuration="1/24s"' in xml
    assert 'width="1280" height="720"' in xml
    assert 'audioRate="44.1k"' in xml
    assert xml.index("Voice") < xml.index("Pictures")


def test_fcpxml_verifier_rejects_semantic_and_media_tampering(tmp_path: Path) -> None:
    result = build_free_trial(MANIFEST, MEDIA_ROOT, tmp_path / "trial")
    fcpxml = result.fcpxml_input_dir / FCPXML_FILENAME
    fcpxml.write_text(
        fcpxml.read_text().replace(
            'offset="0/1s" start="1001/12000s"',
            'offset="1001/24000s" start="1001/12000s"',
            1,
        )
    )
    with pytest.raises(PackageBuildError, match="events differ"):
        verify_fcpxml_input(result.fcpxml_input_dir)

    result = build_free_trial(MANIFEST, MEDIA_ROOT, tmp_path / "lane-tamper")
    fcpxml = result.fcpxml_input_dir / FCPXML_FILENAME
    fcpxml.write_text(fcpxml.read_text().replace('lane="3"', 'lane="4"', 1))
    with pytest.raises(PackageBuildError, match="events differ"):
        verify_fcpxml_input(result.fcpxml_input_dir)

    result = build_free_trial(MANIFEST, MEDIA_ROOT, tmp_path / "clean")
    media = next((result.fcpxml_input_dir / "media").iterdir())
    media.write_bytes(media.read_bytes() + b"tampered")
    with pytest.raises(PackageBuildError, match="hash mismatch"):
        verify_fcpxml_input(result.fcpxml_input_dir)


def test_fcpxml_verifier_rejects_transition_and_duplicate_identities(
    tmp_path: Path,
) -> None:
    result = build_free_trial(MANIFEST, MEDIA_ROOT, tmp_path / "transition")
    fcpxml = result.fcpxml_input_dir / FCPXML_FILENAME
    tree = ET.parse(fcpxml)
    gap = tree.getroot().find("./library/event/project/sequence/spine/gap")
    assert gap is not None
    gap.insert(1, ET.Element("transition", name="unexpected dissolve"))
    tree.write(fcpxml, encoding="utf-8", xml_declaration=True)
    with pytest.raises(PackageBuildError, match="requires hard cuts"):
        verify_fcpxml_input(result.fcpxml_input_dir)

    result = build_free_trial(MANIFEST, MEDIA_ROOT, tmp_path / "duplicate-event")
    fcpxml = result.fcpxml_input_dir / FCPXML_FILENAME
    tree = ET.parse(fcpxml)
    clips = tree.getroot().findall(
        "./library/event/project/sequence/spine/gap/asset-clip"
    )
    first_id = clips[0].find("./metadata/md[@key='vera.eventId']")
    second_id = clips[1].find("./metadata/md[@key='vera.eventId']")
    assert first_id is not None and second_id is not None
    second_id.set("value", cast(str, first_id.get("value")))
    tree.write(fcpxml, encoding="utf-8", xml_declaration=True)
    with pytest.raises(PackageBuildError, match=r"event identities.*duplicate"):
        verify_fcpxml_input(result.fcpxml_input_dir)

    result = build_free_trial(MANIFEST, MEDIA_ROOT, tmp_path / "duplicate-source")
    fcpxml = result.fcpxml_input_dir / FCPXML_FILENAME
    tree = ET.parse(fcpxml)
    assets = tree.getroot().findall("./resources/asset")
    first_source = assets[0].find("./metadata/md[@key='vera.sourceId']")
    second_source = assets[1].find("./metadata/md[@key='vera.sourceId']")
    assert first_source is not None and second_source is not None
    second_source.set("value", cast(str, first_source.get("value")))
    tree.write(fcpxml, encoding="utf-8", xml_declaration=True)
    with pytest.raises(PackageBuildError, match=r"asset/source identities.*duplicate"):
        verify_fcpxml_input(result.fcpxml_input_dir)


def test_existing_different_output_is_preserved(tmp_path: Path) -> None:
    output = tmp_path / "trial"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(PackageBuildError, match="different contents"):
        build_free_trial(MANIFEST, MEDIA_ROOT, output)
    assert sentinel.read_text() == "keep"


def test_fcpxml_verifier_rejects_symlinked_media_ancestor(tmp_path: Path) -> None:
    result = build_free_trial(MANIFEST, MEDIA_ROOT, tmp_path / "trial")
    media = result.fcpxml_input_dir / "media"
    external = tmp_path / "external-media"
    shutil.copytree(media, external)
    shutil.rmtree(media)
    media.symlink_to(external, target_is_directory=True)

    with pytest.raises(PackageBuildError, match="symbolic link"):
        verify_fcpxml_input(result.fcpxml_input_dir)


def test_documented_cli_builds_both_verified_inputs(tmp_path: Path) -> None:
    output = tmp_path / "cli-trial"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vera_timeline_agent.free_trial",
            str(MANIFEST),
            "--media-root",
            str(MEDIA_ROOT),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stderr == ""
    assert "Verified both formats against 5 events" in result.stdout
    verify_otio_package(output / OTIO_INPUT_DIRECTORY)
    verify_fcpxml_input(output / FCPXML_INPUT_DIRECTORY)
