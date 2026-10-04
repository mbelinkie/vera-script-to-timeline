from __future__ import annotations

import copy
import io
import math
import wave
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.roundtrip_audio import verify_omission_evidence
from vera_timeline_agent.roundtrip_build import (
    _digest,
    _receipt_bytes,
    load_operator_json,
)

N = 80
FRAME = 1920
TARGET = {"projectUid": "test-project", "timelineUid": "test-timeline"}


def _write(root: Path, name: str, value: object) -> str:
    raw = _receipt_bytes(value)
    (root / name).write_bytes(raw)
    return _digest(raw)


def _wav(channels: list[list[float]], width: int = 3) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setparams((len(channels), width, 48000, 0, "NONE", "not compressed"))
        scale = 2 ** (width * 8 - 1)
        stream.writeframes(
            b"".join(
                max(-scale, min(scale - 1, round(x * scale))).to_bytes(
                    width, "little", signed=True
                )
                for samples in zip(*channels, strict=True)
                for x in samples
            )
        )
    return output.getvalue()


def _controls() -> dict[str, Any]:
    return {
        "enabled": True,
        "mute": False,
        "solo": False,
        "effects": [],
        "sends": [],
        "destination": "stereo-program",
        "gainDb": 0,
        "pan": 0,
    }


def _segment(uid: str, start: int, end: int, source: int) -> dict[str, Any]:
    return {
        "uid": uid,
        "recordStart": start,
        "recordEnd": end,
        "sourceStart": source,
        "sourceEnd": source + end - start,
        "speed": 100,
        "enabled": True,
        "online": True,
    }


def _program(
    samples: list[list[float]], routes: list[dict[str, Any]]
) -> list[list[float]]:
    channels = [[0.0] * (N * FRAME) for _ in range(2)]
    gains = ((0.8, 0.6), (0.7, 0.65), (0.5, 0.55))
    for source, route, gain in zip(samples, routes, gains, strict=True):
        for segment in route["segments"]:
            length = (segment["recordEnd"] - segment["recordStart"]) * FRAME
            record = segment["recordStart"] * FRAME
            start = segment["sourceStart"] * FRAME
            for channel, g in zip(channels, gain, strict=True):
                for index in range(length):
                    channel[record + index] += source[start + index] * g
    return channels


def _receipt(root: Path, name: str, observation: str, output: str) -> None:
    _write(
        root,
        name,
        {
            "schemaVersion": "issue-144-audio-render/v1",
            "target": TARGET,
            "baselineHash": _digest((root / "baseline.json").read_bytes()),
            "observationHash": _digest((root / observation).read_bytes()),
            "profileHash": _digest((root / "profile.json").read_bytes()),
            "jobId": name,
            "queuedJobId": name,
            "polledJobId": name,
            "status": "complete",
            "settings": {
                "startFrame": 0,
                "endFrame": N,
                "frameRate": "25/1",
                "sampleRate": 48000,
                "channels": 2,
                "codec": "pcm",
                "sampleWidth": 3,
            },
            "output": {"path": output, "sha256": _digest((root / output).read_bytes())},
        },
    )


@pytest.fixture
def case(tmp_path: Path) -> tuple[Path, str, list[list[float]]]:
    samples = [
        [
            round(4000 * math.sin(2 * math.pi * frequency * i / 48000)) / 32768
            for i in range(N * FRAME)
        ]
        for frequency in (311, 467, 619)
    ]
    words = [
        {
            "tokenId": word,
            "startSample": start * FRAME + 345,
            "endSample": end * FRAME + 777,
        }
        for word, start, end in (
            ("alpha", 5, 9),
            ("bravo", 18, 22),
            ("charlie", 32, 36),
            ("delta", 48, 52),
            ("echo", 65, 70),
        )
    ]
    sources = []
    baseline_routes = []
    for i, source in enumerate(samples):
        path = f"source-{i}.wav"
        (tmp_path / path).write_bytes(_wav([source], 2))
        sources.append(
            {
                "id": f"source-{i}",
                "rowId": f"row-{i}",
                "path": path,
                "sha256": _digest((tmp_path / path).read_bytes()),
                "supports": words if i == 0 else [],
            }
        )
        baseline_routes.append(
            {
                "id": f"audio:{i + 1}",
                "sourceId": f"source-{i}",
                "controls": _controls(),
                "segments": [_segment(f"clip-{i}", 0, N, 0)],
            }
        )
    baseline: dict[str, Any] = {
        "schemaVersion": "issue-144-audio-observation/v1",
        "target": TARGET,
        "extentFrames": N,
        "programControls": {"gainDb": 0, "effects": [], "limiter": False},
        "routes": baseline_routes,
    }
    baseline_hash = _write(tmp_path, "baseline.json", baseline)
    _write(
        tmp_path,
        "profile.json",
        {
            "schemaVersion": "issue-144-audio-profile/v1",
            "evidenceLevel": "synthetic_injected",
            "supportProvenance": "fixture_generator",
            "baselineHash": baseline_hash,
            "extentFrames": N,
            "sources": sources,
        },
    )
    edited = copy.deepcopy(baseline)
    edited["routes"][0]["segments"] = [
        _segment("first", 0, 30, 0),
        _segment("second", 30, 70, 40),
    ]
    _write(tmp_path, "observation-a.json", edited)
    _write(tmp_path, "observation-b.json", edited)
    (tmp_path / "reference.wav").write_bytes(_wav(_program(samples, baseline_routes)))
    (tmp_path / "edited.wav").write_bytes(_wav(_program(samples, edited["routes"])))
    _receipt(tmp_path, "calibration.json", "baseline.json", "reference.wav")
    _receipt(tmp_path, "render.json", "observation-a.json", "edited.wav")
    return tmp_path, baseline_hash, samples


