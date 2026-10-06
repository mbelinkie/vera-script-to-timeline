"""Hash-verified W1 replay, with synthetic envelopes; no native qualification."""

from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import subprocess
import wave
from pathlib import Path
from typing import Any

from vera_timeline_agent.roundtrip_audio import verify_omission_evidence
from vera_timeline_agent.roundtrip_build import ROOT, _digest, _receipt_bytes

KIT = "out/issue149-workflow-reruns-20261002-kit-01"


def _load(name: str, records: dict[str, Any]) -> bytes:
    record = records[f"{KIT}/{name}"]
    payload = (ROOT / record["published"]).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == record["publishedSha256"]
    decoded = gzip.decompress(payload) if record["compressed"] else payload
    assert hashlib.sha256(decoded).hexdigest() == record["decodedPublishedSha256"]
    return decoded


def _value(wrapped: dict[str, Any]) -> Any:
    assert set(wrapped) == {"status", "value"} and wrapped["status"] == "ok"
    return wrapped["value"]


def _decode(root: Path, name: str, payload: bytes, channels: int, frames: int) -> bytes:
    path = root / name
    path.write_bytes(payload)
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    streams = json.loads(completed.stdout)["streams"]
    audio = [s for s in streams if s["codec_type"] == "audio"]
    video = [s for s in streams if s["codec_type"] == "video"]
    assert len(audio) == len(video) == 1
    assert (
        audio[0]["codec_name"],
        audio[0]["sample_rate"],
        audio[0]["channels"],
        video[0]["avg_frame_rate"],
        int(video[0]["nb_frames"]),
    ) == ("pcm_s16le", "48000", channels, "25/1", frames)
    decoded = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    ).stdout
    # ffmpeg's streamed WAV uses an unknown data extent; canonicalize only the
    # container header after verifying all expected decoded samples exactly.
    with wave.open(io.BytesIO(decoded), "rb") as stream:
        pcm = stream.readframes(frames * 1920 + 1)
        assert len(pcm) == frames * 1920 * channels * 2
    out = io.BytesIO()
    with wave.open(out, "wb") as stream:
        stream.setparams((channels, 2, 48000, 0, "NONE", "not compressed"))
        stream.writeframes(pcm)
    return out.getvalue()


