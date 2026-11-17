"""Truthful rate-specific bindings for rate-independent imported PNG facts."""

from __future__ import annotations

import json
import os
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest
from test_issue336_product_package import _authored_png_case
from vera_timeline_agent import prep_media, prep_media_inputs
from vera_timeline_agent.build_compiler_bridge import invoke_bridge
from vera_timeline_agent.generated.contracts.compiler_dependencies_v2_schema import (
    RationalRate,
    RequestedPreparationRangeV1,
)
from vera_timeline_agent.local_media_import import FFmpegDecoder
from vera_timeline_agent.media_preparation import (
    MediaPreparationError,
    MediaTools,
    PreparationAuthorization,
    file_hash,
    wire,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.v2_package import (
    V2PackageError,
    _validate_preparations,
)

from scripts.issue336_studio_qualify import png

_STILL_FIXTURE = (
    Path(__file__).parent / "data/authoring_v2/issue_173/compiler/"
    "visual-only-image-still-25fps-default.input.golden.json"
)


@pytest.mark.slow
def test_normal_prep_media_binds_selected_project_local_png(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = json.loads(_STILL_FIXTURE.read_bytes())
    document = fixture["document"]
    dependencies = fixture["dependencies"]
    original_descriptor = dependencies["occurrenceResolutions"][0]

    project_root = tmp_path / "project"
    source = project_root / "Media" / "Local Images" / "still.png"
    source.parent.mkdir(parents=True)
    png(source, 32, 24)

    tools = MediaTools()
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        facts = FFmpegDecoder(ffprobe=tools.ffprobe, ffmpeg=tools.ffmpeg).decode(
            fd, "image"
        )
    finally:
        os.close(fd)
    descriptor = _descriptor(source, facts, Fraction(25))
    descriptor.update(
        payloadId=original_descriptor["payloadId"],
        owner=original_descriptor["owner"],
        mediaReferenceId=original_descriptor["mediaReferenceId"],
    )
    dependencies["occurrenceResolutions"] = [descriptor]
    dependencies["preparedMedia"] = []

    script = tmp_path / "script.json"
    script.write_bytes(canonical_json_bytes(document))
    inputs = tmp_path / "compiler-settings"
    inputs.mkdir()
    (inputs / "compiler-dependencies.json").write_bytes(
        canonical_json_bytes(dependencies)
    )
    media_paths = {
        f"source:{descriptor['mediaReferenceId']}": str(source),
        "event:unrelated": str(tmp_path / "unrelated.bin"),
    }
    Path(media_paths["event:unrelated"]).write_bytes(b"preserved")
    (inputs / "media-paths.json").write_bytes(canonical_json_bytes(media_paths))

    monkeypatch.setattr(prep_media_inputs, "_qualified_tools", lambda _: None)
    prepared = prep_media.prepare_project(
        script,
        inputs,
        project_root,
        acquire=lambda _: None,
        narration=lambda *_: None,
        tools=tools,
        report=lambda _: None,
    )

    prepared_dependencies = json.loads(
        (prepared / "compiler-dependencies.json").read_bytes()
    )
    prepared_descriptor = prepared_dependencies["occurrenceResolutions"][0]
    key = prepared_descriptor["preparedMediaRequirementKey"]
    assert key is not None
    assert [
        item["requirementKey"] for item in prepared_dependencies["preparedMedia"]
    ] == [key]
    preparation_paths = json.loads((prepared / "preparation-paths.json").read_bytes())
    assert set(preparation_paths) == {key}
    receipt = json.loads(Path(preparation_paths[key]).read_bytes())
    assert receipt["binding"] == prepared_dependencies["preparedMedia"][0]
    assert receipt["stillEvidence"]["strictPng"]["decodedFrameCount"] == 1

    manifest = prep_media_inputs.read_json_object(
        prepared / "compiler-dependencies.json"
    )
    assert manifest["timeline"]["frameRate"] == {"numerator": 25, "denominator": 1}
    output_media = json.loads((prepared / "media-paths.json").read_bytes())
    compiled_source = next(
        item
        for item in invoke_bridge(
            "compile",
            prepared / "script.json",
            prepared / "compiler-dependencies.json",
        ).result["manifest"]["sources"]
        if item["preparationRequirementKey"] == key
    )
    assert output_media[f"source:{compiled_source['id']}"] == str(source)
    assert output_media[f"original:{compiled_source['id']}"] == str(source)
    assert output_media["event:unrelated"] == media_paths["event:unrelated"]


def test_prep_media_refuses_local_png_outside_project_media(
    tmp_path: Path,
) -> None:
    dependencies = json.loads(_STILL_FIXTURE.read_bytes())["dependencies"]
    descriptor = dependencies["occurrenceResolutions"][0]
    dependencies["preparedMedia"] = []
    needs = {
        "requirements": [
            {
                "payloadId": descriptor["payloadId"],
                "mediaReferenceId": descriptor["mediaReferenceId"],
                "requestedRange": _request(Fraction(25)),
                "sourceSufficiency": "sufficient",
            }
        ]
    }
    media_root = tmp_path / "project" / "Media"
    media_root.mkdir(parents=True)
    outside_png = tmp_path / "outside.png"
    tools = MediaTools()

    with pytest.raises(MediaPreparationError, match="unauthorized_path"):
        prep_media_inputs.prepare_still_inputs(
            needs,
            dependencies,
            {f"source:{descriptor['mediaReferenceId']}": str(outside_png)},
            {},
            media_root,
            tools=tools,
        )

    assert not (media_root / "Prepared Stills").exists()


def _descriptor(source: Path, facts: Any, rate: Fraction) -> dict[str, Any]:
    probe = {
        "kind": "image",
        "demuxer": "image2pipe",
        "codec": "png",
        "width": facts.width,
        "height": facts.height,
        "frames": 1,
    }
    source_id = "00000000-0000-4000-8000-000000006030"
    snapshot = {
        "system": "local_import",
        "snapshotId": source_id,
        "version": 1,
        "packageId": "00000000-0000-4000-8000-000000006031",
        "contentHash": file_hash(source),
        "probeHash": facts.probe_hash,
    }
    return {
        "payloadId": "00000000-0000-4000-8000-000000006032",
        "owner": {
            "kind": "visual_only_block",
            "blockId": "00000000-0000-4000-8000-000000006033",
        },
        "mediaReferenceId": source_id,
        "sourceSnapshot": snapshot,
        "logicalSourceBounds": {
            "startFrame": 0,
            "endFrame": 1,
            "frameRate": wire(rate),
        },
        "sourceFrameMap": {
            "packageFrameZeroLogicalFrame": 0,
            "packageVideoPtsOrigin": wire(Fraction(0)),
            "loggedTimeAtPackageFrameZero": wire(Fraction(0)),
            "decodedPackageFrameRate": wire(rate),
            "decodedPackageFrameCount": 1,
            "packageVideoTimeBase": wire(1 / rate),
            "sourceAudioStreamMappings": [],
            "descriptorHash": identity_hash({"snapshot": snapshot, "probe": probe}),
            "probeHash": facts.probe_hash,
        },
        "occurrenceSourceInFrame": 0,
        "selectedSourceRange": None,
        "preparedMediaRequirementKey": None,
    }


def _request(rate: Fraction) -> RequestedPreparationRangeV1:
    return cast(
        RequestedPreparationRangeV1,
        {
            "sourceInFrame": 0,
            "duration": wire(1 / rate),
            "preHandle": wire(Fraction(0)),
            "postHandle": wire(Fraction(0)),
        },
    )


def _make_receipt_for_package_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any]]:
    source = tmp_path / "Media" / "Local Images" / "still.png"
    source.parent.mkdir(parents=True)
    png(source, 32, 24)

    class CachedFingerprintTools(MediaTools):
        cached_fingerprint: dict[str, Any] | None = None

        def fingerprint(self) -> dict[str, Any]:
            if self.cached_fingerprint is None:
                self.cached_fingerprint = super().fingerprint()
            return self.cached_fingerprint

    tools = CachedFingerprintTools()
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        facts = FFmpegDecoder(ffprobe=tools.ffprobe, ffmpeg=tools.ffmpeg).decode(
            fd, "image"
        )
    finally:
        os.close(fd)

    rate = Fraction(24000, 1001)
    descriptor = _descriptor(source, facts, rate)
    monkeypatch.setattr(prep_media_inputs, "_qualified_tools", lambda _: None)
    authorization = PreparationAuthorization(
        reference="issue-603-v2-package-validator-test",
        read_roots=(tmp_path,),
        write_root=tmp_path / "Media" / "Prepared Stills",
        tool_hash=identity_hash(tools.fingerprint()),
        minimum_free_bytes=0,
    )
    prepared = prep_media_inputs.prepare_still_media(
        source,
        cast(Any, descriptor),
        _request(rate),
        cast(RationalRate, wire(rate)),
        authorization=authorization,
        tools=tools,
    )
    descriptor["preparedMediaRequirementKey"] = prepared.binding["requirementKey"]
    return prepared.receipt_path, descriptor


