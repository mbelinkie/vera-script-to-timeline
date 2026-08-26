from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from vera_timeline_agent.narration.cache import CacheError, NarrationCache


def test_cache_publication_is_immutable_reusable_and_strict(tmp_path: Path) -> None:
    cache = NarrationCache(tmp_path)
    disposition = cache.publish(
        "synthesis",
        "a" * 64,
        {"provider-input.ssml": b"<speak>x</speak>", "provider-audio.pcm": b"pcm"},
        "synthesis.json",
        {"provider": "fake"},
    )
    entry = cache.read("synthesis", "a" * 64, "synthesis.json")

    assert disposition == "generated"
    assert entry is not None
    assert entry.files["provider-audio.pcm"] == b"pcm"
    assert (
        cache.publish(
            "synthesis",
            "a" * 64,
            {"provider-input.ssml": b"<speak>x</speak>", "provider-audio.pcm": b"pcm"},
            "synthesis.json",
            {"provider": "fake"},
        )
        == "reused"
    )

    (entry.path / "unexpected").write_bytes(b"bad")
    with pytest.raises(CacheError, match="inventory"):
        cache.read("synthesis", "a" * 64, "synthesis.json")


def test_cache_rejects_tampering_symlinks_and_hard_links(tmp_path: Path) -> None:
    cache = NarrationCache(tmp_path)
    key = "b" * 64
    cache.publish(
        "normalization",
        key,
        {"narration.wav": b"wav"},
        "normalization.json",
        {"profile": "v1"},
    )
    entry = cache.read("normalization", key, "normalization.json")
    assert entry is not None
    (entry.path / "narration.wav").write_bytes(b"changed")
    with pytest.raises(CacheError, match="hash"):
        cache.read("normalization", key, "normalization.json")

    other_key = "c" * 64
    cache.publish(
        "normalization",
        other_key,
        {"narration.wav": b"wav"},
        "normalization.json",
        {"profile": "v1"},
    )
    other = cache.read("normalization", other_key, "normalization.json")
    assert other is not None
    audio = other.path / "narration.wav"
    linked = tmp_path / "linked.wav"
    os.link(audio, linked)
    with pytest.raises(CacheError, match="hard link"):
        cache.read("normalization", other_key, "normalization.json")

    symlink_key = "e" * 64
    symlink_target = cache.root / "normalization" / symlink_key
    symlink_target.symlink_to(other.path, target_is_directory=True)
    with pytest.raises(CacheError, match="symbolic link"):
        cache.read("normalization", symlink_key, "normalization.json")

    external = tmp_path / "external-assets"
    external.mkdir()
    block_parent = cache.root / "assets" / "block-symlink"
    block_parent.symlink_to(external, target_is_directory=True)
    with pytest.raises(CacheError, match="symbolic link"):
        cache.read("assets", f"block-symlink/{'a' * 64}", "asset.json")


def test_injected_write_failure_never_publishes_partial_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = NarrationCache(tmp_path)
    key = "f" * 64
    original = Path.write_bytes

    def fail_second(path: Path, data: bytes) -> int:
        if path.name == "second.bin":
            raise OSError("injected write failure")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_second)
    with pytest.raises(OSError, match="injected"):
        cache.publish(
            "synthesis",
            key,
            {"first.bin": b"one", "second.bin": b"two"},
            "synthesis.json",
            {},
        )
    assert not (cache.root / "synthesis" / key).exists()


def test_same_key_concurrent_publish_has_one_winner(tmp_path: Path) -> None:
    cache = NarrationCache(tmp_path)
    key = "d" * 64

    def publish() -> str:
        with cache.lock(key):
            return cache.publish(
                "synthesis",
                key,
                {"provider-audio.pcm": b"same"},
                "synthesis.json",
                {"provider": "fake"},
            )

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: publish(), range(4)))

    assert results.count("generated") == 1
    assert results.count("reused") == 3
