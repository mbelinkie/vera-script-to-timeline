from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from vera_timeline_agent.text_plus_template import (
    DEFAULT_TEXT_PLUS_TEMPLATE_METADATA,
    MAX_TEMPLATE_BYTES,
    TemplateValidationError,
    validate_text_plus_template,
)


def _write_asset(
    root: Path,
    *,
    entries: dict[str, bytes],
    expected_bin: str = "VERA Text+ Template",
    expected_clip: str = "Fusion Title",
) -> Path:
    asset = root / "template.drb"
    with zipfile.ZipFile(asset, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    metadata = {
        "schemaVersion": "vera-text-plus-template-v1",
        "assetFile": asset.name,
        "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
        "sizeBytes": asset.stat().st_size,
        "authoringResolveVersion": "21.0.4.0005",
        "expectedBinName": expected_bin,
        "archiveClipName": expected_clip,
        "expectedClipName": "Text+",
        "expectedToolRegistrationIds": ["MediaOut", "TextPlus"],
        "expectedTopology": {
            "mediaPoolItems": 1,
            "generators": 1,
            "fusionCompositions": 1,
            "textPlusTools": 1,
        },
    }
    metadata_path = root / "template.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return metadata_path


def _valid_entries() -> dict[str, bytes]:
    return {
        "project.xml": b"<SM_Project><ProjectName>Template</ProjectName></SM_Project>",
        "MediaPool/Master/MpFolder.xml": (
            b"<Sm2MpFolder><Name>Master</Name><MediaVec/></Sm2MpFolder>"
        ),
        "MediaPool/Master/000_VERA Text+ Template/MpFolder.xml": (
            b"<Sm2MpFolder><Name>VERA Text+ Template</Name><MediaVec>"
            b"<Element><Sm2MpGenerator><Name>Fusion Title</Name>"
            b"<CompositionTable><Sm2TiCompositionTable/></CompositionTable>"
            b"</Sm2MpGenerator></Element></MediaVec></Sm2MpFolder>"
        ),
    }


def test_versioned_template_and_provenance_are_valid() -> None:
    template = validate_text_plus_template(DEFAULT_TEXT_PLUS_TEMPLATE_METADATA)

    assert template.sha256 == (
        "4a984512f1c7eba6f15a4ea8104a6bb4953e50e4f8aa816a53138daf818372ac"
    )
    assert template.expected_bin_name == "VERA Text+ Template"
    assert template.expected_clip_name == "Text+"
    assert template.authoring_resolve_version == "21.0.4.0005"


def test_template_hash_tampering_is_rejected(tmp_path: Path) -> None:
    metadata_path = _write_asset(tmp_path, entries=_valid_entries())
    asset = tmp_path / "template.drb"
    asset.write_bytes(asset.read_bytes() + b"tampered")
    metadata = json.loads(metadata_path.read_text())
    metadata["sizeBytes"] = asset.stat().st_size
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(TemplateValidationError, match="SHA-256"):
        validate_text_plus_template(metadata_path)


def test_template_symlink_is_rejected(tmp_path: Path) -> None:
    metadata_path = _write_asset(tmp_path, entries=_valid_entries())
    asset = tmp_path / "template.drb"
    target = tmp_path / "actual.drb"
    asset.rename(target)
    asset.symlink_to(target)

    with pytest.raises(TemplateValidationError, match="regular file"):
        validate_text_plus_template(metadata_path)


def test_template_path_traversal_is_rejected(tmp_path: Path) -> None:
    entries = _valid_entries() | {"../escape": b"bad"}
    metadata_path = _write_asset(tmp_path, entries=entries)

    with pytest.raises(TemplateValidationError, match="unsafe archive path"):
        validate_text_plus_template(metadata_path)


def test_template_declared_size_mismatch_is_rejected(tmp_path: Path) -> None:
    metadata_path = _write_asset(tmp_path, entries=_valid_entries())
    metadata = json.loads(metadata_path.read_text())
    metadata["sizeBytes"] += 1
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(TemplateValidationError, match="size"):
        validate_text_plus_template(metadata_path)


def test_template_oversize_is_rejected_before_zip_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata_path = _write_asset(tmp_path, entries=_valid_entries())
    monkeypatch.setattr("vera_timeline_agent.text_plus_template.MAX_TEMPLATE_BYTES", 1)

    with pytest.raises(TemplateValidationError, match="maximum"):
        validate_text_plus_template(metadata_path)

    assert MAX_TEMPLATE_BYTES > 1


def test_template_single_generator_topology_is_required(tmp_path: Path) -> None:
    entries = _valid_entries()
    entries["MediaPool/Master/000_VERA Text+ Template/MpFolder.xml"] = (
        b"<Sm2MpFolder><Name>VERA Text+ Template</Name><MediaVec/></Sm2MpFolder>"
    )
    metadata_path = _write_asset(tmp_path, entries=entries)

    with pytest.raises(TemplateValidationError, match="exactly one generator"):
        validate_text_plus_template(metadata_path)
