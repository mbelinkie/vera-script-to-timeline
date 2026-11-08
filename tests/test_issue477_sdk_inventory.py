"""Synthetic-only SDK declaration evidence; no native application is involved."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from vera_timeline_agent.issue477_sdk_inventory import MAX_BYTES, inventory, main

OLD = """
class TimelineItem:
    def GetUniqueId(self) -> str: ...
    def GetLeftOffset(self, subframePrecision: bool = False) -> float: ...
    def GetRightOffset(self, subframePrecision: bool = False) -> float: ...
class Timeline:
    def GetStartFrame(self) -> int: ...
"""

NEW = """
class TimelineItem:
    def GetUniqueId(self) -> str: ...
    def GetLeftOffset(self) -> float: ...
    def GetRightOffset(self) -> float: ...
    def SetLeftOffset(self, offset: float, subframePrecision=False,
                      updateLinkedItems=True) -> bool: ...
    def SetRightOffset(self, offset: float, subframePrecision=False,
                       updateLinkedItems=True) -> bool: ...
    def SetPosition(self, position: dict, moveLinkedItems=True) -> bool: ...
    def GetPosition(self) -> dict: ...
class Timeline:
    def MoveItems(self, timelineItems: list, position: dict,
                  moveLinkedItems=True) -> bool: ...