def _verify(
    case: tuple[Path, str, list[list[float]]], lane: str = "synthetic_injected"
) -> dict[str, Any]:
    root, baseline, _ = case
    return verify_omission_evidence(
        root,
        baseline_hash=baseline,
        target=TARGET,
        row_id="row-0",
        primary_source_id="source-0",
        evidence_level=lane,
    )


def _edit(case: tuple[Path, str, list[list[float]]], change: Any) -> None:
    root = case[0]
    observation = load_operator_json(root / "observation-a.json")
    change(observation)
    for name in ("observation-a.json", "observation-b.json"):
        _write(root, name, observation)
    _receipt(root, "render.json", "observation-a.json", "edited.wav")


def test_complete_closed_routes_positive_and_deterministic(
    case: tuple[Path, str, list[list[float]]],
) -> None:
    report = _verify(case)
    assert report["status"] == "supported"
    assert report["omittedTokenIds"] == ["charlie"]
    assert report["retainedTokenIds"] == ["alpha", "bravo", "delta", "echo"]
    assert len(report["channels"]) == 2
    assert report == _verify(case)
    assert "quiet" in report["limitations"][0]


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (
            lambda o: o["routes"][0].update(segments=[_segment("all", 0, N, 0)]),
            "no interior omission",
        ),
        (lambda o: o["routes"][0].update(segments=[]), "complete route removal"),
        (
            lambda o: (
                o["routes"][0]["segments"][0].update(recordEnd=33, sourceEnd=33),
                o["routes"][0]["segments"][1].update(recordStart=33, recordEnd=73),
            ),
            "partial support",
        ),
        (
            lambda o: o["routes"][0]["segments"][1].update(
                sourceStart=36, sourceEnd=76
            ),
            "partial support",
        ),
        (
            lambda o: o["routes"][0]["segments"][1].update(
                sourceStart=18, sourceEnd=58
            ),
            "source order",
        ),
        (lambda o: o["routes"][0]["segments"][0].update(speed=90), "speed"),
        (lambda o: o["routes"][0]["segments"][0].update(online=False), "offline"),
        (lambda o: o["routes"][0]["controls"].update(mute=True), "controls"),
        (lambda o: o["routes"][0]["controls"].update(solo=True), "controls"),
        (lambda o: o["routes"][0]["controls"].update(effects=["reverb"]), "controls"),
        (lambda o: o["routes"][0]["controls"].update(sends=["bus2"]), "controls"),
        (lambda o: o["routes"][0]["controls"].update(mystery=True), "controls"),
        (lambda o: o["routes"][0]["controls"].pop("solo"), "controls"),
        (lambda o: o["programControls"].update(limiter=True), "program controls"),
        (lambda o: o["programControls"].update(effects=["reverb"]), "program controls"),
        (lambda o: o.pop("programControls"), "observation"),
        (lambda o: o["routes"][0]["segments"][0].update(recordStart=True), "integer"),
        (lambda o: o["routes"][0]["segments"][1].update(uid="first"), "occurrence"),
        (lambda o: o["routes"][1].update(sourceId="source-0"), "source binding"),
        (
            lambda o: o["routes"].append(copy.deepcopy(o["routes"][0])),
            "route inventory",
        ),
        (
            lambda o: o["routes"][1]["segments"][0].update(
                recordEnd=N - 1, sourceEnd=N - 1
            ),
            "untouched route",
        ),
        (lambda o: o.update(extentFrames=N - 1), "extent"),
        (lambda o: o["target"].update(timelineUid="wrong"), "target"),
    ],
)
def test_structural_refusals(
    case: tuple[Path, str, list[list[float]]], mutation: Any, reason: str
) -> None:
    _edit(case, mutation)
    result = _verify(case)
    assert result["status"] == "refused"
    assert reason in result["reason"]


