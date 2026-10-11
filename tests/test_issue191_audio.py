"""Issue-owned synthetic PCM and receipts: no acoustic/native qualification."""

from __future__ import annotations

import copy
import io
import json
import math
import struct
import wave
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.narration.models import canonical_json_bytes, sha256_bytes
from vera_timeline_agent.roundtrip_build import ProofBuildError
from vera_timeline_agent.roundtrip_v2_audio import (
    FRAME,
    RATE,
    verify_selected_omission_v2,
)


def wav(channels: list[list[int]]) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setparams(
            (len(channels), 2, 48000, len(channels[0]), "NONE", "not compressed")
        )
        stream.writeframes(
            b"".join(
                struct.pack("<h", value)
                for frame in zip(*channels, strict=True)
                for value in frame
            )
        )
    return output.getvalue()


def write(root: Path, name: str, value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_json_bytes(value)
    (root / name).write_bytes(raw)
    return sha256_bytes(raw)


def segment(uid: str, start: int, end: int, sin: int, sout: int) -> dict[str, Any]:
    return {
        "uid": uid,
        "recordStart": start,
        "recordEnd": end,
        "sourceStart": sin,
        "sourceEnd": sout,
        "speed": {"numerator": 1, "denominator": 1},
        "enabled": True,
        "online": True,
    }


def case(root: Path, *, extent: int = 12) -> dict[str, Any]:
    words = ["steady", "left", "remove", "these", "right", "tail"]
    tokens = []
    offset = 0
    for index, word in enumerate(words):
        tokens.append(
            {
                "id": f"00000000-0000-4000-8000-{index:012d}",
                "value": word,
                "startOffset": offset,
                "endOffset": offset + len(word),
            }
        )
        offset += len(word) + 1
    row: dict[str, Any] = {
        "id": "row-1",
        "version": 3,
        "type": "narration",
        "state": "active",
        "text": " ".join(words),
        "tokens": tokens,
    }
    document: dict[str, Any] = {
        "activeDraft": {
            "blocks": [row, {"id": "row-2", "text": " ".join(["unchanged"] * 81)}]
        }
    }
    document_json = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode()
    dhash = sha256_bytes(document_json)
    size = extent * FRAME
    primary = [0] * (8 * FRAME)
    for frame in range(6):
        for sample in range(frame * FRAME + 300, (frame + 1) * FRAME - 300):
            primary[sample] = round(2200 * math.sin(sample * (0.04 + frame / 100)))
    other = [
        0 if i < 8 * FRAME else round(1800 * math.sin(i * 0.037)) for i in range(size)
    ]
    quiet = [
        [round(100 * math.sin(i * frequency)) for i in range(size)]
        for frequency in (0.13, 0.17)
    ]
    source_entries = []
    for sid, samples in (("speech", [primary]), ("other", [other]), ("quiet", quiet)):
        pin = write(root, f"{sid}.wav", wav(samples))
        source_entries.append(
            {
                "id": sid,
                "path": f"{sid}.wav",
                "sha256": pin,
                "channels": len(samples),
                "durationSamples": len(samples[0]),
            }
        )
    profile: dict[str, Any] = {
        "schemaVersion": "issue-189-v2-selected-audio-profile/v1",
        "documentHash": dhash,
        "blockId": "row-1",
        "blockRevision": 3,
        "primarySourceId": "speech",
        "extentFrames": extent,
        "frameRate": RATE,
        "sources": source_entries,
        "selectedTokenIds": [
            "00000000-0000-4000-8000-000000000002",
            "00000000-0000-4000-8000-000000000003",
        ],
    }
    phash = write(root, "profile.json", profile)
    review: dict[str, Any] = {
        "schemaVersion": "issue-189-v2-selected-review/v1",
        "method": "independent_source_listening_waveform/v1",
        "reviewerReference": "fake-reviewer",
        "reviewId": "fake-review",
        "reviewRevision": 1,
        "documentHash": dhash,
        "blockId": "row-1",
        "blockRevision": 3,
        "textHash": sha256_bytes(row["text"].encode()),
        "sourceHash": source_entries[0]["sha256"],
        "supports": [],
    }
    for index in range(1, 5):
        token = tokens[index]
        review["supports"].append(
            {
                "tokenId": token["id"],
                "quotedText": token["value"],
                "startOffset": token["startOffset"],
                "endOffset": token["endOffset"],
                "onsetSample": index * FRAME + 300,
                "endSample": (index + 1) * FRAME - 300,
            }
        )
    write(root, "review.json", review)
    controls = {
        "enabled": True,
        "mute": False,
        "solo": False,
        "gainDb": 0,
        "pan": 0,
        "effects": [],
        "sends": [],
        "automation": [],
        "destination": "stereo-program",
        "channelMap": "mono-dual",
    }
    target = {"projectUid": "fake-project", "timelineUid": "fake-timeline"}
    baseline: dict[str, Any] = {
        "schemaVersion": "issue-189-v2-audio-observation/v1",
        "target": target,
        "extentFrames": extent,
        "frameRate": RATE,
        "programControls": {
            "gainDb": 0,
            "effects": [],
            "limiter": False,
            "automation": [],
            "destination": "stereo-program",
        },
        "routes": [
            {
                "id": "route-1",
                "sourceId": "speech",
                "controls": controls,
                "segments": [segment("whole", 0, 8, 0, 8)],
            },
            {
                "id": "route-2",
                "sourceId": "other",
                "controls": copy.deepcopy(controls),
                "segments": [segment("other", 0, extent, 0, extent)],
            },
            {
                "id": "route-3",
                "sourceId": "quiet",
                "controls": {**controls, "channelMap": "stereo-direct"},
                "segments": [segment("quiet", 0, extent, 0, extent)],
            },
        ],
    }
    current = copy.deepcopy(baseline)
    current["routes"][0]["segments"] = [
        segment("left", 0, 2, 0, 2),
        segment("right", 4, 8, 4, 8),
    ]
    bhash = write(root, "baseline.json", baseline)
    chash = write(root, "current-a.json", current)
    write(root, "current-b.json", current)
    for name, edited in (("pristine", False), ("edited", True)):
        output = [
            [
                (
                    primary[i]
                    if i < len(primary) and not (edited and 2 * FRAME <= i < 4 * FRAME)
                    else 0
                )
                + other[i]
                + quiet[ch][i]
                for i in range(size)
            ]
            for ch in range(2)
        ]
        write(root, f"{name}.wav", wav(output))
    pins: set[str] = set()

    def receipt(name: str, kind: str, bindings: dict[str, Any]) -> None:
        pin = write(
            root,
            name,
            {
                "schemaVersion": "issue-191-fake-receipt/v1",
                "kind": kind,
                "bindings": bindings,
            },
        )
        pins.add(pin)

    for name, pin in (("baseline", bhash), ("current-a", chash), ("current-b", chash)):
        receipt(
            f"{name}-receipt.json",
            "native_observation",
            {"target": target, "observationHash": pin, "profileHash": phash},
        )
    for name, pin in (("pristine", bhash), ("edited", chash)):
        receipt(
            f"{name}-receipt.json",
            "native_render",
            {
                "target": target,
                "observationHash": pin,
                "profileHash": phash,
                "outputHash": sha256_bytes((root / f"{name}.wav").read_bytes()),
                "settings": {
                    "startFrame": 0,
                    "endFrame": extent,
                    "frameRate": RATE,
                    "sampleRate": 48000,
                    "channels": 2,
                    "codec": "pcm",
                },
            },
        )
    pins.add(sha256_bytes((root / "review.json").read_bytes()))
    receipt(
        "lift-receipt.json",
        "native_audio_lift",
        {
            "target": target,
            "baselineHash": bhash,
            "currentHash": chash,
            "primarySourceId": "speech",
            "sourceHash": source_entries[0]["sha256"],
            "originalSegment": baseline["routes"][0]["segments"][0],
            "retainedSegments": current["routes"][0]["segments"],
            "sourceIntervalSamples": {"start": 2 * FRAME, "end": 4 * FRAME},
            "recordIntervalFrames": {"start": 2, "end": 4},
            "operation": "lift_audio_without_ripple",
        },
    )
    receipt(
        "listening-receipt.json",
        "edited_mix_listening",
        {
            "documentHash": dhash,
            "reviewHash": sha256_bytes((root / "review.json").read_bytes()),
            "editedRenderHash": sha256_bytes((root / "edited.wav").read_bytes()),
            "selectedTokenIds": [
                "00000000-0000-4000-8000-000000000002",
                "00000000-0000-4000-8000-000000000003",
            ],
            "neighborTokenIds": [
                "00000000-0000-4000-8000-000000000001",
                "00000000-0000-4000-8000-000000000004",
            ],
        },
    )

    def authenticate(kind: str, raw: bytes, bindings: dict[str, Any]) -> None:
        # Independent fake authority pins receipts, never operator flags/job IDs.
        if sha256_bytes(raw) not in pins:
            raise ProofBuildError("unauthenticated receipt")
        value = json.loads(raw)
        if kind == "selected_review":
            assert value == bindings
        elif value != {
            "schemaVersion": "issue-191-fake-receipt/v1",
            "kind": kind,
            "bindings": bindings,
        }:
            raise ProofBuildError("receipt binding mismatch")

    return {
        "canonical_document_json": document_json,
        "expected_document_hash": dhash,
        "baseline_hash": bhash,
        "current_hash": chash,
        "profile_hash": phash,
        "row_id": "row-1",
        "primary_source_id": "speech",
        "target": target,
        "authenticate": authenticate,
    }


def test_selected_only_complete_stereo_and_repeat(tmp_path: Path) -> None:
    args = case(tmp_path)
    first = verify_selected_omission_v2(tmp_path, **args)
    assert first["status"] == "verified", first.get("reason", first)
    assert first["tokenIds"] == [
        "00000000-0000-4000-8000-000000000002",
        "00000000-0000-4000-8000-000000000003",
    ]
    assert first["sourceIntervalSamples"] == {"start": 4004, "end": 8008}
    assert all(
        ch["residualRms"] < 1e-12
        for entry in first["channels"]
        for ch in entry["channels"]
    )
    assert canonical_json_bytes(first) == canonical_json_bytes(
        verify_selected_omission_v2(tmp_path, **args)
    )
    assert first["evidenceLevel"] == "local_consistency_only"


@pytest.mark.parametrize("raw", [b"not a wave file", b"RIFF"])
def test_malformed_render_returns_refusal(tmp_path: Path, raw: bytes) -> None:
    args = case(tmp_path)
    (tmp_path / "edited.wav").write_bytes(raw)
    original = args["authenticate"]

    def auth(kind: str, receipt: bytes, binding: dict[str, Any]) -> None:
        if kind != "native_render":
            original(kind, receipt, binding)

    args["authenticate"] = auth
    result = verify_selected_omission_v2(tmp_path, **args)
    assert result["status"] == "refused"
    assert result["reason"] == (
        "file does not start with RIFF id" if len(raw) > 4 else ""
    )


@pytest.mark.parametrize(
    "fault",
    [
        "picture-only",
        "clipped-neighbor",
        "extra-cut",
        "unknown-control",
        "unknown-route",
        "partial-source",
        "alias",
        "stale-source",
        "wrong-receipt",
        "stale-review",
        "review-method",
        "quote",
        "end",
        "adjacent",
        "unrelated",
        "ripple",
        "partial-render",
        "stale-document",
    ],
)
def test_refusals(tmp_path: Path, fault: str) -> None:
    args = case(tmp_path)
    current = json.loads((tmp_path / "current-a.json").read_bytes())
    profile = json.loads((tmp_path / "profile.json").read_bytes())
    review = json.loads((tmp_path / "review.json").read_bytes())
    if fault == "picture-only":
        current = json.loads((tmp_path / "baseline.json").read_bytes())
    elif fault == "clipped-neighbor":
        current["routes"][0]["segments"][0] = segment("left", 0, 1, 0, 1)
    elif fault == "extra-cut":
        current["routes"][0]["segments"].append(segment("extra", 8, 9, 7, 8))
    elif fault == "unknown-control":
        current["routes"][2]["controls"]["automation"] = [{"at": 0, "gain": -4}]
    elif fault == "unknown-route":
        current["routes"][2]["sourceId"] = "unknown"
    elif fault == "partial-source":
        profile["sources"].pop()
    elif fault == "alias":
        profile["sources"][1] = {**profile["sources"][0], "id": "other"}
    elif fault == "stale-source":
        (tmp_path / "speech.wav").write_bytes(wav([[0] * (8 * FRAME)]))
    elif fault == "wrong-receipt":
        write(
            tmp_path,
            "edited-receipt.json",
            {"jobId": "invented-job", "status": "complete"},
        )
    elif fault == "stale-review":
        review["blockRevision"] = 2
    elif fault == "review-method":
        review["method"] = "provider-derived-end"
    elif fault == "quote":
        review["supports"][1]["quotedText"] = "wrong"
    elif fault == "end":
        review["supports"][1]["endSample"] = 11 * FRAME
    elif fault == "adjacent":
        write(tmp_path, "current-b.json", {**current, "extentFrames": 11})
    elif fault == "unrelated":
        current["routes"][2]["segments"][0] = segment("quiet", 1, 12, 1, 12)
    elif fault == "ripple":
        current["routes"][0]["segments"][1] = segment("right", 2, 6, 4, 8)
    elif fault == "partial-render":
        write(tmp_path, "edited.wav", wav([[0] * (11 * FRAME)] * 2))
    elif fault == "stale-document":
        args["canonical_document_json"] += b" "
    # Keep file pins current so shape/geometry tests cannot pass by a stale hash alone.
    if fault in {
        "picture-only",
        "clipped-neighbor",
        "extra-cut",
        "unknown-control",
        "unknown-route",
        "unrelated",
        "ripple",
    }:
        args["current_hash"] = write(tmp_path, "current-a.json", current)
        write(tmp_path, "current-b.json", current)
        # A separate fake authority supplies these malformed native captures.
        original = args["authenticate"]

        def malformed_capture_auth(
            kind: str, raw: bytes, bindings: dict[str, Any]
        ) -> None:
            if kind != "native_observation":
                original(kind, raw, bindings)

        args["authenticate"] = malformed_capture_auth
    if fault in {"partial-source", "alias"}:
        args["profile_hash"] = write(tmp_path, "profile.json", profile)
    if fault in {"stale-review", "review-method", "quote", "end"}:
        write(tmp_path, "review.json", review)
    result = verify_selected_omission_v2(tmp_path, **args)
    assert result["status"] == "refused", result


def test_residual_gates_cover_later_right_channel_and_sliding_window(
    tmp_path: Path,
) -> None:
    args = case(tmp_path, extent=308)
    path = tmp_path / "edited.wav"
    raw = bytearray(path.read_bytes())
    # 20ms burst far outside the selected phrase; overall RMS stays below its gate.
    for index in range(200 * FRAME, 200 * FRAME + 960):
        pos = 44 + index * 4 + 2
        value = struct.unpack_from("<h", raw, pos)[0]
        struct.pack_into("<h", raw, pos, value + 295)
    write(tmp_path, "edited.wav", bytes(raw))
    original = args["authenticate"]

    def authenticated_changed_render(
        kind: str, receipt: bytes, bindings: dict[str, Any]
    ) -> None:
        if kind != "native_render":
            original(kind, receipt, bindings)

    args["authenticate"] = authenticated_changed_render
    result = verify_selected_omission_v2(tmp_path, **args)
    assert result["status"] == "refused", result
    right = result["channels"][1]["channels"][1]
    assert right["residualRms"] <= 0.0004
    assert right["maximumSliding20msResidualRms"] > 0.006
