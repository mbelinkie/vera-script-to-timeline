"""Focused host-side proof for the #326 music probe preparation seam."""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path
from urllib.parse import unquote, urlparse

import opentimelineio as otio  # type: ignore[import-untyped]
import pytest
from vera_timeline_agent.v2_package import verify_v2_package

pytestmark = pytest.mark.slow
_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts/issue326_prepare_music_probe.py"
_NODE = Path(
    "/Users/matthewbelinkie/.local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin/node"
)


def _prepare(root: Path, *cases: str) -> None:
    if not _NODE.is_file() or _NODE.is_symlink():
        pytest.skip("pinned Node 24.19.0 is unavailable on this host")
    version = subprocess.run(
        [str(_NODE), "--version"],
        capture_output=True,
        timeout=5,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(_NODE.parent)},
    )
    if version.returncode != 0 or version.stdout.strip() != b"v24.19.0":
        pytest.skip("pinned Node 24.19.0 is not the active host runtime")
    command = [sys.executable, str(_SCRIPT), "--out", str(root)]
    for case in cases:
        command.extend(("--case", case))
    result = subprocess.run(
        command,
        capture_output=True,
        timeout=240,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")


def _sidecar(root: Path, case: str) -> dict[str, object]:
    path = root / "cases" / case / "music-probe.json"
    return json.loads(path.read_bytes())


def test_word_end_and_first_interruption_use_compiler_package_and_native_otio(
    tmp_path: Path,
) -> None:
    root = tmp_path / "issue326"
    _prepare(
        root,
        "word-end-b",
        "neighbor-duration-change",
        "abc-ed-first-interruption",
        "issue125-ending-row-moved",
    )

    word = _sidecar(root, "word-end-b")
    assert word["schemaVersion"] == "issue326-music-probe/v1"
    assert word["evidenceLevel"] == "probe_only"
    assert word["music"]["recordRange"] == {
        "startFrame": 0,
        "endFrame": 84,
        "durationFrames": 84,
    }
    assert word["music"]["sourceRangeSamples"] == {
        "startSample": 48_000,
        "endSample": 216_000,
    }
    compile_dependencies = json.loads(
        Path(word["base"]["manifest"]["path"])
        .with_name("compiler-dependencies-v2.json")
        .read_bytes()
    )
    b_timing = next(
        item
        for item in compile_dependencies["narrationTimingMaps"]
        if item["blockId"] == word["music"]["endRowId"]
    )
    assert word["music"]["endpointEvidence"] == {
        "kind": "word_end",
        "rowId": word["music"]["endRowId"],
        "tokenId": b_timing["tokens"][0]["tokenId"],
        "audibleEnd": {"numerator": 3, "denominator": 2},
        "recordFrame": 84,
    }
    assert word["music"]["gainDb"] == -12
    assert word["music"]["fade"] == {
        "curve": "linear",
        "fadeInFrames": 6,
        "fadeOutFrames": 6,
    }
    assert word["base"]["productionCompilerRefusal"]["code"] == (
        "ROW_AUDIO_RUNTIME_UNAVAILABLE"
    )
    assert word["base"]["verification"]["status"] == "ready_to_import"
    verification = verify_v2_package(Path(word["base"]["packageRoot"]))
    assert verification.build_id == word["base"]["buildId"]

    music_events = word["music"]["expectedNative"]["events"]
    assert len(music_events) == 11
    music_event = next(event for event in music_events if event["kind"] == "music")
    assert music_event["sourceInFrame"] == 24
    assert music_event["recordStartFrame"] == 0
    assert music_event["durationFrames"] == 84
    assert Path(music_event["sourcePath"]).is_absolute()

    derived = otio.adapters.read_from_file(word["derivedOtio"]["path"])
    music_track = next(track for track in derived.tracks if track.name == "Music")
    assert music_track.kind == otio.schema.TrackKind.Audio
    music_clip = next(
        clip for clip in music_track if isinstance(clip, otio.schema.Clip)
    )
    assert music_clip.source_range.start_time.value == 48_000
    assert music_clip.source_range.duration.value == 168_000
    assert (
        music_clip.media_reference.target_url
        == Path(word["music"]["sourcePath"]).as_uri()
    )
    for clip in derived.find_children(otio.schema.Clip):
        reference = clip.media_reference
        assert isinstance(reference, otio.schema.ExternalReference)
        assert urlparse(reference.target_url).scheme == "file"
        assert Path(unquote(urlparse(reference.target_url).path)).is_file()

    for row in word["timeline"]["rows"]:
        assert Path(row["narrationSourcePath"]).is_file()
        with wave.open(row["narrationSourcePath"], "rb") as narration:
            assert narration.getnchannels() == 1
            assert narration.getsampwidth() == 2
            assert narration.getframerate() == 48_000
            assert narration.getnframes() == row["durationFrames"] * 2_000
        visual = Path(row["visualSourcePath"]).read_bytes()
        assert visual.startswith(b"\x89PNG\r\n\x1a\n")

    neighbor = _sidecar(root, "neighbor-duration-change")
    neighbor_rows = {row["label"]: row for row in neighbor["timeline"]["rows"]}
    assert (
        neighbor_rows["A"]["recordStartFrame"],
        neighbor_rows["A"]["durationFrames"],
    ) == (
        0,
        72,
    )
    assert (
        neighbor_rows["B"]["recordStartFrame"],
        neighbor_rows["B"]["durationFrames"],
    ) == (
        72,
        48,
    )
    assert neighbor["music"]["recordRange"] == {
        "startFrame": 0,
        "endFrame": 120,
        "durationFrames": 120,
    }
    assert neighbor["music"]["sourceRangeSamples"] == {
        "startSample": 48_000,
        "endSample": 288_000,
    }

    interrupted = _sidecar(root, "abc-ed-first-interruption")
    before = json.loads(Path(interrupted["authoringSnapshot"]["path"]).read_bytes())[
        "rowAudioSpans"
    ][0]
    after_document = json.loads(
        Path(interrupted["effectiveAuthoringSnapshot"]["path"]).read_bytes()
    )
    after = after_document["rowAudioSpans"][0]
    row_ids = {
        label: row["rowId"]
        for label, row in zip(
            ["A", "B", "C", "D", "E"],
            interrupted["timeline"]["rows"],
            strict=True,
        )
    }
    assert before["endRowId"] == row_ids["E"]
    assert after["endRowId"] == row_ids["C"]
    assert after["review"] == {
        "previousEndRowId": row_ids["E"],
        "previousSettings": before["settings"],
        "alert": "Music shortened by this move",
    }
    assert [block["id"] for block in after_document["activeDraft"]["blocks"]] == [
        row_ids[label] for label in "ABCED"
    ]
    assert interrupted["music"]["recordEndFrame"] == 144
    assert interrupted["music"]["sourceRangeSamples"]["endSample"] == 336_000

    issue125 = _sidecar(root, "issue125-ending-row-moved")
    issue125_doc = json.loads(
        Path(issue125["effectiveAuthoringSnapshot"]["path"]).read_bytes()
    )
    issue125_span = issue125_doc["rowAudioSpans"][0]
    issue125_rows = {row["label"]: row["rowId"] for row in issue125["timeline"]["rows"]}
    assert issue125_span["endRowId"] == issue125_rows["chalk-crescent"]
    assert (
        issue125_span["review"]["previousEndRowId"]
        == issue125_rows["paper-signal-frame"]
    )
    assert issue125["music"]["recordEndFrame"] == 96
