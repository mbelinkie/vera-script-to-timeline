"""Focused host admission guards for the current temporary-presenter profile."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import (
    qualification_output_package_v2 as package,
)
from vera_timeline_agent import v2_package
from vera_timeline_agent.qualification_output_records_v2 import _canonical


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


@lru_cache(maxsize=8)
def _presenter_png(
    width: int = 320,
    height: int = 720,
    red: tuple[int, int, int, int] = (230, 20, 20, 255),
) -> bytes:
    if (width, height, red) == (320, 720, (230, 20, 20, 255)):
        return (Path(__file__).parent / "data/issue250/presenter.png").read_bytes()
    rows = []
    for y in range(height):
        row = bytearray([255, 0, 255, 0] * width)
        for x0, x1, y0, y1, color in (
            (80, 239, 100, 619, red),
            (120, 199, 20, 99, (20, 230, 20, 255)),
        ):
            if y0 <= y <= y1:
                for x in range(x0, min(x1 + 1, width)):
                    row[x * 4 : x * 4 + 4] = bytes(color)
        rows.append(b"\x00" + row)
    raw = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + _png_chunk(b"IEND", b"")
    )
    return raw


def _rgba_alpha(*values: int, default: int = 0) -> bytes:
    alpha = bytearray([default] * (320 * 720))
    for index, value in enumerate(values):
        alpha[index] = value
    pixels = bytearray(320 * 720 * 4)
    pixels[3::4] = alpha
    return bytes(pixels)


def _presenter_objects() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    document = {"id": "synthetic-presenter-test"}
    manifest = {
        "timeline": {"durationFrames": 1},
        "events": [
            {
                "kind": "placeholder",
                "provenance": {"slotId": package._PRESENTER_SLOT},
                "pictureTreatment": {
                    "kind": "still",
                    "composition": {"framingPolicy": "contain"},
                    "reference": {
                        "contentHash": "sha256:" + package._PRESENTER_PNG_SHA256,
                        "width": 320,
                        "height": 720,
                    },
                },
            }
        ],
    }
    message = "On Camera uses the effective temporary presenter still."
    report = {
        "status": "ready",
        "migrationIssues": [],
        "diagnostics": [
            {
                "id": "5e77b270-31bf-5ab0-8a99-4698599c131e",
                "code": "TEMPORARY_PRESENTER_STILL",
                "severity": "warning",
                "message": message,
                "entity": {
                    "id": package._PRESENTER_SLOT,
                    "kind": "slot",
                    "path": "presenterStill",
                },
                "evidence": {"kind": "details", "message": message},
                "recoveryActionKinds": ["REPLACE_TEMPORARY_PRESENTER"],
            }
        ],
        "recoveryActions": [
            {
                "documentId": document["id"],
                "instruction": (
                    "Replace the temporary still with an accepted presenter source "
                    "when available."
                ),
                "kind": "REPLACE_TEMPORARY_PRESENTER",
                "slotId": package._PRESENTER_SLOT,
            }
        ],
    }
    return document, manifest, report


def test_committed_presenter_png_matches_the_fixed_asset_pin() -> None:
    assert package._sha(_presenter_png()) == package._PRESENTER_PNG_SHA256


def test_presenter_pixels_authenticate_png_and_accept_transparent_and_opaque_pixels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "presenter.png"
    path.write_bytes(_presenter_png())
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg_raw = b"test-only mocked ffmpeg identity"
    ffmpeg.write_bytes(ffmpeg_raw)
    monkeypatch.setattr(package, "_FFMPEG", ffmpeg)
    monkeypatch.setattr(package, "_FFMPEG_SHA256", package._sha(ffmpeg_raw))
    monkeypatch.setattr(
        package, "_run_ffmpeg_raw", lambda _path, *, still: _rgba_alpha(0, 255)
    )
    states: dict[Path, tuple[int, int, int, int, int]] = {}
    hashes: dict[Path, str] = {}

    package._presenter_pixels(path, states, hashes)

    assert hashes[path] == package._PRESENTER_PNG_SHA256
    assert states[path] == package._state(path)
    assert hashes[package._FFMPEG] == package._FFMPEG_SHA256


def test_presenter_pixels_rejects_opaque_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "presenter.png"
    path.write_bytes(_presenter_png())
    monkeypatch.setattr(
        package,
        "_run_ffmpeg_raw",
        lambda _path, *, still: _rgba_alpha(default=255),
    )

    with pytest.raises(
        package.QualificationPackageError, match="transparent and opaque"
    ):
        package._presenter_pixels(path, {}, {})


@pytest.mark.parametrize(
    ("raw", "expected_message", "replace_pin"),
    [
        (_presenter_png(red=(231, 20, 20, 255)), "Presenter PNG bytes differ", False),
        (_presenter_png(width=321), "exact 320x720 RGBA image", True),
    ],
)
def test_presenter_pixels_refuses_replacement_and_wrong_dimensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw: bytes,
    expected_message: str,
    replace_pin: bool,
) -> None:
    path = tmp_path / "presenter.png"
    path.write_bytes(raw)
    if replace_pin:
        # Exercise the independent IHDR check even if a different asset were pinned.
        monkeypatch.setattr(
            package, "_PRESENTER_PNG_SHA256", hashlib.sha256(raw).hexdigest()
        )
    monkeypatch.setattr(
        package,
        "_run_ffmpeg_raw",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("decode reached")
        ),
    )

    with pytest.raises(package.QualificationPackageError, match=expected_message):
        package._presenter_pixels(path, {}, {})


def test_presenter_report_accepts_only_the_exact_warning_and_contained_image() -> None:
    document, manifest, report = _presenter_objects()

    package._presenter_report(document, manifest, report)


@pytest.mark.parametrize(
    ("mutation", "expected_message"),
    [
        ("missing-diagnostic", "exact single temporary-still warning"),
        ("extra-diagnostic", "exact single temporary-still warning"),
        ("wrong-label", "exact single temporary-still warning"),
        ("wrong-recovery", "readiness/recovery differs"),
        ("cover", "image identity/contain geometry differs"),
        ("wrong-dimensions", "image identity/contain geometry differs"),
        ("replacement", "image identity/contain geometry differs"),
    ],
)
def test_presenter_report_rejects_warning_recovery_and_image_drift(
    mutation: str, expected_message: str
) -> None:
    document, manifest, report = _presenter_objects()
    if mutation == "missing-diagnostic":
        report["diagnostics"] = []
    elif mutation == "extra-diagnostic":
        report["diagnostics"].append({"code": "UNEXPECTED"})
    elif mutation == "wrong-label":
        report["diagnostics"][0]["code"] = "OTHER_WARNING"
    elif mutation == "wrong-recovery":
        report["recoveryActions"][0]["kind"] = "OTHER_ACTION"
    elif mutation == "cover":
        manifest["events"][0]["pictureTreatment"]["composition"]["framingPolicy"] = (
            "cover"
        )
    elif mutation == "wrong-dimensions":
        manifest["events"][0]["pictureTreatment"]["reference"]["width"] = 321
    else:
        manifest["events"][0]["pictureTreatment"]["reference"]["contentHash"] = (
            "sha256:" + "0" * 64
        )

    with pytest.raises(package.QualificationPackageError, match=expected_message):
        package._presenter_report(document, manifest, report)


def test_presenter_profile_retains_the_original_document_and_dependency_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_root = tmp_path / "presenter-fixture"
    inputs = fixture_root / "inputs"
    inputs.mkdir(parents=True)
    for name in package._PRESENTER_INPUT_PINS:
        (inputs / name).write_bytes(b"{}")
    monkeypatch.setattr(package, "_PRESENTER_ROOT", fixture_root)
    output = tmp_path / "admission"

    with pytest.raises(
        package.QualificationPackageError, match="original fixture inputs differ"
    ):
        package.admit_qualification_package_v2(
            output, profile=package.PRESENTER_PROFILE
        )

    assert not output.exists()


def test_synthetic_profile_still_requires_a_verified_public_package_root(
    tmp_path: Path,
) -> None:
    output = tmp_path / "ordinary-admission"

    with pytest.raises(
        package.QualificationPackageError,
        match="verified synthetic package root required",
    ):
        package.admit_qualification_package_v2(
            output, profile=package.SYNTHETIC_PROFILE
        )

    assert not output.exists()


@pytest.mark.slow
def test_presenter_admission_uses_pinned_originals_and_current_execution_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_inputs = package._PRESENTER_ROOT / "inputs"
    required = [fixture_inputs / name for name in package._PRESENTER_INPUT_PINS]
    required.append(package._PRESENTER_ROOT / "presenter.png")
    if not all(path.is_file() for path in required):
        pytest.skip("fixed presenter host originals are unavailable")
    if (
        any(
            package._sha(path.read_bytes()) != pin
            for path, pin in zip(
                required[: len(package._PRESENTER_INPUT_PINS)],
                package._PRESENTER_INPUT_PINS.values(),
                strict=True,
            )
        )
        or package._sha(required[-1].read_bytes()) != package._PRESENTER_PNG_SHA256
    ):
        pytest.skip("fixed presenter host originals are unavailable")

    cache_root = tmp_path / "admission-cache"
    monkeypatch.setattr(package, "_ADMISSION_CACHE_ROOT", cache_root)
    monkeypatch.setattr(package, "_ADMISSION_CACHE_KEY", cache_root / "hmac-key")
    admission = package.admit_qualification_package_v2(
        tmp_path / "presenter-admission", profile=package.PRESENTER_PROFILE
    )

    original_document = admission.original_document_path.read_bytes()
    original_dependencies = admission.original_dependencies_path.read_bytes()
    execution_dependencies = admission.execution_dependencies_path.read_bytes()
    current_compiler = (
        Path(package.__file__).resolve().parents[2]
        / "packages/contracts/src/compiler-core-v2.ts"
    )
    execution_value = json.loads(execution_dependencies)

    assert admission.profile == package.PRESENTER_PROFILE
    assert (
        package._sha(original_document)
        == package._PRESENTER_INPUT_PINS["script-document-v2.json"]
    )
    assert (
        package._sha(original_dependencies)
        == package._PRESENTER_INPUT_PINS["compiler-dependencies-v2.json"]
    )
    assert package._sha(admission.execution_document_path.read_bytes()) == package._sha(
        original_document
    )
    original_value = json.loads(original_dependencies)
    original_value["compiler"]["sourceHash"] = execution_value["compiler"]["sourceHash"]
    assert execution_value["compiler"]["sourceHash"] == (
        "sha256:" + package._sha(current_compiler.read_bytes())
    )
    assert package._sha(execution_dependencies) == package._sha(
        _canonical(original_value)
    )
    with pytest.raises(v2_package.V2PackageError, match="fully ready"):
        v2_package._validate_inputs(
            json.loads(original_document),
            execution_value,
            admission.manifest,
            admission.report,
        )
    reopened = package.load_qualification_package_v2(
        admission.admission_path, package._sha(admission.admission_path.read_bytes())
    )
    reopened.assert_current()
    assert reopened.diagnostics == admission.diagnostics
