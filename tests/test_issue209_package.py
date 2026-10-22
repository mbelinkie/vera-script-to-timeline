"""Admission boundaries for the separately named qualification package profiles."""

from __future__ import annotations

import copy
import io
import json
import wave
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import qualification_output_package_v2 as package
from vera_timeline_agent import v2_package
from vera_timeline_agent.qualification_output_records_v2 import _canonical
from vera_timeline_agent.qualification_output_v2 import SourceProof


def test_inventory_reopens_without_including_itself(tmp_path: Path) -> None:
    (tmp_path / "media.bin").write_bytes(b"actual bytes")
    first, raw = package._inventory(tmp_path)
    (tmp_path / "package-inventory.json").write_bytes(raw)
    assert package._inventory(tmp_path) == (first, raw)
    (tmp_path / "extra.bin").write_bytes(b"extra")
    assert package._inventory(tmp_path)[1] != raw


def test_inventory_refuses_symlink_files(tmp_path: Path) -> None:
    target = tmp_path / "media.bin"
    target.write_bytes(b"actual bytes")
    (tmp_path / "linked.bin").symlink_to(target)
    with pytest.raises(package.QualificationPackageError, match="regular"):
        package._inventory(tmp_path)


def test_existing_artifact_must_match_raw_bytes(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    path.write_bytes(b'{"value":1}')
    package._retain(path, b'{"value":1}', existing=True)
    with pytest.raises(package.QualificationPackageError, match="differs"):
        package._retain(path, b'{"value":2}', existing=True)


def test_unknown_profile_refuses_before_creating_output(tmp_path: Path) -> None:
    output = tmp_path / "new"
    with pytest.raises(package.QualificationPackageError, match="unsupported"):
        package.admit_qualification_package_v2(output, profile="operator-selected")
    assert not output.exists()


def test_load_rejects_wrong_raw_pin_before_profile_dispatch(tmp_path: Path) -> None:
    path = tmp_path / "qualification-output-package-admission.json"
    path.write_bytes(b'{"schemaVersion":"qualification-output-package-admission/v1"}')
    with pytest.raises(package.QualificationPackageError, match="raw pin"):
        package.load_qualification_package_v2(path, "0" * 64)


def test_source_entry_identifies_delivered_wav_not_native_audio_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(package, "_CANDIDATE", tmp_path)
    samples = package._FRAME_SAMPLES
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(3)
        wav.setframerate(48000)
        wav.writeframes(b"\x01\x00\x00" * samples)
    wav_raw = stream.getvalue()
    wav_hash = package._sha(wav_raw)
    binding: dict[str, Any] = {"requirementKey": "actual-key"}
    record = {
        "binding": binding,
        "audio": {
            "contentHash": "sha256:" + wav_hash,
            "channels": 1,
            "decodedSamples": samples,
            "resampledFirstSample": 0,
        },
    }
    receipt = _canonical(record)
    prepared = v2_package._Preparation(
        "actual-key", record, receipt, "sha256:" + package._sha(receipt), "receipt.json"
    )
    event = {
        "eventId": "event-audio",
        "kind": "source_audio",
        "recordRange": {"startFrame": 0, "endFrame": 1},
        "preparationBindingHash": package._compiler_json_hash(binding),
        "sourceTimeMapping": {
            "sourceFrameMap": {
                "sourceAudioStreamMappings": [
                    {"audioHash": "sha256:" + "f" * 64, "sampleRate": 48000}
                ]
            }
        },
        "audio": {"sampleRange": {"startFrame": 0, "endFrame": samples}},
    }
    view = {
        "events": [
            {
                "id": "event-audio",
                "sourceId": "event-audio",
                "recordRange": {"startFrame": 0, "durationFrames": 1},
                "sourceRange": {"startFrame": 0, "durationFrames": 1},
            }
        ]
    }
    entries, payloads = package._audio_source_entries(
        {"sources": [], "events": [event]},
        {},
        view,
        {"actual-key": prepared},
        {"event-audio": wav_raw},
        {"event-audio": SourceProof(receipt, receipt)},
    )
    assert entries[0]["nativeSourceSha256"] == wav_hash
    assert entries[0]["pcmFileSha256"] == wav_hash
    assert entries[0]["nativeSourceSha256"] != "f" * 64
    assert ("private_preparation", package._sha(receipt)) in payloads


@pytest.fixture
def retained_r16() -> tuple[dict[str, Any], ...]:
    if not package._MANIFEST.is_file():
        pytest.skip("requires retained local R16 private inputs")
    return tuple(
        json.loads(path.read_bytes())
        for path in (
            package._EXECUTION_DOCUMENT,
            package._EXECUTION_DEPENDENCIES,
            package._MANIFEST,
            package._REPORT,
            package._COMPILE_ONE,
        )
    )


def test_r16_retains_actual_report_and_effective_presenter(
    retained_r16: tuple[dict[str, Any], ...],
) -> None:
    diagnostics, recoveries = package._canonical_r16_report(*retained_r16)
    assert len(diagnostics) == 3
    assert len(recoveries) == 1
    assert retained_r16[1]["authoringDefaults"]["presenterStill"] is None
    assert retained_r16[2]["authoringDefaults"]["presenterStill"] is not None


@pytest.mark.parametrize(
    "mutation",
    ["missing_warning", "extra_warning", "wrong_default", "missing_recovery"],
)
def test_r16_report_tampering_refuses(
    retained_r16: tuple[dict[str, Any], ...], mutation: str
) -> None:
    document, dependencies, manifest, report, compiled = copy.deepcopy(retained_r16)
    if mutation == "missing_warning":
        report["diagnostics"].pop()
    elif mutation == "extra_warning":
        report["diagnostics"].append(copy.deepcopy(report["diagnostics"][0]))
    elif mutation == "missing_recovery":
        report["recoveryActions"] = []
    else:
        manifest["authoringDefaults"]["presenterStill"] = None
    # Even an internally consistent forged envelope cannot relax the finite
    # report/default checks. The public admission also recompiles exact bytes.
    compiled["result"]["manifest"] = manifest
    compiled["result"]["report"] = report
    with pytest.raises(package.QualificationPackageError):
        package._canonical_r16_report(
            document, dependencies, manifest, report, compiled
        )


def test_public_packager_keeps_refusing_r16(
    retained_r16: tuple[dict[str, Any], ...],
) -> None:
    document, dependencies, manifest, report, _compiled = retained_r16
    with pytest.raises(v2_package.V2PackageError):
        v2_package._validate_inputs(document, dependencies, manifest, report)


def test_original_input_link_guards_reject_replaced_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(package, "_PRIVATE", tmp_path)
    target_dir = (
        tmp_path
        / "issue-148/2026-10-11-r15-heroes-base-binding/attempt-01/candidate-inputs"
    )
    target_dir.mkdir(parents=True)
    for name in ("script-document-v2.json", "compiler-dependencies-v2.json"):
        target = target_dir / name
        expected_raw = b'{"synthetic":true}'
        target.write_bytes(expected_raw)
        link = tmp_path / name
        link.symlink_to(target)
        digest = package._sha(expected_raw)
        state = {
            "regularFiles": {
                str(link): {
                    "rawSha256": f"sha256:{digest}",
                    "identity": {
                        "path": str(link),
                        "resolvedTarget": str(target),
                        "linkText": str(target),
                        "linkIdentity": package._file_identity(link),
                        "targetIdentity": package._file_identity(target),
                    },
                }
            }
        }
        raw, states, hashes = package._parse_original_link(link, digest, state)
        assert raw == expected_raw and link in states and target in states
        assert hashes[target] == digest
        target.rename(target.with_suffix(".retained"))
        target.write_bytes(expected_raw)
        with pytest.raises(package.QualificationPackageError, match="identity changed"):
            package._parse_original_link(link, digest, state)


def test_r16_delta_recovers_original_dependency_bytes(
    retained_r16: tuple[dict[str, Any], ...],
) -> None:
    delta_raw = package._DELTA.read_bytes()
    assert package._sha(delta_raw) == package._EXPECTED_DELTA
    delta = json.loads(delta_raw)
    originals = []
    for path, digest in (
        (package._ORIGINAL_DOCUMENT, package._EXPECTED_ORIGINAL_DOCUMENT),
        (package._ORIGINAL_DEPENDENCIES, package._EXPECTED_ORIGINAL_DEPENDENCIES),
    ):
        raw = path.read_bytes()
        assert package._sha(raw) == digest
        originals.append(raw)
    package._authenticate_dependency_delta(
        json.loads(originals[1]),
        retained_r16[1],
        delta,
        package._HOST_ACCEPTANCE.read_bytes(),
    )


def test_r16_delta_refuses_unapproved_default_change(
    retained_r16: tuple[dict[str, Any], ...],
) -> None:
    execution = copy.deepcopy(retained_r16[1])
    execution["authoringDefaults"]["visualOnlyStillDurationMs"] += 1
    with pytest.raises(
        package.QualificationPackageError, match="original dependencies"
    ):
        package._authenticate_dependency_delta(
            json.loads(package._ORIGINAL_DEPENDENCIES.read_bytes()),
            execution,
            json.loads(package._DELTA.read_bytes()),
            package._HOST_ACCEPTANCE.read_bytes(),
        )


def test_r16_duration_bound_is_rejected_before_expensive_work() -> None:
    package._validate_r16_duration({"timeline": {"durationFrames": 1498}})
    with pytest.raises(package.QualificationPackageError, match="1498-frame bound"):
        package._validate_r16_duration({"timeline": {"durationFrames": 1499}})


def test_r16_vector_pins_match_retained_raw_files(
    retained_r16: tuple[dict[str, Any], ...],
) -> None:
    assert package._sha(package._MANIFEST.read_bytes()) == package._R16_MANIFEST_SHA256
    assert package._sha(package._REPORT.read_bytes()) == package._R16_REPORT_SHA256
    assert (
        package._sha(package._COMPILE_ONE.read_bytes())
        == package._R16_COMPILE_ONE_SHA256
    )
    assert (
        package._sha(package._COMPILE_TWO.read_bytes())
        == package._R16_COMPILE_TWO_SHA256
    )


def test_admission_key_reopen_refuses_missing_key_without_creating_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "admission-cache"
    monkeypatch.setattr(package, "_ADMISSION_CACHE_ROOT", root)
    monkeypatch.setattr(package, "_ADMISSION_CACHE_KEY", root / "hmac-key")
    with pytest.raises(package.QualificationPackageError):
        package._admission_hmac_key()
    assert not root.exists()
    key = package._admission_hmac_key(create=True)
    assert len(key) == 32
    assert package._admission_hmac_key() == key
    assert (root / "hmac-key").stat().st_mode & 0o777 == 0o400


def test_large_source_proofs_use_authenticated_content_addressed_blobs(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "package"
    package_root.mkdir()
    record_size = 4 * 1024 * 1024 + 1
    assert record_size < package._MAX_JSON < 2 * record_size
    proofs = {
        "a": SourceProof(b"a" * record_size, b"shared-receipt"),
        "b": SourceProof(b"b" * record_size, b"shared-receipt"),
    }
    payloads = {
        ("private_preparation", package._sha(b"receipt-a")): (
            {"binding": "p" * (4 * 1024 * 1024 - 32)},
        )
    }
    package._retain_verification_blobs(package_root, proofs, payloads, existing=False)
    cache_raw = package._verification_cache_raw(
        profile=package.SYNTHETIC_PROFILE,
        package_root=package_root,
        tracked_paths={},
        tracked_hashes={},
        tracked_links={},
        source_paths={},
        source_proofs=proofs,
        source_entries=[],
        source_wavs={},
        proof_payloads=payloads,
    )
    assert len(cache_raw) < package._MAX_JSON
    cache_value = json.loads(cache_raw)
    assert type(cache_value["sourceProofs"][0]["record"]) is dict
    with pytest.raises(package.QualificationPackageError, match="content addressed"):
        bad_path = copy.deepcopy(cache_value)
        bad_path["sourceProofs"][0]["record"]["path"] = (
            "Verification/proofs/../escape.bin"
        )
        package._parse_verification_cache(
            _canonical(bad_path),
            profile=package.SYNTHETIC_PROFILE,
            package_root=package_root,
        )
    parsed = package._parse_verification_cache(
        cache_raw,
        profile=package.SYNTHETIC_PROFILE,
        package_root=package_root,
    )
    assert parsed[4] == proofs
    assert parsed[7] == payloads
    blob = package_root / cache_value["sourceProofs"][0]["record"]["path"]
    blob.chmod(0o600)
    blob.write_bytes(blob.read_bytes() + b"tamper")
    with pytest.raises(package.QualificationPackageError, match="bytes differ"):
        package._parse_verification_cache(
            cache_raw,
            profile=package.SYNTHETIC_PROFILE,
            package_root=package_root,
        )


def test_load_reopens_verified_cache_without_running_toolchain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "admitted"
    root = output / "package"
    source = root / "PublicPackage" / "Media" / "audio.wav"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"audio bytes")
    attestation = output / "attestation.json"
    attestation.write_bytes(b"attestation bytes")
    view = {
        "sources": [
            {
                "id": "audio",
                "path": "Media/audio.wav",
                "contentHash": "sha256:" + package._sha(source.read_bytes()),
            }
        ],
        "events": [],
    }
    empty = b"{}"
    admission = package._finish_admission(
        output,
        profile=package.SYNTHETIC_PROFILE,
        disposition="verified_synthetic",
        creative_qualification="qualified_synthetic_only",
        original_document=empty,
        original_dependencies=empty,
        execution_document=empty,
        execution_dependencies=empty,
        manifest={"events": []},
        manifest_raw=_canonical({"events": []}),
        report={},
        report_raw=empty,
        compiler_runs=(empty, empty),
        view=view,
        view_raw=_canonical(view),
        diagnostics=[],
        recoveries=[],
        preflight_raw=empty,
        preparation_raw=empty,
        source_entries=[],
        source_proofs={},
        source_wavs={},
        source_paths={"audio": source},
        tracked_paths={},
        tracked_hashes={},
        tracked_links={},
        proof_payloads={},
        attestation_path=attestation,
    )
    admission.assert_current()
    monkeypatch.setattr(
        package,
        "_compiler_bytes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("compiler")),
    )
    monkeypatch.setattr(
        package,
        "_run_pinned_ffprobe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("ffprobe")),
    )
    monkeypatch.setattr(
        package,
        "_run_ffmpeg_raw",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("ffmpeg")),
    )
    reopened = package.load_qualification_package_v2(
        admission.admission_path, package._sha(admission.admission_path.read_bytes())
    )
    assert reopened.admission == admission.admission
    assert reopened.source_paths == admission.source_paths
    cache = admission.package_root / package._VERIFIED_ADMISSION_RELATIVE_PATH
    cache.chmod(0o600)
    cache_value = json.loads(cache.read_text())
    cache_value["profile"] = "tampered-cache"
    cache.write_bytes(_canonical(cache_value))
    with pytest.raises(
        package.QualificationPackageError, match="seal metadata differs"
    ):
        package.load_qualification_package_v2(
            admission.admission_path,
            package._sha(admission.admission_path.read_bytes()),
        )


