"""#489 static audit regressions use fabricated files only, never vendor binaries."""

from __future__ import annotations

import hashlib
import json
import os
import struct
from pathlib import Path

import pytest
from vera_timeline_agent import issue489_static_resolve_audit as scanner

APP_REL = Path("Contents/MacOS/Resolve")
MCP_REL = Path("Contents/Applications/ResolveMCP")
RES_REL = Path("Contents/Resources/mcp-tools.json")
OLD = b"AddTake\x00FinalizeTake\x00GetSmartReframeStatus\x00"


def test_installed_main_executable_fits_hard_binary_ceiling() -> None:
    """Mac-read-only 21.1.1.10 file size; no real vendor bytes loaded here."""
    assert 1_049_754_864 <= scanner.MAX_FILE_BYTES < 2 * 1024**3
    assert scanner.MAX_FILE_BYTES <= scanner.MAX_TOTAL_BYTES < 2 * 1024**3


def _macho(symbols: bytes) -> bytes:
    # Fake 64-bit little-endian Mach-O header plus inert strings.
    return b"\xcf\xfa\xed\xfe" + struct.pack("<I", 0x01000007) + b"\x00" * 24 + symbols


def _app(tmp_path: Path, binary: bytes | None = None) -> Path:
    app = tmp_path / "Fake Resolve.app"
    destination = app / APP_REL
    destination.parent.mkdir(parents=True)
    destination.write_bytes(_macho(OLD) if binary is None else binary)
    return app


def test_positive_controls_and_all_missing_new_names_are_subset_only(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)
    result = scanner.audit(app, binaries=[APP_REL], version_label="21.1.1.10")
    assert result["scannedSetState"] == "absent"
    assert all(result["positiveControls"].values())
    assert not any(result["binaryMethodNames"].values())
    assert result["impossibleControlAbsent"] is True
    assert result["versionLabelSource"] == "caller_supplied_unverified"
    assert result["files"] == [
        {
            "path": str(APP_REL),
            "role": "binary",
            "format": "Mach-O-magic-only",
            "bytes": (app / APP_REL).stat().st_size,
            "sha256": hashlib.sha256((app / APP_REL).read_bytes()).hexdigest(),
        }
    ]
    for unsafe_claim in (
        "fullAppCoverageVerified",
        "installedBuildVerified",
        "vendorApiSupportVerified",
        "sameUidRollNativeVerified",
        "mayExecuteNativeEdit",
        "mayUnblock473Or312",
    ):
        assert result[unsafe_claim] is False


@pytest.mark.parametrize(
    "extra",
    [
        b"SetLeftOffset",
        b"SetRightOffset",
        b"MoveItems",
        b"SetPosition",
        b"GetPosition",
        b"RollEdit",
        b"RippleTrim",
    ],
)
def test_new_names_present_never_mean_supported_edit(
    tmp_path: Path, extra: bytes
) -> None:
    app = _app(tmp_path, _macho(OLD + extra + b"\0"))
    result = scanner.audit(app, binaries=[APP_REL])
    assert result["scannedSetState"] == "present-but-unsupported"
    assert result["binaryMethodNames"][extra.decode("ascii")] is True
    assert result["vendorApiSupportVerified"] is False
    assert result["mayExecuteNativeEdit"] is False


def test_token_boundary_does_not_match_substrings(tmp_path: Path) -> None:
    app = _app(tmp_path, _macho(OLD + b"NotSetLeftOffsetFake\0MoveItems_Else\0"))
    result = scanner.audit(app, binaries=[APP_REL])
    assert result["scannedSetState"] == "absent"
    assert result["binaryMethodNames"]["SetLeftOffset"] is False
    assert result["binaryMethodNames"]["MoveItems"] is False


def test_missing_positive_control_fails_closed(tmp_path: Path) -> None:
    app = _app(tmp_path, _macho(b"AddTake\0FinalizeTake\0"))
    result = scanner.audit(app, binaries=[APP_REL])
    assert result["scannedSetState"] == "INCONCLUSIVE"
    assert result["positiveControls"]["GetSmartReframeStatus"] is False


def test_impossible_control_overrides_a_plausible_hit(tmp_path: Path) -> None:
    app = _app(
        tmp_path,
        _macho(
            OLD
            + b"SetLeftOffset\0"
            + scanner.IMPOSSIBLE_CONTROL.encode("ascii")
            + b"\0"
        ),
    )
    result = scanner.audit(app, binaries=[APP_REL])
    assert result["scannedSetState"] == "INCONCLUSIVE"
    assert result["impossibleControlAbsent"] is False