@pytest.mark.parametrize(
    "file,change,reason",
    [
        ("observation-b.json", lambda x: x.update(extentFrames=N - 1), "adjacent"),
        ("render.json", lambda x: x.update(polledJobId="other"), "job"),
        ("render.json", lambda x: x["settings"].update(endFrame=N - 1), "settings"),
        (
            "render.json",
            lambda x: x["output"].update(sha256="sha256:" + "0" * 64),
            "hash",
        ),
        ("render.json", lambda x: x.update(observationHash="stale"), "binding"),
        (
            "profile.json",
            lambda x: x["sources"].append(copy.deepcopy(x["sources"][0])),
            "source inventory",
        ),
        ("profile.json", lambda x: x["sources"][0].update(rowId="row-1"), "row/source"),
        (
            "profile.json",
            lambda x: x.update(supportProvenance="provider_word_ends"),
            "support provenance",
        ),
    ],
)
def test_receipt_and_profile_refusals(
    case: tuple[Path, str, list[list[float]]], file: str, change: Any, reason: str
) -> None:
    root = case[0]
    value = load_operator_json(root / file)
    change(value)
    _write(root, file, value)
    result = _verify(case)
    assert result["status"] == "refused"
    assert reason in result["reason"]


def test_source_and_render_tampering(case: tuple[Path, str, list[list[float]]]) -> None:
    root = case[0]
    for name in ("source-0.wav", "edited.wav"):
        raw = (root / name).read_bytes()
        (root / name).write_bytes(raw + b"tamper")
        assert _verify(case)["status"] == "refused"
        (root / name).write_bytes(raw)


def test_opposite_channel_residue_cannot_cancel(
    case: tuple[Path, str, list[list[float]]],
) -> None:
    root, _, samples = case
    routes = load_operator_json(root / "observation-a.json")["routes"]
    channels = _program(samples, routes)
    for channel, sign in zip(channels, (1, -1), strict=True):
        for i in range(2000):
            channel[30 * FRAME + i] += sign * samples[0][32 * FRAME + 345 + i]
    (root / "edited.wav").write_bytes(_wav(channels))
    _receipt(root, "render.json", "observation-a.json", "edited.wav")
    report = _verify(case)
    assert report["status"] == "refused"
    assert "render consistency" in report["reason"]
    assert all(c["maximumSliding20msResidualRms"] > 0.006 for c in report["channels"])


def test_numeric_tolerance_is_explicitly_not_an_absence_classifier(
    case: tuple[Path, str, list[list[float]]],
) -> None:
    root, _, samples = case
    channels = _program(
        samples, load_operator_json(root / "observation-a.json")["routes"]
    )
    for channel, sign in zip(channels, (1, -1), strict=True):
        for i in range(2000):
            channel[30 * FRAME + i] += sign * 0.015 * samples[0][32 * FRAME + 345 + i]
    (root / "edited.wav").write_bytes(_wav(channels))
    _receipt(root, "render.json", "observation-a.json", "edited.wav")
    # Deliberate out-of-model overlay proves numerical sensitivity limitation.
    # Synthetic closed-route qualification is invalid for this adulterated program.
    profile = load_operator_json(root / "profile.json")
    profile["evidenceLevel"] = "retained_consistency"
    _write(root, "profile.json", profile)
    _receipt(root, "calibration.json", "baseline.json", "reference.wav")
    _receipt(root, "render.json", "observation-a.json", "edited.wav")
    report = _verify(case, "retained_consistency")
    assert report["status"] == "consistent_unqualified"
    assert all(c["residualRms"] < 0.0004 for c in report["channels"])
    assert "not an absence classifier" in report["limitations"][0]


def test_gain_fitted_only_to_unchanged_reference(
    case: tuple[Path, str, list[list[float]]],
) -> None:
    root, _, samples = case
    baseline = load_operator_json(root / "baseline.json")["routes"]
    channels = _program(samples, baseline)
    for c in channels:
        for i in range(len(c)):
            c[i] *= 2
    (root / "reference.wav").write_bytes(_wav(channels))
    _receipt(root, "calibration.json", "baseline.json", "reference.wav")
    assert "gain qualification" in _verify(case)["reason"]


