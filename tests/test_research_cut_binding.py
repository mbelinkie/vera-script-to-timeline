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
