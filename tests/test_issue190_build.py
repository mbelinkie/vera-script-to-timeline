"""New sanitized #190 cases; no original inputs or native effects."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

import pytest
from issue190_case import make_proof_case, make_sparse_proof_case, pin, write
from vera_timeline_agent import roundtrip_v2_build
from vera_timeline_agent.narration.models import identity_hash
from vera_timeline_agent.roundtrip_build import ProofBuildError
from vera_timeline_agent.roundtrip_v2_build import PreparedProofBuildV2
from vera_timeline_agent.v2_package import V2PackageError

# Repeated real Node compiler/package handoffs run serially in the full gate.
pytestmark = pytest.mark.slow


def test_missing_request_refuses_without_creating_outputs(tmp_path: Path) -> None:
    with pytest.raises(ProofBuildError):
        PreparedProofBuildV2(tmp_path, authenticate=lambda *_: None)
    assert list(tmp_path.iterdir()) == []


def test_unknown_request_version_refuses(tmp_path: Path) -> None:
    (tmp_path / "proof-request-v2.json").write_text('{"schemaVersion":"v1"}')
    with pytest.raises(ProofBuildError):
        PreparedProofBuildV2(tmp_path, authenticate=lambda *_: None)
    assert not (tmp_path / "execution").exists()


def test_synthetic_deterministic_preflight_and_public_package(tmp_path: Path) -> None:
    _, probe = make_proof_case(tmp_path)
    calls: list[str] = []
    build = PreparedProofBuildV2(
        tmp_path,
        authenticate=lambda kind, *_: calls.append(kind),
        read_probe=probe,
    )
    first, second = build.preflight(), build.preflight()
    assert first == second
    assert first["evidenceLevel"] == "local_prepared"
    assert first["unchecked"]
    package = build.prepare_package()
    assert package["evidenceLevel"] == "local_prepared"
    assert package == build.prepare_package()
    assert "private_preparation" in calls


@pytest.mark.parametrize(
    "attack",
    [
        "unknown",
        "rate",
        "receipt",
        "media",
        "compiler",
        "source",
        "authority",
        "r16-substitution",
        "unknown-profile",
    ],
)
def test_preflight_refuses_before_native_effects(tmp_path: Path, attack: str) -> None:
    request, probe = make_proof_case(tmp_path)
    if attack == "unknown":
        request["override"] = True
    elif attack == "rate":
        import json

        path = Path(request["executionInputs"]["dependencies"]["path"])
        value = json.loads(path.read_bytes())
        value["timeline"]["frameRate"] = {"numerator": 48, "denominator": 2}
        write(path, value)
    elif attack == "receipt":
        next(iter(request["preparations"].values()))["receipt"]["sha256"] = (
            "sha256:" + "0" * 64
        )
    elif attack == "media":
        Path(next(iter(request["media"].values()))["path"]).write_bytes(b"changed")
    elif attack == "compiler":
        request["sourcePins"]["packages/contracts/src/compiler-core-v2.ts"] = (
            "sha256:" + "0" * 64
        )
    elif attack == "source":
        next(iter(request["preparations"].values()))["original"]["sha256"] = (
            "sha256:" + "0" * 64
        )
    elif attack == "authority":
        Path(request["authority"]["path"]).write_bytes(b"changed")
    elif attack == "r16-substitution":
        request["lane"] = "r16_private"
    else:
        import json

        path = Path(request["executionInputs"]["dependencies"]["path"])
        value = json.loads(path.read_bytes())
        value["preparedMedia"][0]["profile"]["profileVersion"] = "generic"
        write(path, value)
    write(tmp_path / "proof-request-v2.json", request)
    with pytest.raises(ProofBuildError):
        PreparedProofBuildV2(
            tmp_path, authenticate=lambda *_: None, read_probe=probe
        ).preflight()
    assert not list(tmp_path.rglob("package-attestation.json"))


def test_missing_actual_probe_and_rejected_authority_refuse(tmp_path: Path) -> None:
    make_proof_case(tmp_path)
    with pytest.raises(ProofBuildError, match="probe port unavailable"):
        PreparedProofBuildV2(tmp_path, authenticate=lambda *_: None).preflight()

    def reject(*_: object) -> None:
        raise ProofBuildError("untrusted authority")

    with pytest.raises(ProofBuildError, match="untrusted authority"):
        PreparedProofBuildV2(tmp_path, authenticate=reject)


def rebind(request: dict[str, Any], root: Path) -> None:
    for key in ("document", "dependencies"):
        request["executionInputs"][key] = pin(
            Path(request["executionInputs"][key]["path"])
        )
    request["originalInputs"] = {
        k: v["sha256"] for k, v in request["executionInputs"].items()
    }
    request["originalFiles"] = copy.deepcopy(request["executionInputs"])
    write(root / "proof-request-v2.json", request)


@pytest.mark.parametrize("subject", ["document", "dependencies"])
def test_r16_rehashed_substitution_refuses_before_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, subject: str
) -> None:
    request, probe = make_proof_case(tmp_path)
    request["lane"] = "r16_private"
    monkeypatch.setattr(roundtrip_v2_build, "R16_INPUTS", request["originalInputs"])
    original = tmp_path / f"original-{subject}.json"
    execution = Path(request["executionInputs"][subject]["path"])
    original.write_bytes(execution.read_bytes())
    request["originalFiles"][subject] = pin(original)
    value = json.loads(execution.read_bytes())
    if subject == "document":
        value["liveHeadSequence"] += 1
    else:
        value["build"]["buildId"] = "00000000-0000-4000-8000-000000000999"
    write(execution, value)
    request["executionInputs"][subject] = pin(execution)
    write(tmp_path / "proof-request-v2.json", request)
    calls: list[str] = []
    label = "dependency" if subject == "dependencies" else "document"
    with pytest.raises(ProofBuildError, match=f"R16 {label} substitution"):
        PreparedProofBuildV2(
            tmp_path, authenticate=lambda kind, *_: calls.append(kind), read_probe=probe
        )
    assert calls == []
    assert not (tmp_path / "execution").exists()


@pytest.mark.parametrize("policy", ["quiet", "full"])
def test_actual_prepared_source_audio_positive(tmp_path: Path, policy: str) -> None:
    _, probe = make_proof_case(tmp_path, scenario=f"source-audio-{policy}")
    result = PreparedProofBuildV2(
        tmp_path, authenticate=lambda *_: None, read_probe=probe
    ).prepare_package()
    assert result["evidenceLevel"] == "local_prepared"


@pytest.mark.parametrize(
    ("attack", "message"),
    [
        ("probe", "actual decoded probe differs"),
        ("profile", "only finite accepted private preparation profiles"),
        ("mode", "private preparation mode/extent differs"),
        ("pcm-format", "source PCM format/sample count differs"),
        ("pcm-channels", "source PCM format/sample count differs"),
        ("pcm-rate", "source PCM format/sample count differs"),
        ("pcm-truncated", "truncated source PCM"),
        ("pcm-content", "prepared source PCM bytes differ"),
        ("missing-audio", "source audio PCM pin required"),
        ("unbound-audio", "unbound source audio PCM"),
    ],
)
def test_rehashed_preparation_semantics_refuse(
    tmp_path: Path, attack: str, message: str
) -> None:
    scenario = "verified-reuse" if attack == "unbound-audio" else "source-audio-quiet"
    request, probe = make_proof_case(tmp_path, scenario=scenario)
    dep_path = Path(request["executionInputs"]["dependencies"]["path"])
    dep = json.loads(dep_path.read_bytes())
    binding = dep["preparedMedia"][0]
    pins = request["preparations"][binding["requirementKey"]]
    receipt_path = Path(pins["receipt"]["path"])
    receipt = json.loads(receipt_path.read_bytes())
    if attack in {"profile", "mode"}:
        version = (
            "unapproved/v1"
            if attack == "profile"
            else "issue-148-private-png-still-cfr/v1"
        )
        receipt["profile"]["profileVersion"] = version
        binding["profile"].update(
            profileVersion=version, profileHash=identity_hash(receipt["profile"])
        )
        receipt["binding"] = copy.deepcopy(binding)
        receipt["inputs"]["profile"] = copy.deepcopy(binding["profile"])
    elif attack == "missing-audio":
        pins["audio"] = None
    elif attack == "unbound-audio":
        pins["audio"] = copy.deepcopy(pins["delivered"])
    elif attack.startswith("pcm"):
        audio_path = Path(pins["audio"]["path"])
        audio = receipt["audio"]
        if attack in {"pcm-format", "pcm-channels", "pcm-rate"}:
            channels = 2 if attack == "pcm-channels" else audio["channels"]
            width = 2 if attack == "pcm-format" else 3
            rate = 44100 if attack == "pcm-rate" else 48000
            with wave.open(str(audio_path), "wb") as stream:
                stream.setparams((channels, width, rate, 0, "NONE", "not compressed"))
                stream.writeframes(bytes(channels * width * audio["decodedSamples"]))
        elif attack == "pcm-truncated":
            audio_path.write_bytes(audio_path.read_bytes()[:-3])
        pins["audio"] = pin(audio_path)
        for key, media in request["media"].items():
            if media["path"] == str(audio_path):
                request["media"][key] = pin(audio_path)
        audio["contentHash"] = (
            "sha256:" + "0" * 64
            if attack == "pcm-content"
            else pin(audio_path)["sha256"]
        )
    write(receipt_path, receipt)
    pins["receipt"] = pin(receipt_path)
    write(dep_path, dep)
    if attack in {"profile", "mode"}:
        # Binding changes source IDs; keep the attack's media complete.
        old_ids = [
            key.removeprefix("original:")
            for key in request["media"]
            if key.startswith("original:")
        ]
        assert len(old_ids) == 1
        actual = subprocess.run(
            [
                shutil.which("node") or "node",
                str(roundtrip_v2_build.BRIDGE),
                request["executionInputs"]["document"]["path"],
                str(dep_path),
            ],
            capture_output=True,
            check=True,
        )
        sources = json.loads(actual.stdout)["result"]["manifest"]["sources"]
        new_id = next(
            source["id"]
            for source in sources
            if source.get("preparationRequirementKey") == binding["requirementKey"]
        )
        for prefix in ("source", "original"):
            request["media"][f"{prefix}:{new_id}"] = request["media"].pop(
                f"{prefix}:{old_ids[0]}"
            )
    rebind(request, tmp_path)

    def actual_probe(path: Path, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"different": True} if attack == "probe" else probe(path, parameters)

    with pytest.raises(ProofBuildError, match=message):
        PreparedProofBuildV2(
            tmp_path, authenticate=lambda *_: None, read_probe=actual_probe
        ).preflight()
    assert not list(tmp_path.rglob("package-attestation.json"))


def test_sparse_fractional_preflight_checks_actual_pcm_and_receipts(
    tmp_path: Path,
) -> None:
    make_sparse_proof_case(tmp_path)
    kinds: list[str] = []
    result = PreparedProofBuildV2(
        tmp_path, authenticate=lambda kind, *_: kinds.append(kind)
    ).prepare_package()
    assert result["evidenceLevel"] == "local_prepared"
    assert "narration_preparation" in kinds


def test_rehashed_insufficient_source_refuses_before_package(tmp_path: Path) -> None:
    request, probe = make_proof_case(tmp_path, scenario="verified-reuse")
    dep_path = Path(request["executionInputs"]["dependencies"]["path"])
    dep = json.loads(dep_path.read_bytes())
    dep["occurrenceResolutions"][0]["logicalSourceBounds"]["endFrame"] = 31
    write(dep_path, dep)
    rebind(request, tmp_path)
    with pytest.raises(ProofBuildError):
        PreparedProofBuildV2(
            tmp_path, authenticate=lambda *_: None, read_probe=probe
        ).preflight()
    assert not list(tmp_path.rglob("package-attestation.json"))


@pytest.mark.parametrize(
    "attack",
    [
        "rate",
        "stale-text",
        "stale-revision",
        "timing-bytes",
        "review-bytes",
        "pcm-profile",
        "pcm-truncated",
        "missing-media",
        "missing-receipt",
    ],
)
def test_rehashed_sparse_semantic_attacks_refuse(tmp_path: Path, attack: str) -> None:
    request = make_sparse_proof_case(tmp_path)
    dep_path = Path(request["executionInputs"]["dependencies"]["path"])
    dep = json.loads(dep_path.read_bytes())
    row = dep["narrationBoundaryEvidence"][0]
    pins = request["narrationReceipts"][row["blockId"]]
    if attack == "rate":
        dep["timeline"]["frameRate"] = {"numerator": 30, "denominator": 1}
    elif attack == "stale-text":
        row["textHash"] = "sha256:" + "0" * 64
    elif attack == "stale-revision":
        row["blockRevision"] += 1
    elif attack in {"timing-bytes", "review-bytes"}:
        kind = "timing" if attack == "timing-bytes" else "review"
        path = Path(pins[kind]["path"])
        write(path, {"synthetic": "changed but pin refreshed"})
        pins[kind] = pin(path)
    elif attack.startswith("pcm"):
        import wave

        path = Path(
            next(
                p["path"]
                for k, p in request["media"].items()
                if k.startswith("source:")
            )
        )
        if attack == "pcm-profile":
            with wave.open(str(path), "wb") as stream:
                stream.setparams(
                    (
                        1,
                        2,
                        48000,
                        row["audio"]["durationSamples"],
                        "NONE",
                        "not compressed",
                    )
                )
                stream.writeframes(bytes(row["audio"]["durationSamples"] * 2))
        else:
            path.write_bytes(path.read_bytes()[:-3])
        request["media"][f"source:{row['narrationAssetId']}"] = pin(path)
        row["audioHash"] = row["audio"]["audioHash"] = pin(path)["sha256"]
    elif attack == "missing-media":
        del request["media"][f"source:{row['narrationAssetId']}"]
    else:
        request["narrationReceipts"] = {}
    write(dep_path, dep)
    rebind(request, tmp_path)
    expected_error = V2PackageError if attack == "rate" else ProofBuildError
    message = "timeline settings differ" if attack == "rate" else None
    with pytest.raises(expected_error, match=message):
        PreparedProofBuildV2(tmp_path, authenticate=lambda *_: None).preflight()
    assert not list(tmp_path.rglob("package-attestation.json"))