def test_no_operator_file_can_enable_real_qualification(
    case: tuple[Path, str, list[list[float]]],
) -> None:
    report = _verify(case, "real_issue145")
    assert report["status"] == "refused"
    assert "#145" in report["reason"]


def test_operator_duplicate_keys_and_path_escape(
    case: tuple[Path, str, list[list[float]]],
) -> None:
    root = case[0]
    raw = (root / "profile.json").read_bytes()
    (root / "profile.json").write_bytes(b'{"x":1,"x":2}')
    assert "duplicate" in _verify(case)["reason"]
    (root / "profile.json").write_bytes(raw)
    p = load_operator_json(root / "profile.json")
    p["sources"][0]["path"] = "../escape.wav"
    _write(root, "profile.json", p)
    assert "local path" in _verify(case)["reason"]


def test_render_job_cannot_be_reused_for_edited_program(
    case: tuple[Path, str, list[list[float]]],
) -> None:
    root = case[0]
    receipt = load_operator_json(root / "render.json")
    receipt.update(
        jobId="calibration.json",
        queuedJobId="calibration.json",
        polledJobId="calibration.json",
    )
    _write(root, "render.json", receipt)
    assert "job identity reused" in _verify(case)["reason"]


def test_same_decoded_audio_cannot_hide_behind_different_file_hash(
    case: tuple[Path, str, list[list[float]]],
) -> None:
    root = case[0]
    raw = (root / "source-0.wav").read_bytes() + b"different-container"
    (root / "source-1.wav").write_bytes(raw)
    profile = load_operator_json(root / "profile.json")
    profile["sources"][1]["sha256"] = _digest(raw)
    _write(root, "profile.json", profile)
    assert "decoded source alias" in _verify(case)["reason"]


def test_parent_symlink_and_hardlinked_source_refuse(
    case: tuple[Path, str, list[list[float]]], tmp_path: Path
) -> None:
    root, baseline, _ = case
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    report = verify_omission_evidence(
        alias,
        baseline_hash=baseline,
        target=TARGET,
        row_id="row-0",
        primary_source_id="source-0",
        evidence_level="synthetic_injected",
    )
    assert "symbolic link" in report["reason"]
    twin = tmp_path / "twin.wav"
    twin.hardlink_to(root / "source-0.wav")
    assert "independent regular file" in _verify(case)["reason"]


@pytest.mark.parametrize("control,value", [("gainDb", False), ("limiter", 0)])
def test_program_control_boolean_type_neutrality(
    case: tuple[Path, str, list[list[float]]], control: str, value: Any
) -> None:
    _edit(case, lambda o: o["programControls"].update({control: value}))
    result = _verify(case)
    assert result["status"] == "refused"
    assert "program controls" in result["reason"]


def _shared_row_profile(case: tuple[Path, str, list[list[float]]]) -> None:
    root = case[0]
    profile = load_operator_json(root / "profile.json")
    profile["sources"][1]["rowId"] = "row-0"
    profile["sources"][1]["supports"] = [
        {**word, "tokenId": f"aux-{word['tokenId']}"}
        for word in profile["sources"][0]["supports"]
    ]
    _write(root, "profile.json", profile)
    _receipt(root, "calibration.json", "baseline.json", "reference.wav")
    _receipt(root, "render.json", "observation-a.json", "edited.wav")


def test_same_row_auxiliary_supports_do_not_choose_primary(
    case: tuple[Path, str, list[list[float]]],
) -> None:
    _shared_row_profile(case)
    root, baseline, _ = case
    result = verify_omission_evidence(
        root,
        baseline_hash=baseline,
        target=TARGET,
        row_id="row-0",
        primary_source_id="source-0",
        evidence_level="synthetic_injected",
    )
    assert result["status"] == "supported", result
    assert result["sourceId"] == "source-0"
    assert result["omittedTokenIds"] == ["charlie"]


@pytest.mark.parametrize(
    "primary,row,reason",
    [
        ("unknown", "row-0", "primary source"),
        ("source-0", "row-2", "row/source"),
        ("source-1", "row-0", "untouched route"),
    ],
)
def test_trusted_primary_and_row_binding_refuse(
    case: tuple[Path, str, list[list[float]]], primary: str, row: str, reason: str
) -> None:
    _shared_row_profile(case)
    root, baseline, _ = case
    result = verify_omission_evidence(
        root,
        baseline_hash=baseline,
        target=TARGET,
        row_id=row,
        primary_source_id=primary,
        evidence_level="synthetic_injected",
    )
    assert result["status"] == "refused"
    assert reason in result["reason"]
