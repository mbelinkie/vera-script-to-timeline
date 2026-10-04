from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_issue144_omission_preparation import setup
from vera_timeline_agent.roundtrip_build import (
    ProofBuildError,
    _digest,
    _receipt_bytes,
    load_operator_json,
)


def decisions(root: Path, report_hash: str, choice: str = "accept") -> None:
    (root / "omission-decisions.json").write_bytes(
        _receipt_bytes(
            {
                "schemaVersion": "issue-144-omission-decisions/v1",
                "reportHash": report_hash,
                "choice": choice,
            }
        )
    )


@pytest.mark.parametrize("choice", ["accept", "reject"])
def test_explicit_omission_choice_prepares_only_accepted_canonical_revision(
    tmp_path: Path, choice: str
) -> None:
    session, boundary, provider, row = setup(tmp_path)
    session.run("bind-omission-evidence")
    boundary.edit = True
    proposed = session.run("propose-omission")
    original = session.pointer.read_bytes()
    inputs_before = (session.root / "script-document.json").read_bytes()
    decisions(session.root, proposed["reportHash"], choice)
    result = session.run("decide-omission")
    assert result["status"] == (
        "prepared_revision" if choice == "accept" else "rejected"
    )
    revision_root = Path(result["revisionRoot"])
    if choice == "accept":
        document = load_operator_json(revision_root / "script-document.json")
        changed = next(b for b in document["activeDraft"]["blocks"] if b["id"] == row)
        assert changed["text"] == "Alpha Bravo Delta Echo Foxtrot Golf Hotel"
        assert (
            changed["version"]
            == session.build.document["activeDraft"]["blocks"][1]["version"] + 1
        )
        assert (
            document["activeDraft"]["blocks"][-1]
            == session.build.document["activeDraft"]["blocks"][-1]
        )
        request = load_operator_json(revision_root / "regeneration-request.json")
        assert request["text"] == changed["text"] and request["blockId"] == row
        assert not (revision_root / "compiler-dependencies.json").exists()
        assert not (revision_root / "materialization-plan.json").exists()
    else:
        assert not revision_root.exists()
    calls = len(boundary.requests), len(boundary.evidence_calls)
    assert session.run("decide-omission") == result
    assert (len(boundary.requests), len(boundary.evidence_calls)) == calls
    assert not provider.requests and session.pointer.read_bytes() == original
    assert (session.root / "script-document.json").read_bytes() == inputs_before


def test_malformed_omission_choices_refuse_before_capture_or_generation(
    tmp_path: Path,
) -> None:
    session, boundary, provider, _ = setup(tmp_path)
    session.run("bind-omission-evidence")
    boundary.edit = True
    proposal = session.run("propose-omission")
    valid: dict[str, Any] = {
        "schemaVersion": "issue-144-omission-decisions/v1",
        "reportHash": proposal["reportHash"],
        "choice": "accept",
    }
    variants = [
        {**valid, "choice": "yes"},
        {**valid, "choice": ["accept", "reject"]},
        {**valid, "reportHash": "not-a-hash"},
        {**valid, "extra": True},
        {**valid, "schemaVersion": "unknown"},
        {key: value for key, value in valid.items() if key != "choice"},
    ]
    calls = len(boundary.requests), len(boundary.evidence_calls)
    for value in variants:
        (session.root / "omission-decisions.json").write_bytes(_receipt_bytes(value))
        with pytest.raises(ProofBuildError):
            session.run("decide-omission")
    assert (len(boundary.requests), len(boundary.evidence_calls)) == calls
    assert not provider.requests and not (session.root / "decisions").exists()


@pytest.mark.parametrize("kind", ["classification", "text", "revision", "source"])
def test_consistently_rehashed_omission_report_is_not_decision_authority(
    tmp_path: Path, kind: str
) -> None:
    session, boundary, provider, _ = setup(tmp_path)
    session.run("bind-omission-evidence")
    boundary.edit = True
    proposal = session.run("propose-omission")
    report = load_operator_json(Path(proposal["reportPath"]))
    if kind == "classification":
        report["classification"] = "unsupported"
    elif kind == "text":
        report["afterText"] = "forged accepted text"
    elif kind == "revision":
        report["revision"]["result"]["regeneration"]["text"] = "forged accepted text"
    else:
        report["evidence"]["inputs"]["profile.json"] = "sha256:" + "0" * 64
    raw = _receipt_bytes(report)
    digest = _digest(raw)
    (session.root / "reports" / f"{digest[7:]}.json").write_bytes(raw)
    decisions(session.root, digest)
    original = session.pointer.read_bytes()
    with pytest.raises(ProofBuildError):
        session.run("decide-omission")
    assert not provider.requests and session.pointer.read_bytes() == original
    assert not (session.root / "decisions").exists()


def test_changed_split_geometry_invalidates_choice_before_generation(
    tmp_path: Path,
) -> None:
    session, boundary, provider, _ = setup(tmp_path)
    session.run("bind-omission-evidence")
    boundary.edit = True
    proposal = session.run("propose-omission")
    decisions(session.root, proposal["reportHash"])

    def changed(observation: dict[str, Any]) -> None:
        for item in observation["items"]:
            if item["itemUid"].endswith("-tail"):
                item["recordRange"]["startFrame"] += 1

    boundary.change = changed
    original = session.pointer.read_bytes()
    with pytest.raises(ProofBuildError, match="observation changed"):
        session.run("decide-omission")
    assert not provider.requests and session.pointer.read_bytes() == original
    assert not (session.root / "decisions").exists()


@pytest.mark.parametrize("kind", ["receipt", "script", "request", "evidence"])
def test_retained_omission_choice_rederives_report_and_prepared_artifacts(
    tmp_path: Path, kind: str
) -> None:
    session, boundary, provider, _ = setup(tmp_path)
    session.run("bind-omission-evidence")
    boundary.edit = True
    proposal = session.run("propose-omission")
    decisions(session.root, proposal["reportHash"])
    accepted = session.run("decide-omission")
    directory = session.root / "decisions" / accepted["decisionKey"]
    if kind == "receipt":
        path = directory / "receipt.json"
        value = load_operator_json(path)
        value["status"] = "rejected"
    elif kind == "script":
        path = directory / "build" / "script-document.json"
        value = load_operator_json(path)
        value["liveHeadSequence"] += 1
    elif kind == "request":
        path = directory / "build" / "regeneration-request.json"
        value = load_operator_json(path)
        value["text"] = "different row text"
    else:
        report = load_operator_json(Path(proposal["reportPath"]))
        path = Path(report["evidence"]["path"]) / "render.json"
        value = load_operator_json(path)
        value["jobId"] += "-forged"
    path.write_bytes(_receipt_bytes(value))
    original = session.pointer.read_bytes()
    with pytest.raises(ProofBuildError):
        session.run("decide-omission")
    assert not provider.requests and session.pointer.read_bytes() == original


def test_unqualified_omission_report_cannot_be_accepted(tmp_path: Path) -> None:
    session, _boundary, provider, _ = setup(tmp_path)
    session.run("bind-omission-evidence")
    # A complete unchanged programme has no supported omission.
    proposal = session.run("propose-omission")
    assert proposal["status"] == "refused"
    decisions(session.root, proposal["reportHash"])
    with pytest.raises(ProofBuildError, match="unsupported omission"):
        session.run("decide-omission")
    assert not provider.requests and not (session.root / "decisions").exists()