"""


def _stub(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "fake_sdk.pyi"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("version", "source", "state"),
    [
        ("21.1.1.10", OLD, "not_declared_in_supplied_stub"),
        ("21.1.2", NEW, "candidate_unverified"),
        ("21.1.2.10", NEW, "candidate_unverified"),
        ("21.2", NEW, "candidate_unverified"),
        (None, NEW, "unknown"),
        ("21.2", OLD, "unknown"),
        ("21.1.1.10", NEW, "unknown"),
        ("21.1.2", NEW.replace("SetRightOffset", "OtherMethod"), "unknown"),
        ("21.1.2", NEW.replace("timelineItems: list", "items: list"), "unknown"),
        ("21.1.2", NEW.replace("GetUniqueId", "OtherGetter"), "unknown"),
    ],
)
def test_version_and_declarations_never_prove_native_roll(
    tmp_path: Path, version: str | None, source: str, state: str
) -> None:
    path = _stub(tmp_path, source)
    result = inventory(path, version)
    assert result["state"] == state
    assert result["evidenceClass"] == "offline_static_declarations_only"
    assert result["installedBuildVerified"] is False
    assert result["versionLabelSource"] == "caller_supplied_unverified"
    assert result["sameUidRollNativeVerified"] is False
    assert result["mayExecuteNativeEdit"] is False
    assert (
        result["files"]["stub"]["sha256"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )


def test_hashes_and_method_signatures_are_static(tmp_path: Path) -> None:
    stub = _stub(tmp_path, NEW)
    readme = tmp_path / "README.md"
    changelog = tmp_path / "CHANGELOG.md"
    readme.write_text("official? user claims so; not authenticated", encoding="utf-8")
    changelog.write_text("21.2 notes", encoding="utf-8")
    result = inventory(stub, "21.2", readme=readme, changelog=changelog)
    assert set(result["files"]) == {"stub", "readme", "changelog"}
    assert result["files"]["changelog"]["bytes"] == len(changelog.read_bytes())
    left = result["declarations"]["TimelineItem"]["SetLeftOffset"]
    assert left["line"] > 0
    assert "offset: float" in left["signature"]
    assert left["parameters"][:2] == ["self", "offset"]
    assert result["declarations"]["Timeline"]["MoveItems"]["line"] > 0


def test_setter_true_is_not_native_proof(tmp_path: Path) -> None:
    # A simulated success return, even combined with a full set of methods,
    # cannot establish unchanged native clip UIDs, geometry or save/reopen.
    fake_setter_return = True
    result = inventory(_stub(tmp_path, NEW), "21.2")
    assert fake_setter_return
    assert result["state"] == "candidate_unverified"
    assert result["sameUidRollNativeVerified"] is False
    assert result["mayExecuteNativeEdit"] is False


@pytest.mark.parametrize(
    "source",
    [
        "class TimelineItem:\n def Oops(: ...\n",
        "class TimelineItem:\n def GetUniqueId(self): ...\n" * 2,
        OLD + "\nclass Timeline:\n pass\n",
        OLD.replace(
            "class Timeline:\n", "class Timeline:\n    def GetStartFrame(self): ...\n"
        ),
    ],
)
def test_malformed_or_duplicate_class_and_method_rejected(
    tmp_path: Path, source: str
) -> None:
    with pytest.raises(ValueError, match=r"malformed|duplicate"):
        inventory(_stub(tmp_path, source), "21.1.1")


def test_duplicate_methods_rejected_even_when_unlisted(tmp_path: Path) -> None:
    stub = _stub(
        tmp_path,
        OLD.replace(
            "class Timeline:",
            "    def Custom(self): ...\n    def Custom(self): ...\nclass Timeline:",
        ),
    )
    with pytest.raises(ValueError, match="duplicate SDK method"):
        inventory(stub)


def test_symlink_and_symlink_parent_rejected(tmp_path: Path) -> None:
    stub = _stub(tmp_path, NEW)
    alias = tmp_path / "alias.pyi"
    alias.symlink_to(stub)
    with pytest.raises(ValueError, match="symlink"):
        inventory(alias, "21.2")
    directory = tmp_path / "aliasdir"
    directory.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        inventory(directory / stub.name, "21.2")


def test_hardlinked_or_duplicate_document_inputs_rejected(tmp_path: Path) -> None:
    stub = _stub(tmp_path, NEW)
    readme = tmp_path / "README.md"
    readme.write_text("hello", encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    os.link(readme, changelog)
    with pytest.raises(ValueError, match="duplicate SDK input"):
        inventory(stub, "21.2", readme=readme, changelog=changelog)


def test_oversize_and_non_regular_rejected(tmp_path: Path) -> None:
    stub = tmp_path / "fake_sdk.pyi"
    with stub.open("wb") as handle:
        handle.truncate(MAX_BYTES + 1)
    with pytest.raises(ValueError, match="byte limit"):
        inventory(stub)
    with pytest.raises(ValueError, match="regular file"):
        inventory(tmp_path / "missing.pyi")
    directory = tmp_path / "directory.pyi"
    directory.mkdir()
    with pytest.raises(ValueError, match="regular file"):
        inventory(directory)


def test_invalid_encoding_version_and_extension_rejected(tmp_path: Path) -> None:
    stub = tmp_path / "fake_sdk.pyi"
    stub.write_bytes(b"\xff\xfe\xfd")
    with pytest.raises(ValueError, match="UTF-8"):
        inventory(stub)
    _stub(tmp_path, NEW)
    for version in ("21.1.2 (trust me)", "21.1.2.10.2", "v21.2", ""):
        with pytest.raises(ValueError, match="version label"):
            inventory(stub, version)
    wrong = tmp_path / "fake_sdk.py"
    wrong.write_text(NEW, encoding="utf-8")
    with pytest.raises(ValueError, match="extension"):
        inventory(wrong)


def test_comments_docstrings_imports_and_other_classes_do_not_count(
    tmp_path: Path,
) -> None:
    fake = '''"SetLeftOffset SetRightOffset SetPosition MoveItems"
import fictional_vendor_sdk
class TimelineItem:
    """SetLeftOffset(self, offset)"""
    def GetUniqueId(self): ...
class Timeline:
    pass
class Unrelated:
    def SetLeftOffset(self, offset): ...
'''
    result = inventory(_stub(tmp_path, fake), "21.2")
    assert result["state"] == "unknown"
    assert "SetLeftOffset" not in result["declarations"]["TimelineItem"]


def test_weird_annotations_are_never_executed(tmp_path: Path) -> None:
    source = NEW.replace("offset: float", "offset: __import__('os').system('exit 99')")
    result = inventory(_stub(tmp_path, source), "21.2")
    assert result["state"] == "candidate_unverified"
    assert (
        "__import__"
        in result["declarations"]["TimelineItem"]["SetLeftOffset"]["signature"]
    )
    assert result["mayExecuteNativeEdit"] is False


def test_missing_class_or_async_setter_cannot_be_candidate(tmp_path: Path) -> None:
    no_timeline = NEW[: NEW.index("class Timeline:")]
    assert inventory(_stub(tmp_path, no_timeline), "21.2")["state"] == "unknown"
    async_stub = NEW.replace("def SetLeftOffset", "async def SetLeftOffset")
    assert inventory(_stub(tmp_path, async_stub), "21.2")["state"] == "unknown"


def test_offline_cli_prints_json_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _stub(tmp_path, NEW)
    assert main([str(path), "--version-label", "21.1.2"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["state"] == "candidate_unverified"
    assert out["sameUidRollNativeVerified"] is False
    assert out["mayExecuteNativeEdit"] is False
