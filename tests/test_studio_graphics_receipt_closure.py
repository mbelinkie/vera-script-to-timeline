"""The approved compiler integration must close both Python source inventories."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import vera_timeline_agent.roundtrip_build as build
import vera_timeline_agent.roundtrip_proof as proof

IDENTITY = build.ROOT / "packages/contracts/src/ev24-identity.ts"
DOCUMENT = build.ROOT / "tests/data/slice_1_1/minimal.script-document.json"


@pytest.fixture
def semantic_session() -> proof.ProofSession:
    # Isolate the real receipt boundary from unrelated media/native setup.
    session = object.__new__(proof.ProofSession)
    session.build = cast(
        build.PreparedBuild, SimpleNamespace(node="node", _assert_current=lambda: None)
    )
    return session


def test_actual_semantic_receipt_binds_ev24_identity(
    semantic_session: proof.ProofSession,
) -> None:
    receipt = semantic_session._semantic("inspect-script", [DOCUMENT])
    assert receipt["result"]["status"] == "inspected"
    assert receipt["sourceHashes"]["./ev24-identity.ts"] == build._file_hash(IDENTITY)


@pytest.mark.parametrize("tamper", ["missing", "altered"])
def test_semantic_receipt_rejects_unbound_ev24_identity(
    semantic_session: proof.ProofSession,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    run = subprocess.run

    def changed_receipt(*args: Any, **kwargs: Any) -> Any:
        result = run(*args, **kwargs)
        assert result.returncode == 0, result.stderr
        receipt = json.loads(result.stdout)
        if tamper == "missing":
            del receipt["sourceHashes"]["./ev24-identity.ts"]
        else:
            receipt["sourceHashes"]["./ev24-identity.ts"] = "sha256:" + "0" * 64
        result.stdout = json.dumps(receipt).encode()
        return result

    monkeypatch.setattr(subprocess, "run", changed_receipt)
    with pytest.raises(build.ProofBuildError, match="receipt binding differs"):
        semantic_session._semantic("inspect-script", [DOCUMENT])


def test_prepared_build_invalidates_when_ev24_identity_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = object.__new__(build.PreparedBuild)
    prepared.root = tmp_path
    prepared.run_root = tmp_path / "run"
    prepared.input_hashes = {}
    prepared.source_hashes = prepared._code_hashes()
    assert prepared.source_hashes[IDENTITY.relative_to(build.ROOT).as_posix()] == (
        build._file_hash(IDENTITY)
    )
    prepared._assert_current()
    file_hash = build._file_hash
    monkeypatch.setattr(
        build,
        "_file_hash",
        lambda path: "sha256:" + "0" * 64 if path == IDENTITY else file_hash(path),
    )
    with pytest.raises(build.ProofBuildError, match="proof source or lockfile changed"):
        prepared._assert_current()
