"""Static app-bundle/Mach-O inventory for #479; NEVER runs Resolve or its SDK.

This tool only reads the Info.plist and bounded binary headers of an already
present app. A universal binary is not a vendor support or coexistence claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import stat
import struct
import sys
from pathlib import Path
from typing import Any

DEFAULT_APP = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app")
MAX_PLIST_BYTES = 256 * 1024
MAX_ARCHES = 16
_CPU_NAMES = {0x01000007: "x86_64", 0x0100000C: "arm64", 7: "i386", 12: "arm"}
_FAT_FORMATS = {
    b"\xca\xfe\xba\xbe": (">", 20),
    b"\xbe\xba\xfe\xca": ("<", 20),
    b"\xca\xfe\xba\xbf": (">", 32),
    b"\xbf\xba\xfe\xca": ("<", 32),
}
_THIN_FORMATS = {
    b"\xfe\xed\xfa\xce": ">",
    b"\xce\xfa\xed\xfe": "<",
    b"\xfe\xed\xfa\xcf": ">",
    b"\xcf\xfa\xed\xfe": "<",
}


def _read_prefix(path: Path, maximum: int) -> tuple[bytes, int]:
    """Read a bounded prefix only from a real regular file, without symlinks."""
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("symlink in static inventory path")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("static inventory input is not a regular file")
        data = os.read(fd, maximum)
        return data, metadata.st_size
    finally:
        os.close(fd)


def macho_arches(path: Path) -> list[str]:
    """Inspect a Mach-O header; do not execute, load or hash vendor code."""
    # 8 + MAX_ARCHES * 32 covers the maximum allowed 64-bit fat header.
    data, size = _read_prefix(path, 8 + MAX_ARCHES * 32)
    if len(data) < 8:
        raise ValueError("truncated Mach-O header")
    magic = data[:4]
    if magic in _THIN_FORMATS:
        # Require a full 28/32-byte Mach-O header, not a forged magic+CPU stub.
        expected_header = (
            32 if magic in {b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe"} else 28
        )
        if len(data) < expected_header:
            raise ValueError("truncated thin Mach-O header")
        cpu = struct.unpack_from(f"{_THIN_FORMATS[magic]}I", data, 4)[0]
        return [_CPU_NAMES.get(cpu, f"unknown-0x{cpu:08x}")]
    if magic not in _FAT_FORMATS:
        raise ValueError("not a recognized Mach-O binary")

    endian, entry_size = _FAT_FORMATS[magic]
    count = struct.unpack_from(f"{endian}I", data, 4)[0]
    if count < 1 or count > MAX_ARCHES:
        raise ValueError("invalid Mach-O architecture count")
    header_size = 8 + entry_size * count
    if len(data) < header_size:
        raise ValueError("truncated Mach-O architecture table")
    result: list[str] = []
    for index in range(count):
        offset = 8 + index * entry_size
        cpu = struct.unpack_from(f"{endian}I", data, offset)[0]
        if entry_size == 20:
            slice_offset, slice_size = struct.unpack_from(
                f"{endian}II", data, offset + 8
            )
        else:
            slice_offset, slice_size = struct.unpack_from(
                f"{endian}QQ", data, offset + 8
            )
        if (
            slice_offset < header_size
            or slice_size < 8
            or slice_offset + slice_size > size
        ):
            raise ValueError("invalid Mach-O architecture bounds")
        architecture = _CPU_NAMES.get(cpu, f"unknown-0x{cpu:08x}")
        if architecture in result:
            raise ValueError("duplicate Mach-O CPU architecture")
        result.append(architecture)
    return result


def inventory_app(app: Path = DEFAULT_APP) -> dict[str, Any]:
    """Inventory only static bundle metadata; all effect permissions stay false."""
    if app.suffix != ".app":
        raise ValueError("expected existing .app bundle")
    plist_path = app / "Contents" / "Info.plist"
    data, size = _read_prefix(plist_path, MAX_PLIST_BYTES + 1)
    if size > MAX_PLIST_BYTES:
        raise ValueError("Info.plist byte limit exceeded")
    try:
        info = plistlib.loads(data)
    except (plistlib.InvalidFileException, ValueError, TypeError) as error:
        raise ValueError("malformed Info.plist") from error
    if not isinstance(info, dict):
        raise ValueError("malformed Info.plist dictionary")
    executable = info.get("CFBundleExecutable")
    if not isinstance(executable, str) or not re.fullmatch(
        r"[A-Za-z0-9_+.-]{1,64}", executable
    ):
        raise ValueError("unsafe bundle executable name")
    if executable in {".", ".."}:
        raise ValueError("unsafe bundle executable name")
    result = {
        "evidenceClass": "offline_static_app_bundle_only",
        "appPath": str(app),
        "bundleIdentifier": info.get("CFBundleIdentifier"),
        "shortVersion": info.get("CFBundleShortVersionString"),
        "bundleVersion": info.get("CFBundleVersion"),
        "minimumOS": info.get("LSMinimumSystemVersion"),
        "infoPlistSha256": hashlib.sha256(data).hexdigest(),
        "executableArchitectures": macho_arches(
            app / "Contents" / "MacOS" / executable
        ),
        "liveRuntimeVerified": False,
        "studioEditionVerified": False,
        "vendorSupportVerified": False,
        "independentCoexistenceProven": False,
        "mayInstall": False,
        "mayLaunch": False,
        "mayPromote480": False,
    }
    for key in ("bundleIdentifier", "shortVersion", "bundleVersion", "minimumOS"):
        if result[key] is not None and not isinstance(result[key], str):
            raise ValueError("invalid bundle metadata field")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    args = parser.parse_args(argv)
    try:
        result = inventory_app(args.app)
    except (OSError, ValueError) as error:
        print(f"read-only inventory unavailable: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
