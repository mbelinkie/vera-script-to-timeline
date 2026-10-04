from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from issue144_omission_fixture import FrameProvider, OmissionBoundary, inputs
from vera_timeline_agent.build_jobs import NeedsAction
from vera_timeline_agent.roundtrip_build import (
    ProofBuildError,
    _digest,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.roundtrip_proof import ProofSession


def setup(tmp_path: Path) -> tuple[ProofSession, OmissionBoundary, FrameProvider, str]:
    root = tmp_path / "proof"
    _service, provider, row = inputs(root)
    boundary = OmissionBoundary(row)
    session = ProofSession(
        root,
        native_provider=boundary.native,
        capture=boundary.capture,
        omission_evidence=boundary.evidence,
    )
    assert session.run("build")["status"] == "complete"
    assert session.run("bind-baseline")["status"] == "bound"
    (root / "omission-request.json").write_bytes(
        _receipt_bytes({"schemaVersion": "issue-144-omission-request/v1", "rowId": row})
    )
    return session, boundary, provider, row


def test_prepares_pristine_observed_audio_and_proposes_linked_charlie_omission(
    tmp_path: Path,
) -> None:
    session, boundary, provider, row = setup(tmp_path)
    original = session.pointer.read_bytes()
    prepared = session.run("bind-omission-evidence")
    assert prepared["status"] == "prepared"
    assert session.pointer.read_bytes() == original and not provider.requests
    boundary.edit = True
    proposed = session.run("propose-omission")
    assert proposed["status"] == "proposed", proposed
    report = load_operator_json(Path(proposed["reportPath"]))
    block = session.build.document["activeDraft"]["blocks"][1]
    charlie = next(
        token["id"] for token in block["tokens"] if token["value"] == "Charlie"
    )
    assert report["classification"] == "supported" and report["rowId"] == row
    assert report["audio"]["omittedTokenIds"] == [charlie]
    assert (
        report["beforeText"] == block["text"]
        and report["afterText"] == "Alpha Bravo Delta Echo Foxtrot Golf Hotel"
    )
    assert session.pointer.read_bytes() == original and not provider.requests
    assert session.run("propose-omission")["reportHash"] == proposed["reportHash"]
    assert not (session.root / "decisions").exists()


def test_edited_geometry_cannot_be_backfilled_as_pristine_audio_controls(
    tmp_path: Path,
) -> None:
    session, boundary, provider, _ = setup(tmp_path)
    boundary.edit = True

    # Ask the capture boundary to omit even on preparation to model intervening drift.
    def cut(observation: dict[str, Any]) -> None:
        observation["items"][0]["recordRange"]["startFrame"] += 1

    boundary.change = cut
    with pytest.raises(ProofBuildError):
        session.run("bind-omission-evidence")
    assert not provider.requests


def test_no_omission_preparation_refuses_before_any_evidence_or_provider(
    tmp_path: Path,
) -> None:
    session, boundary, provider, _ = setup(tmp_path)
    boundary.edit = True
    with pytest.raises(ProofBuildError, match=r"pristine.*prepar"):
        session.run("propose-omission")
    assert not boundary.evidence_calls and not provider.requests


@pytest.mark.parametrize(
    "kind",
    ["unknownControl", "source", "link", "extra", "disabled", "speed", "wrongTarget"],
)
def test_omission_capture_uncertainty_refuses_without_acceptance_or_generation(
    tmp_path: Path, kind: str
) -> None:
    session, boundary, provider, _ = setup(tmp_path)
    session.run("bind-omission-evidence")
    boundary.edit = True
    original = session.pointer.read_bytes()

    def corrupt(observation: dict[str, Any]) -> None:
        if kind == "unknownControl":
            observation["audioControls"][0]["controls"] = {
                "qualification": "unobserved"
            }
        if kind == "source":
            observation["items"][0]["sourceHash"] = "sha256:" + "f" * 64
        if kind == "link":
            observation["items"][-1]["linkedUids"] = []
        if kind == "extra":
            observation["items"].append(copy.deepcopy(observation["items"][0]))
        if kind == "disabled":
            observation["items"][-1]["enabled"] = False
        if kind == "speed":
            observation["items"][-1]["speed"] = 99
        if kind == "wrongTarget":
            observation["timelineUid"] = "wrong"

    boundary.change = corrupt
    with pytest.raises(ProofBuildError):
        session.run("propose-omission")
    assert session.pointer.read_bytes() == original and not provider.requests


def test_default_omission_boundary_waits_without_provider_or_native_effect(
    tmp_path: Path,
) -> None:
    session, _boundary, provider, _ = setup(tmp_path)
    session.capture = None
    with pytest.raises(NeedsAction):
        session.run("bind-omission-evidence")
    assert not provider.requests


def test_consistent_stored_preparation_forgery_cannot_supply_pristine_facts(
    tmp_path: Path,
) -> None:
    session, boundary, provider, _ = setup(tmp_path)
    prepared = session.run("bind-omission-evidence")
    preparation = Path(prepared["evidence"]["path"]).parent
    inputs_path = preparation / "inputs.json"
    receipt_path = preparation / "receipt.json"
    inputs_value = load_operator_json(inputs_path)
    # Both reads and the envelope hash agree with the forgery. The independent
    # actual baseline/manifest/native UID check must still reject it.
    for observation in (inputs_value["observationA"], inputs_value["observationB"]):
        for item in observation["items"]:
            if item["linkedUids"] and item["recordRange"]["startFrame"] == 0:
                item["recordRange"]["durationFrames"] -= 1
                item["sourceRange"]["durationFrames"] -= 1
    raw = _receipt_bytes(inputs_value)
    inputs_path.write_bytes(raw)
    receipt = load_operator_json(receipt_path)
    receipt["inputHash"] = _digest(raw)
    receipt_path.write_bytes(_receipt_bytes(receipt))
    original = session.pointer.read_bytes()
    boundary.edit = True
    calls = len(boundary.evidence_calls)
    with pytest.raises(ProofBuildError, match="pristine or untouched native facts"):
        session.run("propose-omission")
    assert len(boundary.evidence_calls) == calls and not provider.requests
    assert session.pointer.read_bytes() == original
