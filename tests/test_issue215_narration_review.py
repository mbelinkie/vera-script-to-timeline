"""Matrix narration proof bytes stay bound to the row's pinned review."""

from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_package_v2 as package
from vera_timeline_agent.qualification_output_records_v2 import _canonical
from vera_timeline_agent.qualification_output_v2 import SourceProof


def _install_review_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path, bytes, bytes, str, str]:
    r6_target = tmp_path / "pinned-r6.json"
    r6_alias = tmp_path / "r6-review.json"
    r14_path = tmp_path / "pinned-r14.json"
    r6_raw = b'{"schemaVersion":"r6-test"}'
    r14_raw = b'{"schemaVersion":"r14-test"}'
    r6_target.write_bytes(r6_raw)
    r6_alias.symlink_to(r6_target)
    r14_path.write_bytes(r14_raw)
    r6_hash = package._sha(r6_raw)
    r14_hash = package._sha(r14_raw)
    monkeypatch.setattr(package, "_R6", r6_alias)
    monkeypatch.setattr(package, "_R6_TARGET", r6_target)
    monkeypatch.setattr(package, "_R6_SHA256", r6_hash)
    monkeypatch.setattr(package, "_R14", r14_path)
    monkeypatch.setattr(package, "_R14_SHA256", r14_hash)
    return r6_target, r6_alias, r14_path, r6_raw, r14_raw, r6_hash, r14_hash


def test_matrix_review_selector_tracks_only_the_declared_pinned_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r6_target, r6_alias, r14_path, r6_raw, r14_raw, r6_hash, r14_hash = (
        _install_review_inventory(tmp_path, monkeypatch)
    )
    states: dict[Path, tuple[int, int, int, int, int]] = {}
    hashes: dict[Path, str] = {}

    assert (
        package._track_narration_review("sha256:" + r6_hash, states, hashes) == r6_raw
    )
    assert hashes == {r6_target: r6_hash}
    assert r6_alias not in states

    assert package._track_narration_review(r14_hash, states, hashes) == r14_raw
    assert hashes == {r6_target: r6_hash, r14_path: r14_hash}

    with pytest.raises(
        package.QualificationPackageError,
        match="outside the statically pinned inventory",
    ):
        package._track_narration_review("f" * 64, states, hashes)
    assert hashes == {r6_target: r6_hash, r14_path: r14_hash}


