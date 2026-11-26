from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from vera_timeline_agent.media_preparation import MediaTools
from vera_timeline_agent.prep_media import failed_fetch_slate
from vera_timeline_agent.research_cut_binding import (
    Json,
    bind_narrated_research_cut,
    bind_research_cut,
    copy_cut,
    cut_identity,
    verify_cut,
)

CLIP_ID = "d3e55d4a-72a9-4900-92a0-033d184a7cc8"
SNAPSHOT: Json = {
    "clipId": CLIP_ID,
    "researchProjectId": "project",
    "catalogVideoId": "catalog",
    "video": {"youtubeVideoId": "abcdefghijk"},
    "loggedSelection": {
        "trackId": "track",
        "transcriptVersion": 1,
        "exportStartMs": 117,
        "exportEndMs": 1129,
    },
}


def _cut(path: Path) -> Path:
    path.mkdir()
    artifacts = []
    for name in (f"{CLIP_ID}.mp4", f"{CLIP_ID}.en.srt"):
        data = name.encode()
        (path / name).write_bytes(data)
        artifacts.append(
            {
                "name": name,
                "byteSize": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    (path / f"{CLIP_ID}.json").write_text(
        json.dumps({**cut_identity(SNAPSHOT), "artifacts": artifacts})
    )
    return path


def test_copy_verifies_selection_and_existing_bytes(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    cut = _cut(root / "research")
    (cut / ".DS_Store").write_bytes(b"Finder metadata")
    dest = root / "timeline"
    copied = copy_cut(cut, SNAPSHOT, dest)
    assert not (copied / ".DS_Store").exists()
    assert copy_cut(cut, SNAPSHOT, dest) == copied
    assert verify_cut(cut, SNAPSHOT)[1] == verify_cut(copied, SNAPSHOT)[1]
    wrong = {
        **SNAPSHOT,
        "loggedSelection": {**SNAPSHOT["loggedSelection"], "exportEndMs": 1200},
    }
    with pytest.raises(ValueError, match="frozen clip selection"):
        verify_cut(copied, wrong)
    (copied / f"{CLIP_ID}.mp4").write_bytes(b"changed")
    with pytest.raises(ValueError, match="byte verification"):
        copy_cut(cut, SNAPSHOT, dest)
    assert (cut / f"{CLIP_ID}.mp4").read_bytes() == f"{CLIP_ID}.mp4".encode()


def test_failed_clip_uses_label_and_logged_duration_without_claiming_frames() -> None:
    row: Json = {
        "researchClip": {
            **SNAPSHOT,
            "video": {**SNAPSHOT["video"], "title": "Missing\npublic source"},
        },
        "payload": {"kind": "visual", "pictureKind": "unresolved_visual"},
    }
    failed_fetch_slate(row)
    assert row["payload"]["source"] == {
        "kind": "intentional_placeholder",
        "text": "Unavailable: Missing public source",
    }
    assert row["visualOnlyTiming"] == {
        "kind": "visual_only",
        "durationOverrideMs": 1012,
    }
    assert "frameBinding" not in row


def test_bound_research_use_range_survives_rebinding_without_changing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A verified full cut is reused; placements keep separate inward intervals."""
    import vera_timeline_agent.research_cut_binding as binder

    digest = "sha256:" + "a" * 64
    probe = "sha256:" + "b" * 64
    video = tmp_path / f"{CLIP_ID}.mp4"
    video.write_bytes(b"synthetic inspected fixture")
    monkeypatch.setattr(binder, "verify_cut", lambda _folder, _snap: (video, digest))
    media = SimpleNamespace(
        content_hash=digest,
        probe_hash=probe,
        video_frames=[None] * 96,
        video={},
        audio={"index": 1, "sample_rate": 48000},
        audio_origin=Fraction(0),
        audio_hash="sha256:" + "c" * 64,
        rate=Fraction(24),
        pts_origin=Fraction(0),
        time_base=Fraction(1, 24),
    )
    monkeypatch.setattr(binder, "inspect_media", lambda *_args, **_kwargs: media)
    snapshot = {**SNAPSHOT, "clipVersion": 7}
    first: Json = {
        "id": "00000000-0000-4000-8000-000000000021",
        "researchClip": snapshot,
        "payload": {"payloadId": "00000000-0000-4000-8000-000000000022"},
        "visualOnlyTiming": {"kind": "visual_only"},
    }
    second = json.loads(json.dumps(first))
    second["id"] = "00000000-0000-4000-8000-000000000031"
    second["payload"]["payloadId"] = "00000000-0000-4000-8000-000000000032"
    binder.bind_research_cut(first, tmp_path, MediaTools())
    binder.bind_research_cut(second, tmp_path, MediaTools())
    assert first["frameBinding"] == second["frameBinding"]
    assert first["visualOnlyTiming"]["selectedSourceRange"] == {
        "startFrame": 0,
        "durationFrames": 96,
    }
    first["visualOnlyTiming"]["selectedSourceRange"] = {
        "startFrame": 24,
        "durationFrames": 36,
    }
    _, _, descriptor = bind_research_cut(first, tmp_path, MediaTools())
    assert descriptor["occurrenceSourceInFrame"] == 24
    assert descriptor["selectedSourceRange"] == {"startFrame": 24, "endFrame": 60}
    assert descriptor["logicalSourceBounds"] == {
        "startFrame": 0,
        "endFrame": 96,
        "frameRate": {"numerator": 24, "denominator": 1},
    }
    assert second["visualOnlyTiming"]["selectedSourceRange"] == {
        "startFrame": 0,
        "durationFrames": 96,
    }
    assert first["researchClip"] == second["researchClip"] == snapshot

    first["visualOnlyTiming"]["selectedSourceRange"] = {
        "startFrame": 24,
        "durationFrames": 73,
    }
    with pytest.raises(ValueError, match="outside the verified cut"):
        bind_research_cut(first, tmp_path, MediaTools())

    # A stale or substituted frame binding cannot silently retarget this use.
    first["visualOnlyTiming"]["selectedSourceRange"] = {
        "startFrame": 24,
        "durationFrames": 36,
    }
    forged = json.loads(json.dumps(first))
    forged["frameBinding"]["mediaReferenceId"] = "00000000-0000-4000-8000-000000000099"
    with pytest.raises(ValueError, match="does not match the verified cut"):
        bind_research_cut(forged, tmp_path, MediaTools())
    assert forged["visualOnlyTiming"]["selectedSourceRange"] == {
        "startFrame": 24,
        "durationFrames": 36,
    }


def test_narrated_occurrence_uses_actual_slot_and_independent_ranges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vera_timeline_agent.research_cut_binding as binder
    from vera_timeline_agent.prep_media import _narrated_research_occurrences

    snapshot = {**SNAPSHOT, "clipVersion": 7}
    digest = "sha256:" + "a" * 64
    probe = "sha256:" + "b" * 64
    video = tmp_path / "fixture.mp4"
    monkeypatch.setattr(binder, "verify_cut", lambda *_: (video, digest))
    monkeypatch.setattr(
        binder,
        "inspect_media",
        lambda *_args, **_kwargs: SimpleNamespace(
            content_hash=digest,
            probe_hash=probe,
            video_frames=[None] * 96,
            audio={"index": 1, "sample_rate": 48000},
            audio_origin=Fraction(0),
            audio_hash="sha256:" + "c" * 64,
            rate=Fraction(24000, 1001),
            pts_origin=Fraction(0),
            time_base=Fraction(1001, 24000),
        ),
    )
    clip = {
        "id": "clip",
        "researchClip": snapshot,
        "payload": {"payloadId": "one"},
        "visualOnlyTiming": {},
    }
    bind_research_cut(clip, tmp_path, MediaTools())
    payloads = [
        dict(
            clip["payload"],
            payloadId=key,
            researchClip=snapshot,
            frameBinding=clip["frameBinding"],
            selectedSourceRange={"startFrame": start, "durationFrames": 12},
            sourceUsage={"sourceInFrame": start},
        )
        for key, start in [("one", 12), ("two", 36)]
    ]
    sequence = {
        "id": "seq",
        "slots": [
            {"kind": "content", "id": key, "payload": payload}
            for key, payload in zip(["slot-one", "slot-two"], payloads, strict=True)
        ],
    }
    row = {
        "type": "narration",
        "state": "active",
        "primaryVisualSequence": sequence,
        "attachedFootage": {"clip": clip},
        "unattachedVisuals": [{"payload": payloads[0]}],
    }
    document = {"activeDraft": {"blocks": [row, dict(row, state="inactive")]}}
    frozen = json.dumps(document)
    results = [
        bind_narrated_research_cut(payload, owner, tmp_path, MediaTools())[2]
        for payload, owner in _narrated_research_occurrences(document)
    ]
    assert [item["owner"]["slotId"] for item in results] == ["slot-one", "slot-two"]
    assert [item["selectedSourceRange"] for item in results] == [
        {"startFrame": 12, "endFrame": 24},
        {"startFrame": 36, "endFrame": 48},
    ]
    assert results[0]["logicalSourceBounds"]["frameRate"] == {
        "numerator": 24000,
        "denominator": 1001,
    }
    assert json.dumps(document) == frozen
    with pytest.raises(ValueError, match="needs a verified binding"):
        bind_narrated_research_cut(
            dict(payloads[0], frameBinding=None),
            results[0]["owner"],
            tmp_path,
            MediaTools(),
        )


@pytest.mark.slow
def test_cached_numbered_research_cut_reaches_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run real Prep Media, compile and verify both package representations."""
    import subprocess
    from functools import partial

    import opentimelineio as otio

    from vera_timeline_agent import prep_media_inputs
    from vera_timeline_agent.build_compiler_bridge import invoke_bridge
    from vera_timeline_agent.media_preparation import _prepare_media
    from vera_timeline_agent.prep_media import prepare_project
    from vera_timeline_agent.research_cut_binding import research_clip_folder
    from vera_timeline_agent.v2_package import build_v2_package

    fixture_path = (
        Path(__file__).parent
        / "data/authoring_v2/issue_173/compiler"
        / "visual-only-image-still-25fps-default.input.golden.json"
    )
    fixture = json.loads(fixture_path.read_bytes())
    document, dependencies = fixture["document"], fixture["dependencies"]
    first = document["activeDraft"]["blocks"][0]
    snapshot = {
        **SNAPSHOT,
        "clipVersion": 7,
        "researchProjectId": CLIP_ID,
        "catalogVideoId": CLIP_ID,
        "video": {
            **SNAPSHOT["video"],
            "canonicalUrl": "https://youtu.be/abcdefghijk",
            "title": "Generated numbered cut",
        },
        "loggedSelection": {
            **SNAPSHOT["loggedSelection"],
            "trackId": CLIP_ID,
            "firstSegmentId": CLIP_ID,
            "lastSegmentId": CLIP_ID,
            "exportStartMs": 0,
            "exportEndMs": 334,
            "transcriptStartMs": 0,
            "transcriptEndMs": 300,
            "timingPrecision": "cue",
            "text": "Generated caption",
        },
        "englishText": "Generated caption",
    }
    first["researchClip"] = snapshot
    second = json.loads(json.dumps(first))
    second.update(id="00000000-0000-4000-8000-000000000031", orderKey="b0")
    second["payload"]["payloadId"] = "00000000-0000-4000-8000-000000000032"
    document["activeDraft"]["blocks"] = [first, second]
    dependencies["timeline"]["frameRate"] = {"numerator": 24000, "denominator": 1001}
    dependencies["occurrenceResolutions"] = []
    dependencies["preparedMedia"] = []

    project = tmp_path / "project"
    media_root = project / "Media"
    media_root.mkdir(parents=True)
    export = tmp_path / "export"
    export.mkdir()
    video = export / f"{CLIP_ID}.mp4"
    # A distinct brightness in each decoded frame allows byte-level inspection
    # of both delivered occurrence ranges after real transcode.
    source_frames = b"".join(
        bytes([32 + index * 24]) * (64 * 64 * 3) for index in range(8)
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "64x64",
            "-framerate",
            "24000/1001",
            "-i",
            "pipe:0",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono",
            "-vf",
            "scale=out_color_matrix=bt709,setsar=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-color_range",
            "tv",
            "-x264-params",
            "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-c:a",
            "aac",
            "-shortest",
            str(video),
        ],
        input=source_frames,
        check=True,
    )
    srt = export / f"{CLIP_ID}.en.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:00,300\nGenerated caption\n")
    (export / f"{CLIP_ID}.json").write_text(
        json.dumps(
            {
                **cut_identity(snapshot),
                "artifacts": [
                    {
                        "name": path.name,
                        "byteSize": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                    for path in [video, srt]
                ],
            }
        ),
    )
    cache = copy_cut(export, snapshot, research_clip_folder(media_root, snapshot))
    for row, start, end in [(first, 2, 5), (second, 5, 7)]:
        bind_research_cut(row, cache, MediaTools())
        row["visualOnlyTiming"]["selectedSourceRange"] = {
            "startFrame": start,
            "durationFrames": end - start,
        }
    script = tmp_path / "script.json"
    script.write_text(json.dumps(document))
    inputs = tmp_path / "dependencies"
    inputs.mkdir()
    (inputs / "compiler-dependencies.json").write_text(json.dumps(dependencies))

    # Use the same generated-media qualification mode as the installed-tool
    # tests. The public Prep Media path still requires a qualified toolset.
    monkeypatch.setattr(
        prep_media_inputs,
        "prepare_media",
        partial(_prepare_media, qualification_run=True),
    )

    def acquire(_: Json) -> Path:
        pytest.fail("The saved occurrence must reuse its verified project cut")

    def prepare() -> Path:
        return prepare_project(
            script, inputs, project, acquire=acquire, narration=lambda *_: None
        )

    prepared = prepare()
    assert prepare() == prepared
    assert json.loads(script.read_bytes()) == document
    assert (
        hashlib.sha256(video.read_bytes()).digest()
        == hashlib.sha256((cache / video.name).read_bytes()).digest()
    )

    frozen = prepared / "script.json"
    settings = prepared / "compiler-dependencies.json"
    result = invoke_bridge("compile", frozen, settings).result
    manifest = tmp_path / "manifest.json"
    report = tmp_path / "report.json"
    manifest.write_text(result["manifestJson"])
    report.write_text(result["reportJson"])
    package = tmp_path / "delivery"
    built = build_v2_package(
        manifest,
        report,
        frozen,
        settings,
        package,
        media_paths={
            key: Path(value)
            for key, value in json.loads(
                (prepared / "media-paths.json").read_bytes()
            ).items()
        },
        preparation_paths={
            key: Path(value)
            for key, value in json.loads(
                (prepared / "preparation-paths.json").read_bytes()
            ).items()
        },
    )
    build_root = built.project_root / "Builds" / built.build_id
    timeline = otio.adapters.read_from_file(str(build_root / "timeline.otio"))
    clips = [clip for clip in timeline.find_clips()]
    assert [
        (clip.source_range.start_time.value, clip.source_range.duration.value)
        for clip in clips
    ] == [(2, 3), (5, 2)]
    view = json.loads((build_root / "delivery-view.json").read_bytes())
    assert [
        (event["sourceRange"]["startFrame"], event["sourceRange"]["durationFrames"])
        for event in view["events"]
    ] == [(2, 3), (5, 2)]
    prepared_ranges = [
        (
            item["selectedSourceRange"]["startFrame"],
            item["selectedSourceRange"]["endFrame"],
        )
        for item in json.loads(settings.read_bytes())["occurrenceResolutions"]
    ]
    assert prepared_ranges == [(2, 5), (5, 7)]
    sources = {source["id"]: source["path"] for source in view["sources"]}
    for clip, event, expected in zip(
        clips, view["events"], ([2, 3, 4], [5, 6]), strict=True
    ):
        assert sources[event["sourceId"]] == clip.media_reference.target_url
        path = package / clip.media_reference.target_url
        decoded = subprocess.check_output(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(path),
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ]
        )
        decoded_numbers = [
            round((decoded[offset] - 32) / 24)
            for offset in range(0, len(decoded), 64 * 64 * 3)
        ]
        start = int(clip.source_range.start_time.value)
        duration = int(clip.source_range.duration.value)
        assert decoded_numbers[start : start + duration] == expected
