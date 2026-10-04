from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from issue144_composition_fixture import decisions, setup
from vera_timeline_agent.roundtrip_build import (
    PreparedBuild,
    ProofBuildError,
    _digest,
    _receipt_bytes,
    load_operator_json,
)


def test_three_edits_one_revision_full_row_audio_fresh_target_and_replay(
    tmp_path: Path,
) -> None:
    session, boundary, provider, _ = setup(tmp_path)
    original_pointer = session.pointer.read_bytes()
    original_inputs = dict(session.build.raw)
    session.run("bind-omission-evidence")
    boundary.edit = True
    proposed = session.run("propose-omission")
    report = load_operator_json(Path(proposed["reportPath"]))
    assert proposed["status"] == "proposed", report
    assert report["schemaVersion"] == "issue-144-composed-proposal/v1"
    inspection = report["compositionInspection"]["result"]
    assert sorted(p["operation"] for p in inspection["visualReport"]["rows"]) == [
        "move",
        "trim",
    ]
    assert len(report["audio"]["omittedTokenIds"]) == 1
    assert len(report["audio"]["expectedAuxiliaryRoutes"]) == 2
    decisions(session, proposed["reportHash"])
    accepted = session.run("decide-omission")
    assert accepted["schemaVersion"] == "issue-144-composed-decision/v1"
    doc = load_operator_json(Path(accepted["revisionRoot"]) / "script-document.json")
    first = next(b for b in doc["activeDraft"]["blocks"] if b["id"] == boundary.row_id)
    assert first["text"] == "Alpha Bravo Delta Echo Foxtrot Golf Hotel"
    assert doc["liveHeadSequence"] == session.build.document["liveHeadSequence"] + 1
    old_row = next(
        b
        for b in session.build.document["activeDraft"]["blocks"]
        if b["id"] == boundary.row_id
    )
    assert first["version"] == old_row["version"] + 1
    assert first["visualEvents"][1]["range"]["quotedText"] == "Echo Foxtrot"
    assert first["visualEvents"][2]["range"]["quotedText"] == "Golf"
    assert (
        doc["activeDraft"]["blocks"][-1]
        == session.build.document["activeDraft"]["blocks"][-1]
    )
    key = accepted["decisionKey"]
    generated = session.run("generate-omission", decision_key=key)
    assert generated["status"] == "finalized", generated
    assert len(provider.requests) == 1
    assert provider.requests[0].text == first["text"]
    revised = PreparedBuild(Path(accepted["revisionRoot"]))
    assert (
        revised.dependencies["narration"][1]
        == session.build.dependencies["narration"][1]
    )
    assert (
        revised.dependencies["narration"][0]["audioHash"]
        != session.build.dependencies["narration"][0]["audioHash"]
    )
    rebuilt = session.run("rebuild", decision_key=key)
    assert rebuilt["status"] == "complete", rebuilt
    manifest = load_operator_json(revised.manifest_path)
    for authored, start, duration in (
        (boundary.row_id, 0, 161),
        (old_row["visualEvents"][0]["id"], 0, 161),
        (boundary.move_id, 63, 47),
        (boundary.trim_id, 110, 25),
    ):
        events = [
            e for e in manifest["events"] if e["provenance"]["authoringId"] == authored
        ]
        assert events and all(
            e["recordRange"] == {"startFrame": start, "durationFrames": duration}
            for e in events
        )
    before = load_operator_json(session.build.manifest_path)
    following = doc["activeDraft"]["blocks"][-1]["id"]
    for old in (e for e in before["events"] if e["provenance"]["blockId"] == following):
        new = next(
            e
            for e in manifest["events"]
            if e["kind"] == old["kind"]
            and e["provenance"]["authoringId"] == old["provenance"]["authoringId"]
        )
        assert (
            new["sourceId"] == old["sourceId"]
            and new["sourceRange"] == old["sourceRange"]
        )
        assert new["recordRange"] == {
            **old["recordRange"],
            "startFrame": old["recordRange"]["startFrame"] - 39,
        }
    assert session.pointer.read_bytes() == original_pointer
    promoted = session.run("promote", decision_key=key)
    assert promoted["status"] == "promoted"
    pointer = session.pointer.read_bytes()
    assert pointer != original_pointer
    assert session.run("decide-omission") == accepted
    assert session.run("generate-omission", decision_key=key) == generated
    assert session.run("rebuild", decision_key=key) == rebuilt
    assert session.run("promote", decision_key=key) == promoted
    assert session.pointer.read_bytes() == pointer
    assert len(provider.requests) == 1 and len(boundary.studios) == 2
    for name, raw in original_inputs.items():
        assert (session.root / name).read_bytes() == raw


def test_composed_rejection_forged_geometry_and_stale_choice_have_no_effects(
    tmp_path: Path,
) -> None:
    session, boundary, provider, _ = setup(tmp_path)
    session.run("bind-omission-evidence")
    boundary.edit = True
    proposed = session.run("propose-omission")
    original = session.pointer.read_bytes()
    report = load_operator_json(Path(proposed["reportPath"]))
    for kind in ("preview", "allowance", "canonical"):
        altered = copy.deepcopy(report)
        if kind == "preview":
            event = altered["compositionInspection"]["result"]["visualManifest"][
                "events"
            ][0]
            event["recordRange"]["startFrame"] += 1
        elif kind == "allowance":
            route = next(iter(altered["audio"]["expectedAuxiliaryRoutes"].values()))
            route["segments"][0]["sourceEnd"] += 1
        else:
            altered["revision"]["result"]["regeneration"]["text"] = (
                "forged canonical text"
            )
        raw = _receipt_bytes(altered)
        digest = _digest(raw)
        (session.root / "reports" / f"{digest[7:]}.json").write_bytes(raw)
        decisions(session, digest)
        with pytest.raises(ProofBuildError, match="rederivation differs"):
            session.run("decide-omission")
    decisions(session, proposed["reportHash"], "reject")
    rejected = session.run("decide-omission")
    assert (
        rejected["status"] == "rejected" and not Path(rejected["revisionRoot"]).exists()
    )
    calls = len(boundary.requests), len(boundary.evidence_calls)
    assert session.run("decide-omission") == rejected
    assert (len(boundary.requests), len(boundary.evidence_calls)) == calls
    decisions(session, proposed["reportHash"])

    def stale(observation: dict[str, Any]) -> None:
        for item in observation["items"]:
            if item["itemUid"].endswith("-tail"):
                item["recordRange"]["startFrame"] += 1

    boundary.change = stale
    with pytest.raises(ProofBuildError, match="observation changed"):
        session.run("decide-omission")
    assert not provider.requests and len(boundary.studios) == 1
    assert session.pointer.read_bytes() == original
