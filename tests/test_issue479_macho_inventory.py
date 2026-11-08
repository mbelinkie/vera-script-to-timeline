"""All fixtures are fake bytes: no installed Resolve, package or SDK access."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import struct
from pathlib import Path

import pytest
from vera_timeline_agent.issue479_macho_inventory import (
    MAX_ARCHES,
    MAX_PLIST_BYTES,
    inventory_app,
    macho_arches,
    main,
)


def _fat(
    cpus: tuple[int, ...] = (0x01000007, 0x0100000C), *, fat64: bool = False
) -> bytes:
    entry_bytes = 32 if fat64 else 20
    header_len = 8 + len(cpus) * entry_bytes
    header = bytearray(b"\xca\xfe\xba\xbf" if fat64 else b"\xca\xfe\xba\xbe")
    header.extend(struct.pack(">I", len(cpus)))
    for index, cpu in enumerate(cpus):
        start = header_len + 32 * index
        if fat64:
            header.extend(struct.pack(">IIQQII", cpu, 0, start, 16, 0, 0))
        else:
            header.extend(struct.pack(">IIIII", cpu, 0, start, 16, 0))
    header.extend(b"\0" * (32 * len(cpus)))
    return bytes(header)


def _fake_app(tmp_path: Path, executable: bytes | None = None) -> Path:
    app = tmp_path / "Fake Resolve.app"
    (app / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
    (app / "Contents" / "MacOS" / "Resolve").write_bytes(executable or _fat())
    (app / "Contents" / "Info.plist").write_bytes(
        plistlib.dumps(
            {
                "CFBundleIdentifier": "com.blackmagic-design.DaVinciResolve",
                "CFBundleExecutable": "Resolve",
                "CFBundleShortVersionString": "21.1.1",
                "CFBundleVersion": "21.1.10010",
                "LSMinimumSystemVersion": "15.0",
            }
        )
    )
    return app


@pytest.mark.parametrize("fat64", [False, True])
def test_universal_static_binary_is_not_installer_permission(
    tmp_path: Path, fat64: bool
) -> None:
    app = _fake_app(tmp_path, _fat(fat64=fat64))
    result = inventory_app(app)
    assert result["executableArchitectures"] == ["x86_64", "arm64"]
    assert result["shortVersion"] == "21.1.1"
    assert result["bundleVersion"] == "21.1.10010"
    assert (
        result["infoPlistSha256"]
        == hashlib.sha256((app / "Contents" / "Info.plist").read_bytes()).hexdigest()
    )
    assert result["evidenceClass"] == "offline_static_app_bundle_only"
    for permission in (
        "liveRuntimeVerified",
        "studioEditionVerified",
        "vendorSupportVerified",
        "independentCoexistenceProven",
        "mayInstall",
        "mayLaunch",
        "mayPromote480",
    ):
        assert result[permission] is False


def test_thin_x86_and_arm64_are_only_declarations(tmp_path: Path) -> None:
    for magic, cpu, expected in [
        (b"\xcf\xfa\xed\xfe", 0x01000007, "x86_64"),
        (b"\xcf\xfa\xed\xfe", 0x0100000C, "arm64"),
    ]:
        app = _fake_app(tmp_path, magic + struct.pack("<I", cpu) + b"\0" * 8)
        assert macho_arches(app / "Contents" / "MacOS" / "Resolve") == [expected]


@pytest.mark.parametrize(
    "bad_binary",
    [
        b"",
        b"junk",
        b"\0" * 64,
        b"\xca\xfe\xba\xbe" + struct.pack(">I", MAX_ARCHES + 1),
        b"\xca\xfe\xba\xbe" + struct.pack(">I", 0),
        b"\xca\xfe\xba\xbe" + struct.pack(">I", 1),
        _fat((0x01000007, 0x01000007)),
        _fat()[: 8 + 20 * 2 - 1],
    ],
)
def test_bad_or_contradictory_macho_refused(tmp_path: Path, bad_binary: bytes) -> None:
    app = _fake_app(tmp_path, bad_binary if bad_binary else b"x")
    with pytest.raises(ValueError, match=r"Mach-O|architecture"):
        macho_arches(app / "Contents" / "MacOS" / "Resolve")


def test_file_symlink_and_parent_symlink_refused(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    exe = app / "Contents" / "MacOS" / "Resolve"
    link = exe.parent / "alias"
    link.symlink_to(exe)
    with pytest.raises(ValueError, match="symlink"):
        macho_arches(link)
    alias = tmp_path / "Alias.app"
    alias.symlink_to(app, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        inventory_app(alias)


def test_oversize_plist_and_unsafe_executable_refused(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    info = app / "Contents" / "Info.plist"
    info.write_bytes(b"a" * (MAX_PLIST_BYTES + 1))
    with pytest.raises(ValueError, match="byte limit"):
        inventory_app(app)
    info.write_bytes(plistlib.dumps({"CFBundleExecutable": "../../secret"}))
    with pytest.raises(ValueError, match="unsafe"):
        inventory_app(app)


def test_malformed_plist_and_non_regular_binary_refused(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    (app / "Contents" / "Info.plist").write_bytes(b"not plist")
    with pytest.raises(ValueError, match="malformed"):
        inventory_app(app)
    app = _fake_app(tmp_path)
    binary = app / "Contents" / "MacOS" / "Resolve"
    binary.unlink()
    binary.mkdir()
    with pytest.raises(ValueError, match="regular file"):
        inventory_app(app)


def test_cli_outputs_only_read_only_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = _fake_app(tmp_path)
    assert main(["--app", str(app)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["mayPromote480"] is False
    assert data["executableArchitectures"] == ["x86_64", "arm64"]
    assert main(["--app", str(tmp_path / "missing.app")]) == 2
    assert "unavailable" in capsys.readouterr().err


def test_hardlink_to_binary_can_be_read_without_executing(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    original = app / "Contents" / "MacOS" / "Resolve"
    alt = tmp_path / "copy"
    os.link(original, alt)
    assert macho_arches(alt) == ["x86_64", "arm64"]
