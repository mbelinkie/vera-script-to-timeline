"""Generated kept Music through ordinary Prep Media, compiler and signed package."""

from __future__ import annotations

import hashlib
import json
import wave
from fractions import Fraction
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from test_issue603_still_preparation import _descriptor
from vera_timeline_agent import prep_media_inputs
from vera_timeline_agent.build_jobs import BuildJobError
from vera_timeline_agent.build_timeline_once import (
    BuildOptions,
    StageTimings,
    compile_prepared,
    package_compiled,
)
from vera_timeline_agent.local_media_import import FFmpegDecoder
from vera_timeline_agent.music_input import music_event_id
from vera_timeline_agent.prep_media import prepare_project
from vera_timeline_agent.research_music import prepare_selection
from vera_timeline_agent.v2_package import _compiler_hash

_FIXTURE = (
    Path(__file__).parent
    / "data/authoring_v2/issue_173/compiler"
    / "visual-only-image-still-25fps-default.input.golden.json"
)


def prepare_fixture(root: Path) -> tuple[Path, dict[str, Any], Path]:
    case = json.loads(_FIXTURE.read_bytes())
    document, deps = case["document"], case["dependencies"]
    media = root / "Media"
    media.mkdir(parents=True)
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        writer.writeframes(
            b"\0\0" * 48_000 + b"\x34\x12" * 192_000 + b"\xff\x00" * 48_000
        )
    raw = buffer.getvalue()
    selection = {
        "researchProjectId": "20000000-0000-4000-8000-000000000001",
        "itemId": "20000000-0000-4000-8000-000000000002",
        "sourceId": "20000000-0000-4000-8000-000000000003",
        "itemVersion": 3,
        "sourceVersion": 2,
        "title": "Generated music",
        "startMs": 1000,
        "endMs": 5000,
        "playbackHash": "sha256:" + hashlib.sha256(raw).hexdigest(),
    }
    request = {
        "projectId": document["projectId"],
        "selection": selection,
        "mimeType": "audio/wav",
    }
    prepared = prepare_selection(media, request, BytesIO(raw))
    assert prepare_selection(media, request, BytesIO(raw)) == prepared
    source = prepared["source"]
    row = document["activeDraft"]["blocks"][0]
    row["payload"]["imageMotion"] = {"mode": "none"}
    original_still = media / "still.png"
    Image.new("RGB", (1600, 900), (84, 46, 124)).save(original_still)
    with original_still.open("rb") as still:
        still_facts = FFmpegDecoder().decode(still.fileno(), "image")
    previous = deps["occurrenceResolutions"][0]
    descriptor = _descriptor(original_still, still_facts, Fraction(24))
    for key in ("payloadId", "owner", "mediaReferenceId"):
        descriptor[key] = previous[key]
    deps["occurrenceResolutions"] = [descriptor]
    deps["preparedMedia"] = []
    span_id = "20000000-0000-4000-8000-000000000004"
    document["rowAudioSpans"] = [
        {
            "id": span_id,
            "startRowId": row["id"],
            "endRowId": row["id"],
            "source": source,
            "settings": {"gainDb": -12},
        }
    ]
    document.pop("liveContentHash")
    document["liveContentHash"] = _compiler_hash(document)
    deps["document"]["contentHash"] = document["liveContentHash"]
    deps["timeline"]["frameRate"] = {"numerator": 24, "denominator": 1}
    inputs = root / "settings"
    inputs.mkdir()
    script = inputs / "script.json"
    script.write_text(json.dumps(document))
    (inputs / "compiler-dependencies.json").write_text(json.dumps(deps))
    (inputs / "media-paths.json").write_text(
        json.dumps({f"source:{descriptor['mediaReferenceId']}": str(original_still)})
    )
    handoff = prepare_project(
        script, inputs, root, acquire=lambda _: None, narration=lambda *_: None
    )
    locator = f"event:{music_event_id(document['id'], span_id, source['artifactId'])}"
    audio = Path(json.loads((handoff / "media-paths.json").read_bytes())[locator])
    assert audio.is_relative_to(media)
    with wave.open(str(audio), "rb") as wav:
        assert (
            wav.getframerate(),
            wav.getnchannels(),
            wav.getsampwidth(),
            wav.getnframes(),
        ) == (48000, 1, 2, 192000)
        assert wav.readframes(192000) == b"\x34\x12" * 192000
    return handoff, source, audio


@pytest.mark.slow
def test_research_music_freezes_exact_saved_selection_and_packages_a5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The generated picture uses Linux's test FFmpeg. Native acceptance uses
    # the qualified workstation toolchain with the normal gate enabled.
    monkeypatch.setattr(prep_media_inputs, "_qualified_tools", lambda _: None)
    handoff, source, audio = prepare_fixture(tmp_path)
    frozen = json.loads((handoff / "compiler-dependencies.json").read_bytes())
    assert frozen["musicBindings"][0]["source"] == source
    assert frozen["musicBindings"][0]["durationSamples"] == 192000
    options = BuildOptions(handoff / "script.json", tmp_path / "build", handoff)
    compiled = compile_prepared(options)
    package, _, _ = package_compiled(compiled, timings=StageTimings())
    event = next(
        event for event in package.manifest["events"] if event["kind"] == "music"
    )
    assert event["trackId"] == "music-a5"
    assert (
        event["sourceRange"]
        == event["recordRange"]
        == {"startFrame": 0, "endFrame": 72}
    )
    assert event["music"]["audioHash"] == source["contentHash"]
    manifest_source = next(
        s
        for s in package.manifest["sources"]
        if s["id"] == event["provenance"]["sourceId"]
    )
    assert manifest_source["musicAudio"] == frozen["musicBindings"][0]

    settings = tmp_path / "settings"
    script = settings / "script.json"
    document = json.loads(script.read_bytes())
    deps_path = settings / "compiler-dependencies.json"
    deps = json.loads(deps_path.read_bytes())
    document["rowAudioSpans"][0]["source"]["researchSelection"]["itemVersion"] += 1
    document.pop("liveContentHash")
    document["liveContentHash"] = deps["document"]["contentHash"] = _compiler_hash(
        document
    )
    script.write_text(json.dumps(document))
    deps_path.write_text(json.dumps(deps))
    with pytest.raises(BuildJobError, match="provenance"):
        prepare_project(
            script,
            settings,
            tmp_path,
            acquire=lambda _: None,
            narration=lambda *_: None,
        )

    audio.unlink()
    with pytest.raises(BuildJobError, match="previously ready music disappeared"):
        compile_prepared(
            BuildOptions(handoff / "script.json", tmp_path / "missing", handoff)
        )
