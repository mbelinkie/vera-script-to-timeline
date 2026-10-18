"""The #215 Python/Node bridge over a sanitized synthetic #192 specimen."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
)
from vera_timeline_agent.roundtrip_v2_records import ROOT

NODE_24 = Path(
    "/Users/matthewbelinkie/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/node/bin"
)
OBSERVATION_FIXTURE = ROOT / "packages/contracts/test/issue-215-public-observation.ts"


@pytest.mark.slow
def test_python_public_pure_modes_cross_the_locked_node_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise host request shaping through the real CLI, not native acceptance.

    The #192 document/dependencies and #215 observation are sanitized fixtures.
    Their #214-shaped geometry/comparisons are synthetic; this test explicitly
    bypasses session/currentness/native proof so it verifies only the Python/TS
    protocol, decisions, and compiler output.
    """
    monkeypatch.setenv("PATH", f"{NODE_24}{os.pathsep}{os.environ['PATH']}")
    node = shutil.which("node")
    assert node is not None
    version = subprocess.run(
        [node, "--version"], capture_output=True, check=True, text=True, timeout=10
    ).stdout.strip()
    assert version == "v24.19.0"

    generated = subprocess.run(
        [node, str(OBSERVATION_FIXTURE)],
        capture_output=True,
        check=True,
        text=True,
        timeout=120,
    )
    fixture = json.loads(generated.stdout)
    document = fixture["document"]
    dependencies = fixture["dependencies"]
    evidence = fixture["evidence"]
    inference_decision = fixture["inferenceDecision"]

    # `_pure` is the actual host bridge. These explicit test seams replace the
    # concrete session and native I/O gates, which are outside this protocol test.
    host: Any = object.__new__(proof.QualificationOutputProofV2)
    host.root = tmp_path / "proof"
    host.baseline = SimpleNamespace(
        blobs={
            "executionDocumentSha256": _canonical(document),
            "executionDependenciesSha256": _canonical(dependencies),
        }
    )
    host._current = lambda: None

    baseline = host._pure({"mode": "baseline"})
    assert baseline["documentHash"] == evidence["documentHash"]
    assert baseline["dependenciesHash"] == evidence["dependenciesHash"]

    inference = host._pure({"mode": "infer", "evidence": evidence})
    assert inference["caseKinds"] == ["A"]
    assert inference["commands"]["boundary"] is not None
    assert inference["commands"]["trim"] is None
    assert inference["inferenceHash"] == inference_decision["proposalHash"]

    stage = host._pure(
        {
            "mode": "stage",
            "evidence": evidence,
            "inferenceDecision": inference_decision,
        }
    )
    assert stage["outcome"] == "accept"

    candidate = host._pure(
        {
            "mode": "proposal",
            "evidence": evidence,
            "inferenceDecision": inference_decision,
            "preparedMedia": [],
            "handoff": None,
        }
    )
    assert candidate["schemaVersion"] == "qualification-output-proposal/v1"
    revision = candidate["revision"]
    assert revision["comparisonText"].strip()
    assert revision["manifestJson"]
    assert revision["reportJson"]

    revision_decision = {
        **inference_decision,
        "proposalHash": candidate["proposalHash"],
    }
    decided = host._pure(
        {
            "mode": "decide",
            "evidence": evidence,
            "inferenceDecision": inference_decision,
            "candidate": candidate,
            "decision": revision_decision,
            "history": [],
        }
    )
    assert decided["outcome"] == "accept"
    assert decided["history"] == [candidate["proposalHash"]]
    assert decided["document"] == revision["document"]
    assert decided["dependencies"] == revision["dependencies"]
    for identity in ("buildId", "manifestId", "reportId"):
        assert (
            decided["dependencies"]["build"][identity]
            != dependencies["build"][identity]
        )

    decide_requests = [
        json.loads(path.read_bytes())
        for path in (host.root / "pure").glob("*/request.json")
        if json.loads(path.read_bytes())["mode"] == "decide"
    ]
    assert len(decide_requests) == 1
    request = decide_requests[0]
    assert request["inferenceDecision"] is None
    assert request["preparedMedia"] == candidate["request"]["preparedMedia"]
    assert request["handoff"] == candidate["request"]["handoff"]
    assert request["document"] == document
    assert request["dependencies"] == dependencies

    changed_decision = {**revision_decision, "proposalHash": "sha256:" + "0" * 64}
    with pytest.raises(OutputConsistencyError, match="output proposal refused"):
        host._pure(
            {
                "mode": "decide",
                "evidence": evidence,
                "candidate": candidate,
                "decision": changed_decision,
                "history": [],
            }
        )