def _validate_receipt_path(receipt_path: Path, descriptor: dict[str, Any]) -> Any:
    record = json.loads(receipt_path.read_bytes())
    key = record["requirementKey"]
    manifest = {
        "buildId": "00000000-0000-4000-8000-000000006034",
        "preparationBindings": [record["binding"]],
    }
    dependencies = {"occurrenceResolutions": [descriptor]}
    return _validate_preparations({}, dependencies, manifest, {}, {key: receipt_path})


@pytest.mark.slow
def test_still_receipts_bind_real_import_facts_at_each_logical_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "Media" / "Local Images" / "still.png"
    source.parent.mkdir(parents=True)
    png(source, 32, 24)

    class CachedFingerprintTools(MediaTools):
        cached_fingerprint: dict[str, Any] | None = None

        def fingerprint(self) -> dict[str, Any]:
            if self.cached_fingerprint is None:
                self.cached_fingerprint = super().fingerprint()
            return self.cached_fingerprint

    tools = CachedFingerprintTools()
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        facts = FFmpegDecoder(ffprobe=tools.ffprobe, ffmpeg=tools.ffmpeg).decode(
            fd, "image"
        )
    finally:
        os.close(fd)
    monkeypatch.setattr(prep_media_inputs, "_qualified_tools", lambda _: None)
    tool_hash = identity_hash(tools.fingerprint())
    authorization = PreparationAuthorization(
        reference="issue-603-generated-still-test",
        read_roots=(tmp_path,),
        write_root=tmp_path / "Media" / "Prepared Stills",
        tool_hash=tool_hash,
        minimum_free_bytes=0,
    )

    source_probes: list[dict[str, Any]] = []
    requirement_keys: set[str] = set()
    for rate in (Fraction(24000, 1001), Fraction(25), Fraction(30)):
        descriptor = _descriptor(source, facts, rate)
        prepared = prep_media_inputs.prepare_still_media(
            source,
            cast(Any, descriptor),
            _request(rate),
            cast(RationalRate, wire(rate)),
            authorization=authorization,
            tools=tools,
        )
        record = json.loads(prepared.receipt_path.read_bytes())
        source_probes.append(record["sourceProbe"])
        requirement_keys.add(record["requirementKey"])
        assert (
            record["sourceProbe"]
            == record["deliveredProbe"]
            == {
                "kind": "image",
                "demuxer": "image2pipe",
                "codec": "png",
                "width": facts.width,
                "height": facts.height,
                "frames": 1,
            }
        )
        assert identity_hash(record["sourceProbe"]) == facts.probe_hash
        assert record["stillEvidence"] == {
            "version": "one_png_frame_held_at_timeline_rate/v1",
            "sourceProbeHash": facts.probe_hash,
            "strictPng": {
                "sourceHash": file_hash(source),
                "width": facts.width,
                "height": facts.height,
                "decodedFrameCount": 1,
            },
        }
        assert "stillRateProbe" not in record
        assert record["binding"]["targetRate"] == wire(rate)
        assert record["binding"]["verification"]["decodedFrameRate"] == wire(rate)
        assert record["binding"]["verification"]["videoTimeBase"] == wire(1 / rate)
        assert record["binding"]["mode"] == "verified_reuse"
        assert prepared.video_path == source
        assert prepared.audio_path is None

    assert len(requirement_keys) == 3
    assert source_probes[0] == source_probes[1] == source_probes[2]


