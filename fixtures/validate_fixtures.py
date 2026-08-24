#!/usr/bin/env python3
"""Strictly validate the deterministic synthetic media fixture kit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

FIXTURES_DIR = Path(__file__).resolve().parent
DESCRIPTOR_PATH = FIXTURES_DIR / "fixture-kit.json"
MEDIA_DIR = FIXTURES_DIR / "media"

EXPECTED_KIND_COUNTS = {"video": 3, "still": 2, "audio": 1}
CANONICAL_SETTINGS = {
    "video": {
        "frameRate": {"numerator": 24000, "denominator": 1001},
        "width": 1920,
        "height": 1080,
        "pixelAspectRatio": "1/1",
    },
    "audio": {"sampleRateHz": 48000, "channels": 2},
}
TOP_LEVEL_KEYS = {
    "schemaVersion",
    "kitId",
    "description",
    "canonicalSettings",
    "provenance",
    "generation",
    "assets",
}
ASSET_KEYS = {
    "id",
    "role",
    "kind",
    "path",
    "description",
    "provenance",
    "sha256",
    "sizeBytes",
    "media",
}
PROVENANCE_KEYS = {
    "sourceType",
    "generatedBy",
    "containsThirdPartyMedia",
    "containsProductionMedia",
}
GENERATION_KEYS = {
    "command",
    "ffmpegVersion",
    "ffprobeVersion",
    "versionCaveat",
}
VIDEO_MEDIA_KEYS = {
    "streamCount",
    "formatName",
    "codecType",
    "durationSeconds",
    "codecName",
    "profile",
    "pixelFormat",
    "width",
    "height",
    "frameRate",
    "timeBase",
    "durationTs",
    "frameCount",
}
STILL_MEDIA_KEYS = {
    "streamCount",
    "formatName",
    "codecType",
    "codecName",
    "pixelFormat",
    "width",
    "height",
}
AUDIO_MEDIA_KEYS = {
    "streamCount",
    "formatName",
    "codecType",
    "durationSeconds",
    "codecName",
    "sampleFormat",
    "sampleRateHz",
    "channels",
    "channelLayout",
    "timeBase",
    "durationTs",
}
MEDIA_KEYS_BY_KIND = {
    "video": VIDEO_MEDIA_KEYS,
    "still": STILL_MEDIA_KEYS,
    "audio": AUDIO_MEDIA_KEYS,
}
EXTENSION_BY_KIND = {"video": ".mp4", "still": ".png", "audio": ".wav"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*\.v[1-9][0-9]*$")
ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FixtureValidationError(ValueError):
    """Raised when a fixture descriptor or asset violates the local contract."""


def _expect_object(value: object, location: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise FixtureValidationError(f"{location} must be a JSON object")
    return cast(dict[str, Any], value)


def _expect_exact_keys(
    value: dict[str, Any], expected: set[str], location: str
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise FixtureValidationError(
            f"{location} has wrong fields; missing={missing}, unknown={unknown}"
        )


def _expect_nonempty_string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FixtureValidationError(f"{location} must be a non-empty string")
    return value


def _expect_positive_int(value: object, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise FixtureValidationError(f"{location} must be a positive integer")
    return value


def _validate_provenance(value: object, location: str) -> None:
    provenance = _expect_object(value, location)
    _expect_exact_keys(provenance, PROVENANCE_KEYS, location)
    if provenance["sourceType"] != "procedurally_generated_synthetic":
        raise FixtureValidationError(
            f"{location}.sourceType must identify synthetic media"
        )
    _expect_nonempty_string(provenance["generatedBy"], f"{location}.generatedBy")
    for field in ("containsThirdPartyMedia", "containsProductionMedia"):
        if provenance[field] is not False:
            raise FixtureValidationError(f"{location}.{field} must be false")


def _validate_media(media_value: object, kind: str, location: str) -> None:
    media = _expect_object(media_value, location)
    _expect_exact_keys(media, MEDIA_KEYS_BY_KIND[kind], location)
    if media["streamCount"] != 1:
        raise FixtureValidationError(f"{location}.streamCount must equal 1")
    for field in ("formatName", "codecName"):
        _expect_nonempty_string(media[field], f"{location}.{field}")
    expected_codec_type = "audio" if kind == "audio" else "video"
    if media["codecType"] != expected_codec_type:
        raise FixtureValidationError(
            f"{location}.codecType must equal {expected_codec_type}"
        )
    if kind in {"video", "still"}:
        if media["width"] != 1920 or media["height"] != 1080:
            raise FixtureValidationError(f"{location} must be 1920x1080")
        _expect_nonempty_string(media["pixelFormat"], f"{location}.pixelFormat")
    if kind == "video":
        expected = {
            "formatName": "mov,mp4,m4a,3gp,3g2,mj2",
            "codecName": "h264",
            "profile": "High",
            "pixelFormat": "yuv420p",
            "frameRate": "24000/1001",
            "timeBase": "1/24000",
            "durationTs": 48048,
            "frameCount": 48,
            "durationSeconds": "2.002000",
        }
        for field, expected_value in expected.items():
            if media[field] != expected_value:
                raise FixtureValidationError(
                    f"{location}.{field} must equal {expected_value}"
                )
    if kind == "still":
        expected = {
            "formatName": "png_pipe",
            "codecName": "png",
            "pixelFormat": "rgb24",
        }
        for field, expected_value in expected.items():
            if media[field] != expected_value:
                raise FixtureValidationError(
                    f"{location}.{field} must equal {expected_value}"
                )
    if kind == "audio":
        if media["sampleRateHz"] != 48000 or media["channels"] != 2:
            raise FixtureValidationError(f"{location} must be stereo 48 kHz audio")
        expected = {
            "formatName": "wav",
            "codecName": "pcm_s16le",
            "sampleFormat": "s16",
            "channelLayout": "unspecified",
            "timeBase": "1/48000",
            "durationTs": 144000,
            "durationSeconds": "3.000000",
        }
        for field, expected_value in expected.items():
            if media[field] != expected_value:
                raise FixtureValidationError(
                    f"{location}.{field} must equal {expected_value}"
                )


def load_descriptor(path: Path = DESCRIPTOR_PATH) -> dict[str, Any]:
    """Load a descriptor as a JSON object without accepting non-object roots."""
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FixtureValidationError(
            f"cannot read descriptor {path}: {error}"
        ) from error
    return _expect_object(parsed, "descriptor")


def validate_descriptor(descriptor: dict[str, Any]) -> None:
    """Validate the closed fixture-local descriptor schema."""
    _expect_exact_keys(descriptor, TOP_LEVEL_KEYS, "descriptor")
    if descriptor["schemaVersion"] != 1:
        raise FixtureValidationError("descriptor.schemaVersion must equal 1")
    if descriptor["kitId"] != "vera.slice-0.1.synthetic-media-kit.v1":
        raise FixtureValidationError(
            "descriptor.kitId is not the stable Slice 0.1 kit ID"
        )
    _expect_nonempty_string(descriptor["description"], "descriptor.description")
    if descriptor["canonicalSettings"] != CANONICAL_SETTINGS:
        raise FixtureValidationError(
            "descriptor.canonicalSettings must precisely record the D-0004 "
            "fixture defaults"
        )
    _validate_provenance(descriptor["provenance"], "descriptor.provenance")

    generation = _expect_object(descriptor["generation"], "descriptor.generation")
    _expect_exact_keys(generation, GENERATION_KEYS, "descriptor.generation")
    if generation["command"] != "uv run --frozen python -m fixtures.generate_fixtures":
        raise FixtureValidationError("descriptor.generation.command is not canonical")
    if generation["ffmpegVersion"] != "8.1.2":
        raise FixtureValidationError(
            "descriptor.generation.ffmpegVersion must equal 8.1.2"
        )
    if generation["ffprobeVersion"] != "8.1.2":
        raise FixtureValidationError(
            "descriptor.generation.ffprobeVersion must equal 8.1.2"
        )
    _expect_nonempty_string(
        generation["versionCaveat"], "descriptor.generation.versionCaveat"
    )

    assets_value = descriptor["assets"]
    if not isinstance(assets_value, list):
        raise FixtureValidationError("descriptor.assets must be an array")
    assets = cast(list[object], assets_value)
    if len(assets) != sum(EXPECTED_KIND_COUNTS.values()):
        raise FixtureValidationError(
            "descriptor.assets must contain exactly six assets"
        )

    ids: set[str] = set()
    roles: set[str] = set()
    paths: set[str] = set()
    counts = dict.fromkeys(EXPECTED_KIND_COUNTS, 0)
    for index, asset_value in enumerate(assets):
        location = f"descriptor.assets[{index}]"
        asset = _expect_object(asset_value, location)
        _expect_exact_keys(asset, ASSET_KEYS, location)
        asset_id = _expect_nonempty_string(asset["id"], f"{location}.id")
        role = _expect_nonempty_string(asset["role"], f"{location}.role")
        kind = _expect_nonempty_string(asset["kind"], f"{location}.kind")
        relative_path = _expect_nonempty_string(asset["path"], f"{location}.path")
        _expect_nonempty_string(asset["description"], f"{location}.description")
        if not ID_PATTERN.fullmatch(asset_id):
            raise FixtureValidationError(
                f"{location}.id has an invalid stable-ID shape"
            )
        if not ROLE_PATTERN.fullmatch(role):
            raise FixtureValidationError(f"{location}.role has an invalid role shape")
        if kind not in EXPECTED_KIND_COUNTS:
            raise FixtureValidationError(f"{location}.kind is unsupported")
        if asset_id in ids or role in roles or relative_path in paths:
            raise FixtureValidationError(f"{location} repeats an ID, role, or path")
        ids.add(asset_id)
        roles.add(role)
        paths.add(relative_path)
        counts[kind] += 1

        path = Path(relative_path)
        if (
            path.is_absolute()
            or path.parent != Path("media")
            or path.suffix.lower() != EXTENSION_BY_KIND[kind]
        ):
            raise FixtureValidationError(
                f"{location}.path must be a direct media/{kind} asset"
            )
        digest = _expect_nonempty_string(asset["sha256"], f"{location}.sha256")
        if not SHA256_PATTERN.fullmatch(digest):
            raise FixtureValidationError(f"{location}.sha256 must be lowercase SHA-256")
        _expect_positive_int(asset["sizeBytes"], f"{location}.sizeBytes")
        _validate_provenance(asset["provenance"], f"{location}.provenance")
        _validate_media(asset["media"], kind, f"{location}.media")

    if counts != EXPECTED_KIND_COUNTS:
        raise FixtureValidationError(
            f"descriptor inventory is {counts}, expected {EXPECTED_KIND_COUNTS}"
        )


def descriptor_assets(descriptor: dict[str, Any]) -> list[dict[str, Any]]:
    """Return assets after descriptor validation has established their shape."""
    validate_descriptor(descriptor)
    return cast(list[dict[str, Any]], descriptor["assets"])


def sha256_file(path: Path) -> str:
    """Hash a file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_inventory(descriptor: dict[str, Any], root: Path = FIXTURES_DIR) -> None:
    """Require every and only descriptor-declared file below the media directory."""
    declared = {asset["path"] for asset in descriptor_assets(descriptor)}
    media_root = root / "media"
    actual = {
        path.relative_to(root).as_posix()
        for path in media_root.rglob("*")
        if path.is_file()
    }
    if actual != declared:
        raise FixtureValidationError(
            f"media inventory mismatch; missing={sorted(declared - actual)}, "
            f"undeclared={sorted(actual - declared)}"
        )


