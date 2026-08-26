"""Validation and provenance for VERA's pinned Text+ media-pool template."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast
from xml.etree import ElementTree

DEFAULT_TEXT_PLUS_TEMPLATE_METADATA = (
    Path(__file__).with_name("assets") / "text_plus_template.json"
)
MAX_TEMPLATE_BYTES = 1024 * 1024
MAX_ARCHIVE_ENTRIES = 64
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 4 * 1024 * 1024


class TemplateValidationError(ValueError):
    """The pinned Text+ template or its provenance is unsafe or inconsistent."""


@dataclass(frozen=True)
class TextPlusTemplate:
    """A validated, immutable Text+ template asset."""

    asset_path: Path
    metadata_path: Path
    sha256: str
    size_bytes: int
    authoring_resolve_version: str
    expected_bin_name: str
    expected_clip_name: str
    expected_fusion_compositions: int
    expected_text_plus_tools: int
    expected_tool_registration_ids: tuple[str, ...]
    append_end_frame_delta: int | None = None
    validated_resolve_version: str | None = None


def validate_text_plus_template(
    metadata_path: Path = DEFAULT_TEXT_PLUS_TEMPLATE_METADATA,
    *,
    require_validated_duration_rule: bool = False,
) -> TextPlusTemplate:
    """Validate provenance, archive safety, and the exported generator topology."""
    metadata_path = metadata_path.resolve()
    metadata = _read_metadata(metadata_path)
    asset_name = _required_string(metadata, "assetFile")
    if Path(asset_name).name != asset_name:
        raise TemplateValidationError("assetFile must be a single local filename")
    asset_path = metadata_path.parent / asset_name
    try:
        details = asset_path.lstat()
    except OSError as error:
        raise TemplateValidationError(
            f"Text+ template asset is missing: {asset_path}"
        ) from error
    if asset_path.is_symlink() or not stat.S_ISREG(details.st_mode):
        raise TemplateValidationError("Text+ template asset must be a regular file")
    size_bytes = details.st_size
    if size_bytes > MAX_TEMPLATE_BYTES:
        raise TemplateValidationError(
            f"Text+ template exceeds the {MAX_TEMPLATE_BYTES}-byte maximum"
        )
    declared_size = _required_int(metadata, "sizeBytes", minimum=1)
    if size_bytes != declared_size:
        raise TemplateValidationError(
            f"Text+ template size differs from provenance: {size_bytes} != "
            f"{declared_size}"
        )
    expected_hash = _required_string(metadata, "sha256")
    if len(expected_hash) != 64 or any(
        value not in "0123456789abcdef" for value in expected_hash
    ):
        raise TemplateValidationError("Text+ template SHA-256 is malformed")
    actual_hash = _sha256(asset_path)
    if actual_hash != expected_hash:
        raise TemplateValidationError(
            "Text+ template SHA-256 differs from its provenance sidecar"
        )
    if metadata.get("schemaVersion") != "vera-text-plus-template-v1":
        raise TemplateValidationError("unsupported Text+ template metadata schema")
    expected_bin = _required_string(metadata, "expectedBinName")
    archive_clip = _required_string(metadata, "archiveClipName")
    expected_clip = _required_string(metadata, "expectedClipName")
    authoring_version = _required_string(metadata, "authoringResolveVersion")
    topology = metadata.get("expectedTopology")
    if not isinstance(topology, dict):
        raise TemplateValidationError("expectedTopology must be an object")
    for key in (
        "mediaPoolItems",
        "generators",
        "fusionCompositions",
        "textPlusTools",
    ):
        if _required_int(topology, key, minimum=1) != 1:
            raise TemplateValidationError(f"expectedTopology.{key} must equal 1")
    expected_registration_ids_value = metadata.get("expectedToolRegistrationIds")
    if (
        not isinstance(expected_registration_ids_value, list)
        or not expected_registration_ids_value
        or not all(
            isinstance(value, str) and value
            for value in expected_registration_ids_value
        )
        or len(set(expected_registration_ids_value))
        != len(expected_registration_ids_value)
    ):
        raise TemplateValidationError(
            "expectedToolRegistrationIds must contain unique nonempty strings"
        )
    expected_registration_ids = tuple(sorted(expected_registration_ids_value))
    _validate_archive(asset_path, expected_bin, archive_clip)
    end_delta = metadata.get("appendEndFrameDelta")
    if end_delta is not None and (
        not isinstance(end_delta, int) or isinstance(end_delta, bool)
    ):
        raise TemplateValidationError("appendEndFrameDelta must be an integer")
    validated_version = metadata.get("validatedResolveVersion")
    if validated_version is not None and (
        not isinstance(validated_version, str) or not validated_version
    ):
        raise TemplateValidationError("validatedResolveVersion must be a string")
    if require_validated_duration_rule and (
        end_delta is None or validated_version is None
    ):
        raise TemplateValidationError(
            "Text+ template has no producer-accepted duration validation rule"
        )
    return TextPlusTemplate(
        asset_path=asset_path,
        metadata_path=metadata_path,
        sha256=actual_hash,
        size_bytes=size_bytes,
        authoring_resolve_version=authoring_version,
        expected_bin_name=expected_bin,
        expected_clip_name=expected_clip,
        expected_fusion_compositions=cast(int, topology["fusionCompositions"]),
        expected_text_plus_tools=cast(int, topology["textPlusTools"]),
        expected_tool_registration_ids=expected_registration_ids,
        append_end_frame_delta=end_delta,
        validated_resolve_version=validated_version,
    )


def _read_metadata(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise TemplateValidationError(
            f"Text+ template metadata could not be read: {path}"
        ) from error
    if not isinstance(value, dict):
        raise TemplateValidationError("Text+ template metadata must be an object")
    return cast(dict[str, Any], value)


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise TemplateValidationError(f"{key} must be a nonempty string")
    return item


def _required_int(value: dict[str, Any], key: str, *, minimum: int) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool) or item < minimum:
        raise TemplateValidationError(f"{key} must be an integer >= {minimum}")
    return item


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_archive(path: Path, expected_bin: str, expected_clip: str) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_ARCHIVE_ENTRIES:
                raise TemplateValidationError(
                    "Text+ template archive inventory is invalid"
                )
            total_size = 0
            for entry in entries:
                pure = PurePosixPath(entry.filename)
                if (
                    pure.is_absolute()
                    or ".." in pure.parts
                    or "\\" in entry.filename
                    or not entry.filename
                ):
                    raise TemplateValidationError(
                        f"unsafe archive path in Text+ template: {entry.filename!r}"
                    )
                if entry.flag_bits & 0x1:
                    raise TemplateValidationError(
                        "encrypted Text+ template entries are forbidden"
                    )
                total_size += entry.file_size
                if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise TemplateValidationError(
                        "Text+ template expanded size exceeds the safety limit"
                    )
            bad_entry = archive.testzip()
            if bad_entry is not None:
                raise TemplateValidationError(
                    f"Text+ template archive CRC failed for {bad_entry}"
                )
            folder_entries = [
                entry for entry in entries if entry.filename.endswith("/MpFolder.xml")
            ]
            matches: list[ElementTree.Element] = []
            for entry in folder_entries:
                root = ElementTree.fromstring(archive.read(entry))
                if root.findtext("Name") == expected_bin:
                    matches.append(root)
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise TemplateValidationError(
            "Text+ template is not a valid DRB archive"
        ) from error
    if len(matches) != 1:
        raise TemplateValidationError(
            f"expected exactly one exported bin named {expected_bin!r}"
        )
    folder = matches[0]
    generators = folder.findall("./MediaVec/Element/Sm2MpGenerator")
    if len(generators) != 1:
        raise TemplateValidationError("expected exactly one generator in template bin")
    if generators[0].findtext("Name") != expected_clip:
        raise TemplateValidationError(
            f"template generator name differs from {expected_clip!r}"
        )
    compositions = generators[0].findall("./CompositionTable/Sm2TiCompositionTable")
    if len(compositions) != 1:
        raise TemplateValidationError(
            "expected exactly one Fusion composition in template generator"
        )