@pytest.mark.slow
def test_still_preparation_refuses_a_forged_import_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "Media" / "Local Images" / "still.png"
    source.parent.mkdir(parents=True)
    png(source, 32, 24)

    class CachedFingerprintTools(MediaTools):
        cached_fingerprint: dict[str, Any] | None = None

        def fingerprint(self) -> dict[str, Any]:
            if self.cached_fingerprint is None:
                self.cached_fingerprint = super().fingerprint()
            return self.cached_fingerprint

    tools = CachedFingerprintTools()
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        facts = FFmpegDecoder(ffprobe=tools.ffprobe, ffmpeg=tools.ffmpeg).decode(
            fd, "image"
        )
    finally:
        os.close(fd)

    rate = Fraction(24000, 1001)
    descriptor = _descriptor(source, facts, rate)
    probe = {
        "kind": "image",
        "demuxer": "image2pipe",
        "codec": "png",
        "width": facts.width,
        "height": facts.height,
        "frames": 1,
    }
    monkeypatch.setattr(prep_media_inputs, "_qualified_tools", lambda _: None)
    authorization = PreparationAuthorization(
        reference="issue-603-forged-snapshot-test",
        read_roots=(tmp_path,),
        write_root=tmp_path / "Media" / "Prepared Stills",
        tool_hash=identity_hash(tools.fingerprint()),
        minimum_free_bytes=0,
    )

    descriptor["sourceFrameMap"]["loggedTimeAtPackageFrameZero"] = wire(Fraction(1, 24))
    with pytest.raises(MediaPreparationError, match="one frame at target rate"):
        prep_media_inputs.prepare_still_media(
            source,
            cast(Any, descriptor),
            _request(rate),
            cast(RationalRate, wire(rate)),
            authorization=authorization,
            tools=tools,
        )
    descriptor["sourceFrameMap"]["loggedTimeAtPackageFrameZero"] = wire(Fraction(0))

    imported_bytes = source.read_bytes()
    png(source, 33, 24)
    with pytest.raises(MediaPreparationError, match="PNG import facts"):
        prep_media_inputs.prepare_still_media(
            source,
            cast(Any, descriptor),
            _request(rate),
            cast(RationalRate, wire(rate)),
            authorization=authorization,
            tools=tools,
        )
    source.write_bytes(imported_bytes)
    descriptor["sourceSnapshot"]["probeHash"] = "sha256:" + "0" * 64
    descriptor["sourceFrameMap"]["probeHash"] = descriptor["sourceSnapshot"][
        "probeHash"
    ]
    descriptor["sourceFrameMap"]["descriptorHash"] = identity_hash(
        {"snapshot": descriptor["sourceSnapshot"], "probe": probe}
    )
    with pytest.raises(MediaPreparationError, match="PNG import facts"):
        prep_media_inputs.prepare_still_media(
            source,
            cast(Any, descriptor),
            _request(rate),
            cast(RationalRate, wire(rate)),
            authorization=authorization,
            tools=tools,
        )
    assert not authorization.write_root.exists()