def _narration_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    declared_review_hash: str,
    receipt: bytes,
    review: bytes,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, bytes],
    dict[str, SourceProof],
]:
    block_id = "narration-row-215"
    event_id = "narration-event-215"
    source_id = "narration-source-215"
    timing_raw = b'{"timing":"pinned"}'
    timing_hash = package._sha(timing_raw)
    timing_root = tmp_path / "TimingSources"
    timing_root.mkdir(parents=True)
    (timing_root / f"{block_id}.json").write_bytes(timing_raw)
    monkeypatch.setattr(package, "_CANDIDATE", tmp_path)
    monkeypatch.setattr(package, "_NARRATION_TIMING_HASHES", {block_id: timing_hash})

    wav_stream = io.BytesIO()
    with wave.open(wav_stream, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(3)
        output.setframerate(48000)
        output.writeframes(b"\x00\x00\x00" * package._FRAME_SAMPLES)
    wav_raw = wav_stream.getvalue()
    audio_hash = package._sha(wav_raw)
    audio = {
        "audioHash": "sha256:" + audio_hash,
        "channels": 1,
        "durationSamples": package._FRAME_SAMPLES,
        "sampleRate": 48000,
    }
    record = {
        "audio": audio,
        "audioHash": audio["audioHash"],
        "blockId": block_id,
        "narrationAssetId": source_id,
        "timingHash": "sha256:" + timing_hash,
        "verification": {"reviewArtifactHash": declared_review_hash},
    }
    manifest = {
        "sources": [{"id": source_id, "narrationAudio": audio}],
        "events": [
            {
                "eventId": event_id,
                "kind": "narration",
                "provenance": {"blockId": block_id},
            }
        ],
    }
    dependencies = {"narrationBoundaryEvidence": [record]}
    view = {
        "events": [
            {
                "id": event_id,
                "sourceId": source_id,
                "recordRange": {"startFrame": 0, "durationFrames": 1},
                "sourceRange": {"startFrame": 0, "durationFrames": 1},
            }
        ]
    }
    proofs = {
        source_id: SourceProof(
            _canonical(record), receipt, timing=timing_raw, review=review
        )
    }
    return manifest, dependencies, view, {source_id: wav_raw}, proofs


def test_matrix_audio_proof_must_match_declared_review_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        _r6_target,
        _r6_alias,
        _r14_path,
        r6_raw,
        r14_raw,
        r6_hash,
        _r14_hash,
    ) = _install_review_inventory(tmp_path, monkeypatch)
    manifest, dependencies, view, wavs, proofs = _narration_projection(
        tmp_path / "valid",
        monkeypatch,
        declared_review_hash="sha256:" + r6_hash,
        receipt=r6_raw,
        review=r6_raw,
    )
    timing = proofs["narration-source-215"].timing
    assert timing is not None
    entries, payloads = package._audio_source_entries(
        manifest,
        dependencies,
        view,
        {},
        wavs,
        proofs,
        matrix_profile=True,
    )
    assert entries[0]["provenancePinsSha256"] == package._sha(
        _canonical(
            {
                "timing": package._sha(timing),
                "review": r6_hash,
                "receipt": r6_hash,
            }
        )
    )
    assert ("narration_preparation", r6_hash) in payloads

    (
        mismatched_manifest,
        mismatched_dependencies,
        mismatched_view,
        mismatched_wavs,
        mismatched_proofs,
    ) = _narration_projection(
        tmp_path / "mismatched",
        monkeypatch,
        declared_review_hash="sha256:" + r6_hash,
        receipt=r14_raw,
        review=r14_raw,
    )
    with pytest.raises(
        package.QualificationPackageError,
        match="differs from declared pinned artifact",
    ):
        package._audio_source_entries(
            mismatched_manifest,
            mismatched_dependencies,
            mismatched_view,
            {},
            mismatched_wavs,
            mismatched_proofs,
            matrix_profile=True,
        )

    (
        unknown_manifest,
        unknown_dependencies,
        unknown_view,
        unknown_wavs,
        unknown_proofs,
    ) = _narration_projection(
        tmp_path / "unknown",
        monkeypatch,
        declared_review_hash="sha256:" + "f" * 64,
        receipt=r6_raw,
        review=r6_raw,
    )
    with pytest.raises(
        package.QualificationPackageError,
        match="outside the statically pinned inventory",
    ):
        package._audio_source_entries(
            unknown_manifest,
            unknown_dependencies,
            unknown_view,
            {},
            unknown_wavs,
            unknown_proofs,
            matrix_profile=True,
        )


_PRIVATE_A_PACKAGE = (
    Path.home()
    / "Library/Application Support/VERA/qualification-output-preparation"
    / "issue215-20261018-01/A-original-02/package"
)


@pytest.mark.slow
@pytest.mark.skipif(
    not _PRIVATE_A_PACKAGE.is_dir(),
    reason="requires the retained private Studio A package",
)
def test_private_a_admission_reopens_with_the_declared_r6_review(
    tmp_path: Path,
) -> None:
    admission = package.admit_qualification_package_v2(
        tmp_path / "admission",
        profile=package.MATRIX_PROFILE,
        package_root=_PRIVATE_A_PACKAGE,
        preparation_paths={},
    )
    r6_proofs = [
        proof
        for proof in admission.source_proofs.values()
        if package._json(proof.record, "test narration proof")
        .get("verification", {})
        .get("reviewArtifactHash")
        == "sha256:" + package._R6_SHA256
    ]
    assert r6_proofs
    assert all(
        proof.review is not None
        and package._sha(proof.review) == package._R6_SHA256
        and proof.receipt == proof.review
        for proof in r6_proofs
    )
    admission.assert_current()
    admission_path = admission.admission_path
    reopened = package.load_qualification_package_v2(
        admission_path, package._sha(admission_path.read_bytes())
    )
    reopened.assert_current()
    assert any(
        proof.review is not None and package._sha(proof.review) == package._R6_SHA256
        for proof in reopened.source_proofs.values()
    )
    assert package._R6_TARGET in reopened._tracked_hashes
