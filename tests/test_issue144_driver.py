from __future__ import annotations

import json
from pathlib import Path

from test_issue144_prepared_build import _inputs
from vera_timeline_agent.roundtrip_driver import main
from vera_timeline_agent.roundtrip_wi import file_hash


def test_bad_boundary_hash_does_not_execute_module(tmp_path: Path) -> None:
    root = tmp_path / "proof"
    _inputs(root)
    marker = tmp_path / "executed"
    source = tmp_path / "boundary.py"
    source.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
    )
    result = main(
        [
            "status",
            "--proof-root",
            str(root),
            "--boundary-file",
            str(source),
            "--boundary-sha256",
            "sha256:" + "0" * 64,
        ]
    )
    assert result == 2 and not marker.exists()
    assert not (root / "operator-boundary.json").exists()


def test_pinned_boundary_replay_and_change_refusal(tmp_path: Path) -> None:
    root = tmp_path / "proof"
    _inputs(root)
    source = tmp_path / "boundary.py"
    source.write_text("FILE_PINS = {}\ndef make_boundary(root):\n    return {}\n")
    args = [
        "status",
        "--proof-root",
        str(root),
        "--boundary-file",
        str(source),
        "--boundary-sha256",
        file_hash(source),
    ]
    assert main(args) == 0
    original = (root / "operator-boundary.json").read_bytes()
    assert (
        main(args) == 0 and (root / "operator-boundary.json").read_bytes() == original
    )
    marker = tmp_path / "changed-module-executed"
    source.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
        "FILE_PINS = {}\ndef make_boundary(root):\n    return {'unknown': True}\n"
    )
    args[-1] = file_hash(source)
    assert main(args) == 2
    assert not marker.exists()
    assert (root / "operator-boundary.json").read_bytes() == original


def test_unqualified_real_lane_does_not_become_native_success(tmp_path: Path) -> None:
    root = tmp_path / "proof"
    _inputs(root)
    path = root / "proof-request.json"
    request = json.loads(path.read_text())
    request["evidenceLevel"] = "real_issue145"
    path.write_text(json.dumps(request))
    assert main(["build", "--proof-root", str(root)]) == 2
    assert not (root / "baseline.json").exists()
    assert not list((root / "runs").glob("*/native-intent.json"))
