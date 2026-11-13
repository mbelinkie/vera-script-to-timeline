"""#100 optional, hash-pinned local music resolution without provider or Resolve."""

from __future__ import annotations

import copy
import hashlib
import wave
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.build_jobs import BuildJobError
from vera_timeline_agent.music_input import (
    music_event_id,
    resolve_music_bindings,
    verify_music_pins,
)


def _wav(
    path: Path, *, rate: int = 48000, channels: int = 1, samples: int = 48000
) -> str:
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\0\0" * samples * channels)
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str], Path]:
    song = path / "verified.wav"
    digest = _wav(song)
    source = {
        "mediaReferenceId": "00000000-0000-4000-8000-000000000011",
        "artifactId": "00000000-0000-4000-8000-000000000012",
        "artifactVersion": 1,
        "contentHash": digest,
    }
    span = {
        "id": "00000000-0000-4000-8000-000000000013",
        "startRowId": "A",
        "endRowId": "C",
        "source": source,
        "settings": {},
    }
    document = {"id": "00000000-0000-4000-8000-000000000014", "rowAudioSpans": [span]}
    deps = {
        "musicBindings": [],
        "roles": {"narrationTrackId": "narration", "sourceAudioTrackIds": []},
        "tracks": [
            {"id": "narration", "kind": "audio", "index": 1, "name": "Narration"}
        ],
    }
    key = "event:" + music_event_id(
        str(document["id"]), str(span["id"]), str(source["artifactId"])
    )
    return document, deps, {key: str(song)}, song


def test_ready_is_hash_bound_and_does_not_mutate_prepared_inputs(
    tmp_path: Path,
) -> None:
    document, dependencies, paths, wav = _fixture(tmp_path)
    before = copy.deepcopy((document, dependencies, paths))
    result = resolve_music_bindings(document, dependencies, paths)
    assert result.dependencies["musicBindings"] == [
        {
            "spanId": document["rowAudioSpans"][0]["id"],
            "source": document["rowAudioSpans"][0]["source"],
            "displayFilename": "verified.wav",
            "status": "ready",
            "sampleRate": 48000,
            "channels": 1,
            "durationSamples": 48000,
        }
    ]
    assert result.dependencies["roles"]["musicTrackId"] == "music-a5"
    assert result.dependencies["tracks"][-1] == {
        "id": "music-a5",
        "kind": "audio",
        "index": 5,
        "name": "A5 Music",
    }
    assert result.pins == (
        (wav, document["rowAudioSpans"][0]["source"]["contentHash"], 48000),
    )
    assert (document, dependencies, paths) == before
    verify_music_pins(result)


def test_missing_file_or_mapping_is_named_and_nonblocking(tmp_path: Path) -> None:
    document, dependencies, paths, wav = _fixture(tmp_path)
    wav.unlink()
    missing = resolve_music_bindings(document, dependencies, paths)
    assert missing.dependencies["musicBindings"][0]["displayFilename"] == "verified.wav"
    assert missing.dependencies["musicBindings"][0]["status"] == "missing"
    assert not missing.pins
    assert missing.media_paths == {}
    assert "musicTrackId" not in missing.dependencies["roles"]
    assert paths  # original mapping remains intact
    verify_music_pins(missing)
    wav.write_bytes(b"an unexpected late file")
    with pytest.raises(BuildJobError, match="changed after freeze"):
        verify_music_pins(missing)
    without_mapping = resolve_music_bindings(document, dependencies, {})
    assert (
        without_mapping.dependencies["musicBindings"][0]["displayFilename"]
        == document["rowAudioSpans"][0]["source"]["artifactId"]
    )


def test_real_file_wrong_hash_or_truncated_wav_is_not_downgraded_to_missing(
    tmp_path: Path,
) -> None:
    document, dependencies, paths, wav = _fixture(tmp_path)
    document["rowAudioSpans"][0]["source"]["contentHash"] = "sha256:" + "e" * 64
    with pytest.raises(BuildJobError, match="hash mismatch"):
        resolve_music_bindings(document, dependencies, paths)
    digest = _wav(wav)
    document["rowAudioSpans"][0]["source"]["contentHash"] = digest
    wav.write_bytes(wav.read_bytes()[:-5])
    with pytest.raises(BuildJobError, match=r"truncated|hash mismatch"):
        resolve_music_bindings(document, dependencies, paths)


@pytest.mark.parametrize("rate,channels", [(44100, 1), (48000, 2)])
def test_unsupported_music_profile_refuses(
    tmp_path: Path, rate: int, channels: int
) -> None:
    document, dependencies, paths, wav = _fixture(tmp_path)
    document["rowAudioSpans"][0]["source"]["contentHash"] = _wav(
        wav, rate=rate, channels=channels
    )
    with pytest.raises(BuildJobError, match="48kHz mono PCM"):
        resolve_music_bindings(document, dependencies, paths)


def test_symlink_ancestor_and_nonfile_refuse(tmp_path: Path) -> None:
    document, dependencies, paths, wav = _fixture(tmp_path)
    key = next(iter(paths))
    link = tmp_path / "link.wav"
    link.symlink_to(wav)
    paths[key] = str(link)
    with pytest.raises(BuildJobError, match="symbolic link"):
        resolve_music_bindings(document, dependencies, paths)
    paths[key] = str(tmp_path)
    with pytest.raises(BuildJobError, match="regular"):
        resolve_music_bindings(document, dependencies, paths)


def test_bindings_cannot_be_duplicated_or_replaced_or_stale(tmp_path: Path) -> None:
    document, dependencies, paths, wav = _fixture(tmp_path)
    result = resolve_music_bindings(document, dependencies, paths)
    dependencies["musicBindings"] = [result.dependencies["musicBindings"][0]] * 2
    with pytest.raises(BuildJobError, match="duplicate"):
        resolve_music_bindings(document, dependencies, paths)
    dependencies["musicBindings"] = [
        copy.deepcopy(result.dependencies["musicBindings"][0])
    ]
    dependencies["musicBindings"][0]["durationSamples"] += 1
    with pytest.raises(BuildJobError, match="prepared music binding changed"):
        resolve_music_bindings(document, dependencies, paths)
    dependencies["musicBindings"] = [result.dependencies["musicBindings"][0]]
    wav.unlink()
    with pytest.raises(BuildJobError, match="previously ready music disappeared"):
        resolve_music_bindings(document, dependencies, paths)


def test_ready_pin_detects_in_place_tamper_and_replacement(tmp_path: Path) -> None:
    document, dependencies, paths, wav = _fixture(tmp_path)
    result = resolve_music_bindings(document, dependencies, paths)
    original = wav.read_bytes()
    wav.write_bytes(original[:55] + b"X" + original[56:])
    with pytest.raises(BuildJobError, match="hash mismatch"):
        verify_music_pins(result)


def test_a5_is_never_silently_reassigned(tmp_path: Path) -> None:
    document, dependencies, paths, _ = _fixture(tmp_path)
    dependencies["tracks"].append(
        {"id": "other", "kind": "audio", "index": 5, "name": "Other"}
    )
    with pytest.raises(BuildJobError, match="A5 is already occupied"):
        resolve_music_bindings(document, dependencies, paths)