@pytest.mark.slow
def test_actual_r12_still_pixels_and_full_probe_content_match(
    retained_r16: tuple[dict[str, Any], ...],
) -> None:
    states: dict[Path, tuple[int, int, int, int, int]] = {}
    hashes: dict[Path, str] = {}
    raw, evidence = package._authenticate_r12_stills(retained_r16[1], states, hashes)
    assert package._sha(raw) == package._R12_STILLS_SHA256
    assert len(evidence["candidates"]) == 2
    assert all(path in hashes for path in states)


@pytest.mark.slow
def test_actual_r16_admits_and_reopens_with_original_bytes_and_warnings(
    tmp_path: Path, retained_r16: tuple[dict[str, Any], ...]
) -> None:
    admission = package.admit_qualification_package_v2(
        tmp_path / "r16", profile=package.R16_PROFILE
    )
    assert admission.disposition == "qualification_only"
    assert len(admission.diagnostics) == 3
    assert len(admission.source_entries) == 6
    assert (
        admission.blobs["originalDocumentSha256"]
        == admission.blobs["executionDocumentSha256"]
    )
    assert (
        admission.blobs["originalDependenciesSha256"]
        != admission.blobs["executionDependenciesSha256"]
    )
    assert admission.report == retained_r16[3]
    assert (
        admission.package_root / "Compiler/compile-1.json"
    ).read_bytes() == package._COMPILE_ONE.read_bytes()
    assert (
        admission.package_root / "Compiler/compile-2.json"
    ).read_bytes() == package._COMPILE_TWO.read_bytes()
    admission.assert_current()
    path, digest = admission.serialize_native_admission()
    reopened = package.load_qualification_package_v2(path, digest)
    assert reopened.admission == admission.admission
    assert reopened.blobs == admission.blobs
    assert reopened.native_package_ref() == admission.native_package_ref()
    admitted_native = native._admission_profile(
        {
            "profile": admission.profile,
            "package": admission.native_package_ref(),
            "context": {key: native._hash(raw) for key, raw in admission.blobs.items()},
            "inputs": {
                "originalDocumentPath": str(admission.original_document_path),
                "originalDependenciesPath": str(admission.original_dependencies_path),
                "executionDocumentPath": str(admission.execution_document_path),
                "executionDependenciesPath": str(admission.execution_dependencies_path),
            },
        }
    )
    assert admitted_native["sourceRoot"] == admission.package_root
