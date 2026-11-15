from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from vera_timeline_agent.prep_media import failed_fetch_slate
from vera_timeline_agent.research_cut_binding import (
    Json,
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
    dest = root / "timeline"
    copied = copy_cut(cut, SNAPSHOT, dest)
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