def test_unknown_format_is_inconclusive_even_with_controls(tmp_path: Path) -> None:
    app = _app(tmp_path, b"not a Mach-O file\0" + OLD)
    result = scanner.audit(app, binaries=[APP_REL])
    assert result["files"][0]["format"] == "unrecognized"
    assert result["scannedSetState"] == "INCONCLUSIVE"


def test_multiple_binary_files_and_cross_chunk_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path, _macho(b"AddTake\0"))
    helper = app / MCP_REL
    helper.parent.mkdir(parents=True)
    helper.write_bytes(_macho(b"FinalizeTake\0GetSmartReframeStatus\0SetRightOffset\0"))
    monkeypatch.setattr(scanner, "CHUNK_BYTES", 7)
    result = scanner.audit(app, binaries=[MCP_REL, APP_REL])
    assert result["scannedSetState"] == "present-but-unsupported"
    assert all(result["positiveControls"].values())
    assert [entry["path"] for entry in result["files"]] == sorted(
        (str(MCP_REL), str(APP_REL))
    )


def test_token_at_chunk_end_followed_by_identifier_is_not_a_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path, _macho(OLD + b"SetLeftOffset_extended\0"))
    # The probe terminates at an os.read boundary; the next byte is '_'.
    monkeypatch.setattr(scanner, "CHUNK_BYTES", 32 + len(OLD) + len(b"SetLeftOffset"))
    result = scanner.audit(app, binaries=[APP_REL])
    assert result["scannedSetState"] == "absent"
    assert result["binaryMethodNames"]["SetLeftOffset"] is False


def test_mcp_resource_hints_only_and_no_untrusted_values(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)
    resource = app / RES_REL
    resource.parent.mkdir(parents=True)
    resource.write_text(
        json.dumps(
            {
                "tools": [
                    {"name": "timeline_roll_trim", "apiKey": "PRIVATE_DO_NOT_ECHO"},
                    {"name": "preview_video"},
                    {"name": "password_trim_secret"},
                ],
                "example": "SetLeftOffset",
            }
        ),
        encoding="utf-8",
    )
    result = scanner.audit(app, binaries=[APP_REL], resources=[RES_REL])
    assert result["scannedSetState"] == "absent"
    assert result["resourceMethodNames"]["SetLeftOffset"] is True
    assert result["binaryMethodNames"]["SetLeftOffset"] is False
    assert result["candidateMcpEditToolNames"] == ["timeline_roll_trim"]
    assert result["needsIndependentMcpToolReview"] is True
    assert "PRIVATE_DO_NOT_ECHO" not in json.dumps(result)
    assert result["mayExecuteNativeEdit"] is False


def test_built_in_mcp_binary_tool_name_hints_are_not_support_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path)
    helper = app / MCP_REL
    helper.parent.mkdir(parents=True)
    helper.write_bytes(
        _macho(
            b'{"name":"native_clip_roll"}\0'
            b'{"name":"timeline_edit"}\0'
            b'{"name":"password_trim_secret"}\0'
        )
    )
    monkeypatch.setattr(scanner, "CHUNK_BYTES", 11)
    result = scanner.audit(app, binaries=[APP_REL, MCP_REL])
    assert result["candidateMcpEditToolNames"] == ["native_clip_roll", "timeline_edit"]
    assert result["needsIndependentMcpToolReview"] is True
    assert result["scannedSetState"] == "absent"
    assert result["vendorApiSupportVerified"] is False
    assert result["sameUidRollNativeVerified"] is False


def test_no_arbitrary_binary_or_script_is_run(tmp_path: Path) -> None:
    app = _app(tmp_path)
    marker = tmp_path / "side-effect"
    # Exec bit and shebang don't matter: the scanner only opens bytes.
    (app / APP_REL).write_bytes(
        b"#!/bin/sh\n" + f"touch {marker}\n".encode("ascii") + OLD
    )
    (app / APP_REL).chmod(0o755)
    result = scanner.audit(app, binaries=[APP_REL])
    assert result["scannedSetState"] == "INCONCLUSIVE"
    assert not marker.exists()


