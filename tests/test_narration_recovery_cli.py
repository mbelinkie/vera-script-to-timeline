from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.models import sha256_bytes
from vera_timeline_agent.narration.recovery import RecoveryError
from vera_timeline_agent.narration.recovery_cli import retained_source


def test_retained_tie_verifies_inventory_request_and_frozen_source(
    tmp_path: Path,
) -> None:
    cache = NarrationCache(tmp_path)
    key, quarantine = "a" * 64, "b" * 64
    block = dict(
        id="row",
        version=1,
        type="narration",
        text="one two",
        tokens=[dict(startOffset=0, endOffset=3), dict(startOffset=4, endOffset=7)],
    )
    asset = dict(
        asset_id=key,
        status="failed",
        provider="fish_audio",
        block_id="row",
        block_revision=1,
        request_hash=f"sha256:{key}",
        text_hash=sha256_bytes(b"one two"),
    )
    pcm = b"\x01\x00" * 4410
    event = dict(
        content="one two",
        chunk_seq=0,
        chunk_audio_offset_sec=0,
        audio_base64=base64.b64encode(pcm).decode(),
        alignment=dict(
            audio_duration=0.1,
            segments=[
                dict(text="one", start=0, end=0),
                dict(text="two", start=0, end=0.1),
            ],
        ),
    )
    response = b"data: " + json.dumps(event).encode() + b"\n\n"
    cache.publish("assets", f"row/{key}", {}, "asset.json", dict(asset=asset))
    cache.publish(
        "quarantine",
        quarantine,
        {"provider-response.sse": response},
        "response.json",
        dict(synthesisKey=key),
    )
    document = dict(activeDraft=dict(blocks=[block]))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert retained_source(cache, f"row/{key}", quarantine, document)[-1] == pcm
    assert all(p.read_bytes() == data for p, data in before.items())
    block["text"] = "two one"
    with pytest.raises(RecoveryError, match="differs"):
        retained_source(cache, f"row/{key}", quarantine, document)