def verify_hashes(descriptor: dict[str, Any], root: Path = FIXTURES_DIR) -> None:
    """Verify byte sizes and SHA-256 digests for all declared assets."""
    for asset in descriptor_assets(descriptor):
        path = root / asset["path"]
        try:
            size = path.stat().st_size
        except OSError as error:
            raise FixtureValidationError(f"cannot stat {path}: {error}") from error
        if size != asset["sizeBytes"]:
            raise FixtureValidationError(
                f"{asset['id']} size is {size}, expected {asset['sizeBytes']}"
            )
        actual_hash = sha256_file(path)
        if actual_hash != asset["sha256"]:
            raise FixtureValidationError(
                f"{asset['id']} SHA-256 is {actual_hash}, expected {asset['sha256']}"
            )


def ffprobe_available() -> bool:
    """Return whether FFprobe can be resolved from PATH."""
    return shutil.which("ffprobe") is not None


def probe_asset(path: Path, kind: str) -> dict[str, object]:
    """Return the stable, relevant subset of FFprobe metadata for one asset."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise FixtureValidationError(f"FFprobe failed for {path}: {error}") from error
    parsed = _expect_object(json.loads(result.stdout), f"FFprobe output for {path}")
    streams_value = parsed.get("streams")
    if not isinstance(streams_value, list) or len(streams_value) != 1:
        raise FixtureValidationError(f"{path} must contain exactly one stream")
    stream = _expect_object(streams_value[0], f"FFprobe stream for {path}")
    format_data = _expect_object(parsed.get("format"), f"FFprobe format for {path}")

    common: dict[str, object] = {
        "streamCount": 1,
        "formatName": format_data["format_name"],
        "codecType": stream["codec_type"],
        "codecName": stream["codec_name"],
    }
    if kind == "video":
        common.update(
            {
                "durationSeconds": format_data["duration"],
                "profile": stream["profile"],
                "pixelFormat": stream["pix_fmt"],
                "width": stream["width"],
                "height": stream["height"],
                "frameRate": stream["avg_frame_rate"],
                "timeBase": stream["time_base"],
                "durationTs": int(stream["duration_ts"]),
                "frameCount": int(stream["nb_frames"]),
            }
        )
    elif kind == "still":
        common.update(
            {
                "pixelFormat": stream["pix_fmt"],
                "width": stream["width"],
                "height": stream["height"],
            }
        )
    elif kind == "audio":
        common.update(
            {
                "durationSeconds": format_data["duration"],
                "sampleFormat": stream["sample_fmt"],
                "sampleRateHz": int(stream["sample_rate"]),
                "channels": stream["channels"],
                "channelLayout": stream.get("channel_layout", "unspecified"),
                "timeBase": stream["time_base"],
                "durationTs": int(stream["duration_ts"]),
            }
        )
    else:
        raise FixtureValidationError(f"cannot probe unsupported kind {kind}")
    return common


def verify_media_metadata(
    descriptor: dict[str, Any], root: Path = FIXTURES_DIR
) -> None:
    """Compare relevant FFprobe metadata to every descriptor expectation."""
    if not ffprobe_available():
        raise FixtureValidationError(
            "FFprobe is required for media metadata verification"
        )
    for asset in descriptor_assets(descriptor):
        actual = probe_asset(root / asset["path"], asset["kind"])
        if actual != asset["media"]:
            raise FixtureValidationError(
                f"{asset['id']} media metadata mismatch\n"
                f"actual={json.dumps(actual, sort_keys=True)}\n"
                f"expected={json.dumps(asset['media'], sort_keys=True)}"
            )


def verify_fixture_kit(*, require_ffprobe: bool) -> tuple[dict[str, Any], bool]:
    """Run all fixture validations and report whether FFprobe checks ran."""
    descriptor = load_descriptor()
    validate_descriptor(descriptor)
    verify_inventory(descriptor)
    verify_hashes(descriptor)
    probed = ffprobe_available()
    if probed:
        verify_media_metadata(descriptor)
    elif require_ffprobe:
        raise FixtureValidationError("FFprobe is required but was not found on PATH")
    return descriptor, probed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-ffprobe",
        action="store_true",
        help="fail rather than warn when FFprobe is unavailable",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = _parse_args()
    try:
        descriptor, probed = verify_fixture_kit(require_ffprobe=args.require_ffprobe)
    except FixtureValidationError as error:
        print(f"fixture verification FAILED: {error}", file=sys.stderr)
        return 1
    counts = {kind: 0 for kind in EXPECTED_KIND_COUNTS}
    for asset in descriptor_assets(descriptor):
        counts[asset["kind"]] += 1
    probe_status = (
        "FFprobe metadata verified"
        if probed
        else "FFprobe unavailable; metadata skipped"
    )
    print(
        "fixture verification passed: "
        f"{counts['video']} video clips, {counts['still']} stills, "
        f"{counts['audio']} audio bed; hashes verified; {probe_status}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