def test_retained_w1_support_and_render_consistency_remain_unqualified(
    tmp_path: Path,
) -> None:
    publication = json.loads(
        (ROOT / "docs/investigations/issue-141/publication-manifest.json").read_bytes()
    )
    records = {r["source"]: r for r in publication["records"]}
    manifest = json.loads(_load("media/manifest.json", records))
    sources = []
    for i, name in enumerate(("a1_alpha.wav", "a2_numbers.wav", "a3_bed.wav")):
        raw = _load(f"media/{name}", records)
        (tmp_path / name).write_bytes(raw)
        assert hashlib.sha256(raw).hexdigest() == manifest["files"][name]["sha256"]
        sources.append(
            {
                "id": f"source-{i}",
                "rowId": f"row-{i}",
                "path": name,
                "sha256": _digest(raw),
                "supports": [
                    {
                        "tokenId": w["word"],
                        "startSample": w["start_sample"],
                        "endSample": w["end_sample"],
                    }
                    for w in manifest["files"][name].get("words", [])
                ],
            }
        )
    embedded = _decode(tmp_path, "base.mov", _load("media/base.mov", records), 1, 400)
    with wave.open(io.BytesIO(embedded), "rb") as stream:
        embedded_pcm = stream.readframes(400 * 1920)
    with wave.open(str(tmp_path / "a1_alpha.wav"), "rb") as stream:
        assert stream.readframes(400 * 1920) == embedded_pcm
    prefix = "evidence/w1-subtitle-poll-linked-cut-01-20261002-kit-01"
    pre_raw, post_raw = [
        _load(f"{prefix}/{name}.json", records) for name in ("pre", "post")
    ]
    assert pre_raw == post_raw
    native = json.loads(pre_raw)
    timeline = next(t for t in native["project"]["timelines"] if t["isCurrent"])
    assert _value(timeline["getters"]["GetStartFrame"]) == 0
    assert _value(timeline["getters"]["GetEndFrame"]) == 399
    # Explicit synthetic replay identities/row map/receipts. This is a numerical
    # replay of retained native geometry and complete program/source bytes, not
    # a live baseline, clip ancestry, source alignment or native receipt claim.
    target = {
        "projectUid": "retained-replay-project",
        "timelineUid": "retained-replay-timeline",
    }
    routes: list[dict[str, Any]] = []
    for i, track in enumerate(timeline["tracks"]["audio"]):
        assert _value(track["GetIsTrackEnabled"]) is True
        segments = []
        for item in _value(track["GetItemListInTrack"]):
            assert _value(item["GetClipEnabled"]) is True
            assert _value(item["GetSpeed"])["Percentage"] == 100
            segments.append(
                {
                    "uid": _value(item["GetUniqueId"]),
                    "recordStart": _value(item["GetStart"]),
                    "recordEnd": _value(item["GetEnd"]),
                    "sourceStart": _value(item["GetSourceStartFrame"]),
                    "sourceEnd": _value(item["GetSourceEndFrame"]),
                    "enabled": True,
                    "online": True,
                    "speed": 100,
                }
            )
        routes.append(
            {
                "id": f"audio:{i + 1}",
                "sourceId": f"source-{i}",
                "controls": {"qualification": "unobserved"},
                "segments": segments,
            }
        )
    assert [
        (s["recordStart"], s["recordEnd"], s["sourceStart"], s["sourceEnd"])
        for s in routes[0]["segments"]
    ] == [(0, 99, 0, 99), (100, 349, 150, 399)]
    edited: dict[str, Any] = {
        "schemaVersion": "issue-144-audio-observation/v1",
        "target": target,
        "extentFrames": 399,
        "programControls": {"qualification": "unobserved"},
        "routes": routes,
    }
    baseline = copy.deepcopy(edited)
    baseline["routes"][0]["segments"] = [
        {**routes[0]["segments"][0], "recordEnd": 399, "sourceEnd": 399}
    ]

    def write(name: str, value: object) -> str:
        raw = _receipt_bytes(value)
        (tmp_path / name).write_bytes(raw)
        return _digest(raw)

    baseline_hash = write("baseline.json", baseline)
    profile_hash = write(
        "profile.json",
        {
            "schemaVersion": "issue-144-audio-profile/v1",
            "evidenceLevel": "retained_consistency",
            "supportProvenance": "fixture_generator",
            "baselineHash": baseline_hash,
            "extentFrames": 399,
            "sources": sources,
        },
    )
    edited_hash = write("observation-a.json", edited)
    write("observation-b.json", edited)
    for job, movie, observation_hash in (
        ("calibration", "W1-picture-only-cut-01", baseline_hash),
        ("render", "W1-linked-cut-01", edited_hash),
    ):
        raw = _decode(
            tmp_path, f"{job}.mov", _load(f"renders/{movie}.mov", records), 2, 399
        )
        (tmp_path / f"{job}.wav").write_bytes(raw)
        write(
            f"{job}.json",
            {
                "schemaVersion": "issue-144-audio-render/v1",
                "target": target,
                "baselineHash": baseline_hash,
                "profileHash": profile_hash,
                "observationHash": observation_hash,
                "jobId": job,
                "queuedJobId": job,
                "polledJobId": job,
                "status": "complete",
                "settings": {
                    "startFrame": 0,
                    "endFrame": 399,
                    "frameRate": "25/1",
                    "sampleRate": 48000,
                    "channels": 2,
                    "codec": "pcm",
                    "sampleWidth": 2,
                },
                "output": {"path": f"{job}.wav", "sha256": _digest(raw)},
            },
        )
    result = verify_omission_evidence(
        tmp_path,
        baseline_hash=baseline_hash,
        target=target,
        row_id="row-0",
        primary_source_id="source-0",
        evidence_level="retained_consistency",
    )
    assert result["status"] == "consistent_unqualified", result
    assert result["omittedTokenIds"] == ["charlie"]
    assert result["decomposition"][2]["supportSamples"] == [216000, 234932]
    assert all(c["consistent"] for c in result["channels"])
    assert result["channels"][0]["residualRms"] < 0.0004
    # Same retained file cannot be promoted to a real lane by an operator claim.
    result = verify_omission_evidence(
        tmp_path,
        baseline_hash=baseline_hash,
        target=target,
        row_id="row-0",
        primary_source_id="source-0",
        evidence_level="real_issue145",
    )
    assert result["status"] == "refused" and "#145" in result["reason"]