@pytest.mark.slow
def test_v2_package_validates_real_still_receipt_and_requires_its_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt_path, descriptor = _make_receipt_for_package_validation(
        tmp_path, monkeypatch
    )
    record = json.loads(receipt_path.read_bytes())
    key = record["requirementKey"]
    assert _validate_receipt_path(receipt_path, descriptor)[key].record["stillEvidence"]
    assert record["inputs"]["targetRate"] == {"numerator": 24000, "denominator": 1001}

    for name in ("missing", "altered", "interpretation"):
        damaged = json.loads(receipt_path.read_bytes())
        if name == "missing":
            damaged.pop("stillEvidence")
        elif name == "interpretation":
            damaged["inputs"].pop("stillInterpretation")
        else:
            damaged["stillEvidence"]["strictPng"]["width"] = 33
        damaged_path = tmp_path / f"{name}-receipt.json"
        damaged_path.write_bytes(canonical_json_bytes(damaged))
        with pytest.raises(V2PackageError, match="lacks verified PNG evidence"):
            _validate_receipt_path(damaged_path, descriptor)


@pytest.mark.slow
def test_v2_package_keeps_legacy_24_still_receipts_without_new_evidence(
    tmp_path: Path,
) -> None:
    case = _authored_png_case(
        tmp_path, frames=48, motion={"mode": "none"}, framing="contain"
    )
    receipt_path = next(iter(case.preparation_paths.values()))
    receipt = json.loads(receipt_path.read_bytes())
    manifest = json.loads(case.manifest_path.read_bytes())
    assert manifest["timeline"]["frameRate"] == {"numerator": 24, "denominator": 1}
    assert "stillEvidence" not in receipt
    assert "kind" not in receipt["sourceProbe"]

    validated = _validate_preparations(
        json.loads(case.document_path.read_bytes()),
        json.loads(case.dependencies_path.read_bytes()),
        manifest,
        json.loads(case.report_path.read_bytes()),
        case.preparation_paths,
    )
    assert set(validated) == {receipt["requirementKey"]}
