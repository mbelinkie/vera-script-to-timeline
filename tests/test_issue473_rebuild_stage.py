"""Guard source-media selection before any native #473 rebuild effect."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _stage() -> ModuleType:
    source = Path(__file__).resolve().parents[1] / "scripts/issue-473-rebuild-stage.py"
    spec = importlib.util.spec_from_file_location("issue473_stage_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ID = "19c894ef-03cc-5b4d-8c89-6a24448a15ba"
NARR = "36300212-5430-5012-9a93-c0dd67498537"
PLACE = "df1127c7-f35b-543a-88d7-04d3d65b7489"


def test_original_media_is_exact_source_pinned_and_distinguishes_null_narration(
    tmp_path: Path,
) -> None:
    stage = _stage()
    root = tmp_path / "package"
    for relative in (
        f"Media/Resolved/{ID}.mp4",
        f"Media/Narration/{NARR}.wav",
        f"Builds/old/Preparation/original/{ID}.mp4",
        f"Media/Resolved/{PLACE}.png",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())
    revised = {
        "sources": [
            {"id": ID, "narrationAudio": None},
            {"id": NARR, "narrationAudio": {"audioHash": "sha256:proof"}},
        ],
        "events": [{"eventId": PLACE, "kind": "placeholder"}],
    }
    paths = stage._original_media_paths(root, "old", revised)
    assert set(paths) == {
        f"source:{ID}",
        f"original:{ID}",
        f"source:{NARR}",
        f"event:{PLACE}",
    }
    assert paths[f"source:{ID}"].suffix == ".mp4"
    assert paths[f"source:{NARR}"].suffix == ".wav"

    # A second lookalike must never be silently chosen by a glob.
    (root / "Media/Resolved" / f"{ID}.mov").write_bytes(b"ambiguous")
    with pytest.raises(RuntimeError, match="ambiguous"):
        stage._original_media_paths(root, "old", revised)


def test_original_media_refuses_symlinks_and_source_audio(tmp_path: Path) -> None:
    stage = _stage()
    source = tmp_path / "media"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    (source / f"{ID}.mp4").symlink_to(outside)
    with pytest.raises(RuntimeError, match="ambiguous"):
        stage._exact_media_file(source, ID)
    with pytest.raises(RuntimeError, match="non-UUID"):
        stage._exact_media_file(source, "../source")
