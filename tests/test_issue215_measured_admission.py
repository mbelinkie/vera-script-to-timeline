"""#215 W1: matrix-profile admission of measured (#182) narration evidence."""

from __future__ import annotations

import copy
import io
import json
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from issue182_fixture import build_cache, frozen_block
from vera_timeline_agent import qualification_output_package_v2 as package
from vera_timeline_agent.narration.measure import (
    ALGORITHM_ID,
    ALGORITHM_VERSION,
    ARTIFACT_VERSION,
    DEFAULT_PARAMETERS,
    EVIDENCE_VERSION,
    METHOD,
    ONSET_BASIS,
    TOKENIZATION_VERSION,
    load_asset,
    measure_asset,
    parameters_hash,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, sha256_bytes
from vera_timeline_agent.qualification_output_package_v2 import (
    MATRIX_PROFILE,
    QualificationPackageError,
    _audio_proofs,
    _audio_source_entries,
)
from vera_timeline_agent.qualification_output_records_v2 import _canonical as canonical
from vera_timeline_agent.qualification_output_v2 import SourceProof
from vera_timeline_agent.roundtrip_build import ProofBuildError
from vera_timeline_agent.roundtrip_v2_audio import (
    narration_review_pin,
    reviewed_artifact_hash,
    verify_measured_narration_evidence,
)

BLOCK = "18200000-0000-4000-8000-000000000010"
SOURCE = "narration-source-1"
EVENT = "event-1"
ASSET_ID = "ab" * 32
FRAME = 2002
SAMPLES = 2 * FRAME
MEASUREMENT_LOCATOR = f"baseline/narration-measurements/{ASSET_ID}.measurement.json"
AUDIO_LOCATOR = f"v1/assets/{BLOCK}/{ASSET_ID}/narration.wav"
TIMING_LOCATOR = f"v1/assets/{BLOCK}/{ASSET_ID}/timing.json"


def rat(samples: int) -> dict[str, int]:
    value = Fraction(samples, 48_000)
    return {"numerator": value.numerator, "denominator": value.denominator}


def wav_bytes() -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(3)
        writer.setframerate(48_000)
        writer.writeframes(b"\x01\x00\x00" * SAMPLES)
    return stream.getvalue()


class Measured:
    """A small self-consistent measured evidence row with all its pinned bytes."""

    def __init__(self) -> None:
        self.wav = wav_bytes()
        self.timing = b'{"provider":"timing","marks":[0,41]}'
        audio_hash = sha256_bytes(self.wav)
        timing_hash = sha256_bytes(self.timing)
        parameters = dict(DEFAULT_PARAMETERS)
        algorithm = {
            "id": ALGORITHM_ID,
            "version": ALGORITHM_VERSION,
            "parametersHash": parameters_hash(parameters),
            "parameters": parameters,
        }
        asset_id = "vera-asset-1"
        self.artifact_value: dict[str, Any] = {
            "schemaVersion": ARTIFACT_VERSION,
            "algorithm": algorithm,
            "asset": {
                "cacheAssetId": ASSET_ID,
                "narrationAssetId": asset_id,
                "blockId": BLOCK,
                "blockRevision": 1,
                "textHash": "sha256:" + "11" * 32,
                "audioHash": audio_hash,
                "timingHash": timing_hash,
                "durationSamples": SAMPLES,
                "sampleRate": 48_000,
                "channels": 1,
            },
            "lag": {
                "verified": True,
                "samples": 0,
                "rawSampleRate": 16_000,
                "method": "rms_envelope",
                "transformVerification": {"method": "rms_envelope"},
            },
            "tokens": [
                {
                    "tokenId": "t0",
                    "quotedText": "one",
                    "startOffset": 0,
                    "endOffset": 3,
                    "onsetSamples": 100,
                    "audibleEndSamples": 1500,
                    "endDecision": "measured",
                },
                {
                    "tokenId": "t1",
                    "quotedText": "two",
                    "startOffset": 4,
                    "endOffset": 7,
                    "onsetSamples": 2100,
                    "audibleEndSamples": None,
                    "endDecision": "absent",
                },
            ],
            "refusals": [],
        }
        self.artifact = canonical_json_bytes(self.artifact_value)
        self.row: dict[str, Any] = {
            "schemaVersion": EVIDENCE_VERSION,
            "blockId": BLOCK,
            "blockRevision": 1,
            "textHash": "sha256:" + "11" * 32,
            "tokenizationVersion": TOKENIZATION_VERSION,
            "narrationAssetId": asset_id,
            "audioHash": audio_hash,
            "timingHash": timing_hash,
            "alignmentVersion": "provider-timing/v1",
            "audio": {
                "narrationAssetId": asset_id,
                "audioHash": audio_hash,
                "timingHash": timing_hash,
                "cacheAssetId": ASSET_ID,
                "locator": AUDIO_LOCATOR,
                "durationSamples": SAMPLES,
                "sampleRate": 48_000,
                "channels": 1,
            },
            "tokens": [
                {
                    "tokenId": "t0",
                    "startOffset": 0,
                    "endOffset": 3,
                    "quotedText": "one",
                    "onset": rat(100),
                    "audibleEnd": rat(1500),
                },
                {
                    "tokenId": "t1",
                    "startOffset": 4,
                    "endOffset": 7,
                    "quotedText": "two",
                    "onset": rat(2100),
                },
            ],
            "verification": {
                "method": METHOD,
                "algorithm": algorithm,
                "measurementArtifactLocator": MEASUREMENT_LOCATOR,
                "measurementArtifactHash": sha256_bytes(self.artifact),
                "onsetBasis": ONSET_BASIS,
                "onsetUncertainty": {"numerator": 25, "denominator": 1000},
                "audibleEndUncertainty": {"numerator": 30, "denominator": 1000},
            },
        }

    def retarget(self, mutate: Any) -> None:
        """Mutate the artifact and re-pin it so only the mutation can refuse."""
        mutate(self.artifact_value)
        self.artifact = canonical_json_bytes(self.artifact_value)
        self.row["verification"]["measurementArtifactHash"] = sha256_bytes(
            self.artifact
        )


def reviewed_row() -> dict[str, Any]:
    return {
        "blockId": BLOCK,
        "verification": {"reviewArtifactHash": "sha256:" + "ab" * 32},
    }


# --------------------------------------------------------------------- verifier


def test_self_consistent_measured_evidence_is_admitted() -> None:
    fixture = Measured()
    pin = verify_measured_narration_evidence(
        fixture.row,
        timing=fixture.timing,
        artifact=fixture.artifact,
        audio_sha256=sha256_bytes(fixture.wav),
    )
    assert pin == fixture.row["verification"]["measurementArtifactHash"]
    assert (
        narration_review_pin(
            fixture.row, timing=fixture.timing, artifact=fixture.artifact
        )
        == pin
    )
    # The method is still on the row: measured evidence is never relabelled.
    assert fixture.row["verification"]["method"] == "measured_audio_boundaries/v1"


def test_reviewed_path_is_unchanged() -> None:
    row = reviewed_row()
    assert narration_review_pin(row) == reviewed_artifact_hash(row)
    assert narration_review_pin(row) == "sha256:" + "ab" * 32
    legacy_method = copy.deepcopy(row)
    legacy_method["verification"]["method"] = "reviewed_audio_boundaries/v1"
    assert narration_review_pin(legacy_method) == "sha256:" + "ab" * 32
    # The reviewed-only helper still refuses measured evidence.
    with pytest.raises(ProofBuildError, match="reviewed-only"):
        reviewed_artifact_hash(Measured().row)


@pytest.mark.parametrize("method", ["manual_audio_boundaries/v9", "", 7])
def test_unknown_methods_are_refused(method: object) -> None:
    row = reviewed_row()
    row["verification"]["method"] = method
    with pytest.raises(ProofBuildError, match="unknown and refused"):
        narration_review_pin(row)
    with pytest.raises(QualificationPackageError, match="unknown and refused"):
        package._narration_method(row)


def test_tampered_measurement_artifact_is_refused() -> None:
    fixture = Measured()
    tampered = fixture.artifact.replace(b'"samples":0', b'"samples":9')
    assert tampered != fixture.artifact
    with pytest.raises(ProofBuildError, match="measurement artifact bytes differ"):
        verify_measured_narration_evidence(
            fixture.row, timing=fixture.timing, artifact=tampered
        )


def test_tampered_timing_is_refused() -> None:
    fixture = Measured()
    with pytest.raises(ProofBuildError, match="provider timing bytes differ"):
        verify_measured_narration_evidence(
            fixture.row, timing=fixture.timing + b" ", artifact=fixture.artifact
        )


def test_tampered_audio_is_refused() -> None:
    fixture = Measured()
    with pytest.raises(ProofBuildError, match="narration audio bytes differ"):
        verify_measured_narration_evidence(
            fixture.row,
            timing=fixture.timing,
            artifact=fixture.artifact,
            audio_sha256=sha256_bytes(fixture.wav + b"\x00"),
        )


def test_artifact_audio_hash_must_match_the_evidence() -> None:
    fixture = Measured()
    fixture.retarget(
        lambda value: value["asset"].update(audioHash="sha256:" + "0" * 64)
    )
    with pytest.raises(ProofBuildError, match="audio bytes differ"):
        verify_measured_narration_evidence(
            fixture.row, timing=fixture.timing, artifact=fixture.artifact
        )


def test_tampered_parameters_hash_is_refused() -> None:
    fixture = Measured()
    fixture.row["verification"]["algorithm"]["parametersHash"] = "sha256:" + "5" * 64
    with pytest.raises(ProofBuildError, match="parametersHash differs"):
        verify_measured_narration_evidence(
            fixture.row, timing=fixture.timing, artifact=fixture.artifact
        )


def test_parameters_changed_without_rehash_are_refused() -> None:
    fixture = Measured()
    fixture.row["verification"]["algorithm"]["parameters"]["endQuietDbfs"] = -30
    with pytest.raises(ProofBuildError, match="parametersHash differs"):
        verify_measured_narration_evidence(
            fixture.row, timing=fixture.timing, artifact=fixture.artifact
        )


def test_uncertainty_must_follow_the_declared_parameters() -> None:
    fixture = Measured()
    fixture.row["verification"]["audibleEndUncertainty"] = {
        "numerator": 1,
        "denominator": 1000,
    }
    with pytest.raises(ProofBuildError, match="uncertainty declarations differ"):
        verify_measured_narration_evidence(
            fixture.row, timing=fixture.timing, artifact=fixture.artifact
        )


def test_token_boundaries_must_match_the_measurement_artifact() -> None:
    fixture = Measured()
    fixture.row["tokens"][0]["audibleEnd"] = rat(1600)
    with pytest.raises(ProofBuildError, match="token differs from the measurement"):
        verify_measured_narration_evidence(
            fixture.row, timing=fixture.timing, artifact=fixture.artifact
        )


def test_unverified_lag_or_refusals_are_refused() -> None:
    fixture = Measured()
    fixture.retarget(lambda value: value["lag"].update(verified=False))
    with pytest.raises(ProofBuildError, match="not a verified measurement"):
        verify_measured_narration_evidence(
            fixture.row, timing=fixture.timing, artifact=fixture.artifact
        )


def test_same_rate_measurement_requires_reproduced_transform() -> None:
    fixture = Measured()
    fixture.retarget(
        lambda value: value["lag"].update(
            rawSampleRate=48_000,
            method="sample_correlation",
            uncertaintySamples=0,
            windowsVerified=3,
        )
    )
    with pytest.raises(ProofBuildError, match="supported transform verification"):
        verify_measured_narration_evidence(
            fixture.row, timing=fixture.timing, artifact=fixture.artifact
        )


def test_unclean_locators_are_refused() -> None:
    for locator in ("../escape.json", "/abs/path.json", "a//b.json", ""):
        fixture = Measured()
        fixture.row["verification"]["measurementArtifactLocator"] = locator
        with pytest.raises(ProofBuildError, match="locator"):
            verify_measured_narration_evidence(
                fixture.row, timing=fixture.timing, artifact=fixture.artifact
            )


# --------------------------------------------------------------- package lanes


class CachedMeasured:
    """A replayable local cache measurement for package-ingress tests."""

    def __init__(self, root: Path) -> None:
        self.cache, self.asset, self.asset_key = build_cache(root / "cache")
        self.block = frozen_block()
        loaded = load_asset(self.cache, self.asset_key)
        self.measurement_locator = (
            f"baseline/narration-measurements/{self.asset.asset_id}.measurement.json"
        )
        result = measure_asset(
            loaded, self.block, artifact_locator=self.measurement_locator
        )
        self.wav = loaded.wav_bytes
        self.timing = loaded.timing_bytes
        self.artifact = result.artifact_bytes
        self.row = result.evidence
        self.asset_dir = self.cache.root / "assets" / self.asset_key
        synthesis_key = self.asset.request_hash.removeprefix("sha256:")
        self.synthesis_dir = self.cache.root / "synthesis" / synthesis_key
        measurement = root / "out" / self.measurement_locator
        wav = root / "package" / "narration.wav"
        measurement.parent.mkdir(parents=True, exist_ok=True)
        wav.parent.mkdir(parents=True, exist_ok=True)
        measurement.write_bytes(self.artifact)
        wav.write_bytes(self.wav)
        self.paths = {
            "measurement": measurement,
            "timing": self.asset_dir / "timing.json",
            "wav": wav,
        }


def package_inputs(
    fixture: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    block_id = fixture.row["blockId"]
    audio = {
        "narrationAssetId": SOURCE,
        "audioHash": fixture.row["audioHash"],
        "durationSamples": fixture.row["audio"]["durationSamples"],
        "sampleRate": fixture.row["audio"]["sampleRate"],
        "channels": fixture.row["audio"]["channels"],
    }
    manifest = {
        "sources": [{"id": SOURCE, "narrationAudio": audio}],
        "events": [
            {
                "eventId": EVENT,
                "kind": "narration",
                "provenance": {"blockId": block_id},
            }
        ],
    }
    view = {
        "events": [
            {
                "id": EVENT,
                "sourceId": SOURCE,
                "recordRange": {"startFrame": 0, "durationFrames": 2},
                "sourceRange": {"startFrame": 0, "durationFrames": 2},
            }
        ]
    }
    dependencies = {"narrationBoundaryEvidence": [fixture.row]}
    return manifest, view, dependencies


def build_source_proof(fixture: Measured) -> SourceProof:
    return SourceProof(
        canonical(fixture.row),
        fixture.artifact,
        timing=fixture.timing,
        review=fixture.artifact,
    )


def run_entries(
    fixture: Measured, *, matrix: bool, proof: SourceProof | None = None
) -> list[dict[str, Any]]:
    manifest, view, dependencies = package_inputs(fixture)
    entries, payloads = _audio_source_entries(
        manifest,
        dependencies,
        view,
        {},
        {SOURCE: fixture.wav},
        {SOURCE: proof or build_source_proof(fixture)},
        matrix_profile=matrix,
    )
    assert [kind for kind, _ in payloads] == ["narration_preparation"]
    payload = next(iter(payloads.values()))[0]
    # The method stays visible in the retained proof payload.
    assert payload["row"]["verification"]["method"] == METHOD
    assert (
        payload["reviewHash"] == fixture.row["verification"]["measurementArtifactHash"]
    )
    return entries


def test_matrix_profile_admits_measured_narration_entries() -> None:
    fixture = Measured()
    entries = run_entries(fixture, matrix=True)
    assert len(entries) == 1 and entries[0]["sourceId"] == SOURCE


def test_matrix_profile_refuses_tampered_inputs() -> None:
    fixture = Measured()
    proof = build_source_proof(fixture)
    for tampered in (
        SourceProof(proof.record, proof.receipt, timing=b"x", review=proof.review),
        SourceProof(
            proof.record,
            fixture.artifact + b" ",
            timing=proof.timing,
            review=fixture.artifact + b" ",
        ),
        SourceProof(proof.record, proof.receipt, timing=proof.timing, review=b"{}"),
        SourceProof(proof.record, proof.receipt, timing=None, review=proof.review),
    ):
        with pytest.raises(QualificationPackageError):
            run_entries(fixture, matrix=True, proof=tampered)


def test_matrix_profile_refuses_unknown_method_even_with_a_pinned_review() -> None:
    fixture = Measured()
    fixture.row["verification"]["method"] = "invented_boundaries/v2"
    with pytest.raises(QualificationPackageError, match="unknown and refused"):
        run_entries(fixture, matrix=True)


def test_r16_profile_does_not_admit_measured_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = Measured()
    r6_target = tmp_path / "pinned-r6.json"
    r6_alias = tmp_path / "r6-review.json"
    r14_path = tmp_path / "pinned-r14.json"
    r6_raw = b'{"schemaVersion":"r6-test"}'
    r14_raw = b'{"schemaVersion":"r14-test"}'
    r6_target.write_bytes(r6_raw)
    r6_alias.symlink_to(r6_target)
    r14_path.write_bytes(r14_raw)
    monkeypatch.setattr(package, "_R6", r6_alias)
    monkeypatch.setattr(package, "_R6_TARGET", r6_target)
    monkeypatch.setattr(package, "_R6_SHA256", package._sha(r6_raw))
    monkeypatch.setattr(package, "_R14", r14_path)
    monkeypatch.setattr(package, "_R14_SHA256", package._sha(r14_raw))

    with pytest.raises(
        QualificationPackageError,
        match="narration timing source is not the pinned actual file",
    ):
        run_entries(fixture, matrix=False)


def evidence_paths(paths: dict[str, Path]) -> dict[str, dict[str, Path]]:
    block_id = paths["timing"].parts[-3]
    return {block_id: {"timing": paths["timing"], "measurement": paths["measurement"]}}


def test_matrix_audio_proofs_read_and_track_measured_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = CachedMeasured(tmp_path)
    paths = fixture.paths
    states: dict[Path, Any] = {}
    hashes: dict[Path, str] = {}
    manifest, view, dependencies = package_inputs(fixture)
    bypass_source_entry_profile_check(monkeypatch)
    wavs, proofs, entries, _payloads = _audio_proofs(
        manifest,
        dependencies,
        view,
        {SOURCE: paths["wav"]},
        {},
        states,
        hashes,
        matrix_profile=True,
        narration_evidence_paths=evidence_paths(paths),
        narration_document={"activeDraft": {"blocks": [fixture.block]}},
    )
    assert wavs[SOURCE] == fixture.wav
    assert proofs[SOURCE].timing == fixture.timing
    assert proofs[SOURCE].review == fixture.artifact == proofs[SOURCE].receipt
    assert entries == [{}]
    assert {paths["timing"], paths["measurement"], paths["wav"]} <= set(hashes)
    assert set(fixture.asset_dir.iterdir()) | set(
        fixture.synthesis_dir.iterdir()
    ) <= set(hashes)


@pytest.mark.parametrize("forgery", ["boundary", "parameters"])
def test_matrix_ingress_rejects_forged_self_consistent_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forgery: str
) -> None:
    fixture = CachedMeasured(tmp_path)
    if forgery == "parameters":
        parameters = dict(DEFAULT_PARAMETERS)
        parameters["onsetUncertaintyMs"] += 1
        result = measure_asset(
            load_asset(fixture.cache, fixture.asset_key),
            fixture.block,
            artifact_locator=fixture.measurement_locator,
            parameters=parameters,
        )
        fixture.artifact = result.artifact_bytes
        fixture.row = result.evidence
    else:
        artifact_value = json.loads(fixture.artifact)
        artifact_value["tokens"][0]["onsetSamples"] += 48
        fixture.artifact = canonical_json_bytes(artifact_value)
        fixture.row["tokens"][0]["onset"] = rat(
            artifact_value["tokens"][0]["onsetSamples"]
        )
        fixture.row["verification"]["measurementArtifactHash"] = sha256_bytes(
            fixture.artifact
        )
    fixture.paths["measurement"].write_bytes(fixture.artifact)

    # The generic proof verifier establishes self-consistency only; the matrix
    # package ingress must additionally remeasure against the local raw PCM.
    assert (
        verify_measured_narration_evidence(
            fixture.row,
            timing=fixture.timing,
            artifact=fixture.artifact,
            audio_sha256=sha256_bytes(fixture.wav),
        )
        == fixture.row["verification"]["measurementArtifactHash"]
    )
    with pytest.raises(
        QualificationPackageError,
        match="artifact differs from local cache remeasurement",
    ):
        run_proofs(fixture, evidence_paths(fixture.paths), monkeypatch)


def bypass_source_entry_profile_check(monkeypatch: pytest.MonkeyPatch) -> None:
    # This cache fixture is PCM-16; source-entry serialization independently
    # verifies the production PCM-24 package profile.
    monkeypatch.setattr(
        package, "_audio_source_entries", lambda *args, **kwargs: ([{}], {})
    )


def run_proofs(
    fixture: CachedMeasured, tmp_evidence: Any, monkeypatch: pytest.MonkeyPatch
) -> Any:
    bypass_source_entry_profile_check(monkeypatch)
    manifest, view, dependencies = package_inputs(fixture)
    return _audio_proofs(
        manifest,
        dependencies,
        view,
        {SOURCE: fixture.paths["wav"]},
        {},
        {},
        {},
        matrix_profile=True,
        narration_evidence_paths=tmp_evidence,
        narration_document={"activeDraft": {"blocks": [fixture.block]}},
    )


def test_matrix_audio_proofs_refuse_tampered_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for victim in ("measurement", "timing", "wav"):
        fixture = CachedMeasured(tmp_path / victim)
        paths = fixture.paths
        paths[victim].write_bytes(paths[victim].read_bytes() + b" ")
        with pytest.raises(QualificationPackageError):
            run_proofs(fixture, evidence_paths(paths), monkeypatch)


def test_matrix_audio_proofs_require_declared_paths_inside_the_locator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = CachedMeasured(tmp_path)
    paths = fixture.paths
    with pytest.raises(QualificationPackageError, match="requires its timing"):
        run_proofs(fixture, None, monkeypatch)
    other = tmp_path / "elsewhere.json"
    other.write_bytes(fixture.artifact)
    swapped = {
        fixture.row["blockId"]: {"timing": paths["timing"], "measurement": other}
    }
    with pytest.raises(QualificationPackageError, match="not inside the evidence"):
        run_proofs(fixture, swapped, monkeypatch)


def test_package_admission_entry_points_accept_evidence_paths_only_for_matrix() -> None:
    with pytest.raises(QualificationPackageError, match="matrix profile"):
        package.admit_qualification_package_v2(
            Path("/nonexistent-output"),
            profile=package.R16_PROFILE,
            narration_evidence_paths={BLOCK: {}},
        )
    assert MATRIX_PROFILE == "qualification-output-studio-matrix/v1"


# ------------------------------------------------------- real campaign evidence


def test_prior_measurement_algorithm_version_requires_remeasurement() -> None:
    fixture = Measured()
    fixture.row["verification"]["algorithm"]["version"] = "1"
    with pytest.raises(ProofBuildError, match="algorithm identity differs"):
        verify_measured_narration_evidence(
            fixture.row, timing=fixture.timing, artifact=fixture.artifact
        )


CAMPAIGN = (
    Path.home() / "Library/Application Support/VERA/polly-campaign/issue182-20261020"
)


@pytest.mark.skipif(not CAMPAIGN.is_dir(), reason="#182 campaign evidence absent")
def test_old_real_campaign_evidence_requires_remeasurement() -> None:
    for run in ("baseline", "revised"):
        folder = CAMPAIGN / "out" / run / "narration-measurements"
        for evidence_path in sorted(folder.glob("*.boundary-evidence.json")):
            row = json.loads(evidence_path.read_bytes())
            artifact = evidence_path.with_name(
                evidence_path.name.replace("boundary-evidence", "measurement")
            ).read_bytes()
            timing = (
                CAMPAIGN
                / "cache"
                / row["audio"]["locator"].rsplit("/", 1)[0]
                / "timing.json"
            ).read_bytes()
            wav = (CAMPAIGN / "cache" / row["audio"]["locator"]).read_bytes()
            with pytest.raises(ProofBuildError, match="algorithm identity differs"):
                verify_measured_narration_evidence(
                    row,
                    timing=timing,
                    artifact=artifact,
                    audio_sha256=sha256_bytes(wav),
                )