def test_symlinked_file_parent_and_root_are_rejected(tmp_path: Path) -> None:
    app = _app(tmp_path)
    link = app / "Contents" / "MacOS" / "linked.dylib"
    link.symlink_to(app / APP_REL)
    with pytest.raises(ValueError, match="symlink"):
        scanner.audit(app, binaries=[Path("Contents/MacOS/linked.dylib")])
    alias = app / "Contents" / "aliased"
    alias.symlink_to(app / "Contents" / "MacOS", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        scanner.audit(app, binaries=[Path("Contents/aliased/Resolve")])
    root_link = tmp_path / "Shortcut.app"
    root_link.symlink_to(app, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        scanner.audit(root_link, binaries=[APP_REL])


@pytest.mark.parametrize(
    "path",
    [
        Path("/tmp/somewhere.dylib"),
        Path("../secret"),
        Path("Contents/../../secret"),
        Path("Contents/MacOS/script.py"),
    ],
)
def test_unsafe_paths_and_bad_binary_suffix_rejected(
    tmp_path: Path, path: Path
) -> None:
    app = _app(tmp_path)
    with pytest.raises(ValueError, match=r"candidate|unsafe|binary"):
        scanner.audit(app, binaries=[path])


def test_duplicate_relative_path_and_hardlink_rejected(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with pytest.raises(ValueError, match="duplicate"):
        scanner.audit(app, binaries=[APP_REL, APP_REL])
    hardlink = app / "Contents" / "MacOS" / "Resolve2"
    os.link(app / APP_REL, hardlink)
    with pytest.raises(ValueError, match="identity"):
        scanner.audit(app, binaries=[APP_REL, Path("Contents/MacOS/Resolve2")])


def test_nonregular_fifo_and_directory_are_rejected(tmp_path: Path) -> None:
    app = _app(tmp_path)
    directory = app / "Contents" / "MacOS" / "folder"
    directory.mkdir()
    with pytest.raises(ValueError, match="regular"):
        scanner.audit(app, binaries=[Path("Contents/MacOS/folder")])
    fifo = app / "Contents" / "MacOS" / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="regular"):
        scanner.audit(app, binaries=[Path("Contents/MacOS/fifo")])


def test_file_count_individual_and_aggregate_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path)
    monkeypatch.setattr(scanner, "MAX_FILES", 1)
    with pytest.raises(ValueError, match="file-count"):
        scanner.audit(app, binaries=[APP_REL], resources=[RES_REL])
    monkeypatch.setattr(scanner, "MAX_FILES", 48)
    monkeypatch.setattr(scanner, "MAX_FILE_BYTES", 8)
    with pytest.raises(ValueError, match="byte limit"):
        scanner.audit(app, binaries=[APP_REL])
    monkeypatch.setattr(scanner, "MAX_FILE_BYTES", 1200 * 1024 * 1024)
    monkeypatch.setattr(scanner, "MAX_TOTAL_BYTES", 5)
    with pytest.raises(ValueError, match="aggregate"):
        scanner.audit(app, binaries=[APP_REL])


def test_resource_byte_limit_and_invalid_version(tmp_path: Path) -> None:
    app = _app(tmp_path)
    resource = app / RES_REL
    resource.parent.mkdir(parents=True)
    with resource.open("wb") as handle:
        handle.truncate(scanner.MAX_RESOURCE_BYTES + 1)
    with pytest.raises(ValueError, match="byte limit"):
        scanner.audit(app, binaries=[APP_REL], resources=[RES_REL])
    with pytest.raises(ValueError, match="version"):
        scanner.audit(app, binaries=[APP_REL], version_label="21.1.2 executable")


@pytest.mark.parametrize(
    "resource",
    [
        "Contents/Resources/.env",
        "Contents/Resources/config.json",
        "Contents/Resources/credential-store.json",
    ],
)
def test_private_configuration_resources_refused(tmp_path: Path, resource: str) -> None:
    app = _app(tmp_path)
    with pytest.raises(ValueError, match="private"):
        scanner.audit(app, binaries=[APP_REL], resources=[Path(resource)])


def test_cli_only_emits_static_json_and_cannot_run_native(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = _app(tmp_path)
    assert (
        scanner.main(
            [
                "--app",
                str(app),
                "--binary",
                str(APP_REL),
                "--version-label",
                "21.1.1.10",
            ]
        )
        == 0
    )
    data = json.loads(capsys.readouterr().out)
    assert data["scannedSetState"] == "absent"
    assert data["mayExecuteNativeEdit"] is False
    assert scanner.main(["--app", str(app), "--binary", "../escape"]) == 2
    assert "INCONCLUSIVE" in capsys.readouterr().err
