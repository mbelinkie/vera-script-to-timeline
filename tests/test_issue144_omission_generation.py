from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from issue144_omission_fixture import FrameProvider, OmissionBoundary, inputs
from test_issue144_omission_decisions import decisions
from vera_timeline_agent.build_jobs import NeedsAction
from vera_timeline_agent.narration.service import NarrationService
from vera_timeline_agent.roundtrip_build import (
    PreparedBuild,
    ProofBuildError,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.roundtrip_narration import replace_row_narration
from vera_timeline_agent.roundtrip_proof import ProofSession


def setup(
    tmp_path: Path,
    *,
    choice: str = "accept",
) -> tuple[
    ProofSession, OmissionBoundary, FrameProvider, NarrationService, dict[str, Any]
]:
    root = tmp_path / "proof"
    service, provider, row = inputs(root)
    boundary = OmissionBoundary(row)
    session = ProofSession(
        root,
        native_provider=boundary.native,
        capture=boundary.capture,
        omission_evidence=boundary.evidence,
        narration_service=service,
    )
    assert session.run("build")["status"] == "complete"
    session.run("bind-baseline")
    (root / "omission-request.json").write_bytes(
        _receipt_bytes({"schemaVersion": "issue-144-omission-request/v1", "rowId": row})
    )
    session.run("bind-omission-evidence")
    boundary.edit = True
    proposal = session.run("propose-omission")
    decisions(root, proposal["reportHash"], choice)
    accepted = session.run("decide-omission")
    return session, boundary, provider, service, accepted


def test_accepted_omission_replaces_whole_row_retimes_and_promotes_fresh_target(
    tmp_path: Path,
) -> None:
    session, boundary, provider, _service, accepted = setup(tmp_path)
    key = accepted["decisionKey"]
    original_pointer = session.pointer.read_bytes()
    original_inputs = dict(session.build.raw)
    before = load_operator_json(session.build.manifest_path)
    generated = session.run("generate-omission", decision_key=key)
    assert generated["status"] == "finalized", generated
    assert len(provider.requests) == 1
    assert provider.requests[0].text == "Alpha Bravo Delta Echo Foxtrot Golf Hotel"
    revised = PreparedBuild(Path(accepted["revisionRoot"]))
    assert (
        revised.dependencies["narration"][1]
        == session.build.dependencies["narration"][1]
    )
    assert (
        revised.dependencies["narration"][0]["audioHash"]
        != session.build.dependencies["narration"][0]["audioHash"]
    )
    assert session.run("generate-omission", decision_key=key) == generated
    assert (
        session.pointer.read_bytes() == original_pointer and len(boundary.studios) == 1
    )
    rebuilt = session.run("rebuild", decision_key=key)
    assert rebuilt["status"] == "complete", rebuilt
    after = load_operator_json(revised.manifest_path)
    first = provider.requests[0].block_id
    old_narr = next(
        e
        for e in before["events"]
        if e["kind"] == "audio"
        and e["provenance"]["authoringKind"] == "narration_block"
        and e["provenance"]["blockId"] == first
    )
    new_narr = next(
        e
        for e in after["events"]
        if e["kind"] == "audio"
        and e["provenance"]["authoringKind"] == "narration_block"
        and e["provenance"]["blockId"] == first
    )
    assert old_narr["recordRange"]["durationFrames"] == 200
    assert new_narr["recordRange"]["durationFrames"] == 161
    assert old_narr["sourceId"] != new_narr["sourceId"]
    old_visuals = [
        e
        for e in before["events"]
        if e["kind"] == "video" and e["provenance"]["blockId"] == first
    ]
    for old in old_visuals:
        new = next(
            e
            for e in after["events"]
            if e["kind"] == "video"
            and e["provenance"]["authoringId"] == old["provenance"]["authoringId"]
        )
        assert new["recordRange"] != old["recordRange"]
    following = session.build.document["activeDraft"]["blocks"][-1]["id"]
    for old in [e for e in before["events"] if e["provenance"]["blockId"] == following]:
        new = next(
            e
            for e in after["events"]
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
    assert session.run("rebuild", decision_key=key) == rebuilt
    promoted = session.run("promote", decision_key=key)
    assert promoted["status"] == "promoted"
    pointer = session.pointer.read_bytes()
    assert pointer != original_pointer
    assert session.run("decide-omission") == accepted
    assert session.run("rebuild", decision_key=key) == rebuilt
    assert session.run("promote", decision_key=key) == promoted
    assert session.pointer.read_bytes() == pointer and len(provider.requests) == 1
    assert len(boundary.studios) == 2
    for name, raw in original_inputs.items():
        assert (session.root / name).read_bytes() == raw


def test_missing_service_and_stale_split_refuse_before_new_provider_or_native(
    tmp_path: Path,
) -> None:
    session, boundary, provider, service, accepted = setup(tmp_path)
    key = accepted["decisionKey"]
    original = session.pointer.read_bytes()
    session.narration_service = None
    with pytest.raises(NeedsAction):
        session.run("generate-omission", decision_key=key)
    session.narration_service = service

    def drift(observation: dict[str, Any]) -> None:
        for item in observation["items"]:
            if item["itemUid"].endswith("-tail"):
                item["recordRange"]["startFrame"] += 1

    boundary.change = drift
    with pytest.raises(ProofBuildError, match="observation changed"):
        session.run("generate-omission", decision_key=key)
    assert not provider.requests and len(boundary.studios) == 1
    assert session.pointer.read_bytes() == original


def test_interrupted_handoff_binds_service_before_resume_and_reuses_actual_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import roundtrip_generation as generation

    session, boundary, provider, service, accepted = setup(tmp_path)
    actual = replace_row_narration

    def interrupted(*args: Any, **kwargs: Any) -> Any:
        actual(*args, **kwargs)
        raise RuntimeError("injected crash after service cache, before handoff")

    monkeypatch.setattr(generation, "replace_row_narration", interrupted)
    with pytest.raises(RuntimeError, match="injected crash"):
        session.run("generate-omission", decision_key=accepted["decisionKey"])
    assert len(provider.requests) == 1
    directory = session.root / "decisions" / accepted["decisionKey"]
    assert (directory / "generation-inputs.json").exists()
    assert not (directory / "row-handoff.json").exists()
    config = service.config
    service.config = replace(
        config, profile=replace(config.profile, voice_id="different")
    )
    monkeypatch.setattr(generation, "replace_row_narration", actual)
    with pytest.raises(RuntimeError, match=r"immutable.*different bytes"):
        session.run("generate-omission", decision_key=accepted["decisionKey"])
    assert len(provider.requests) == 1
    service.config = config
    assert (
        session.run("generate-omission", decision_key=accepted["decisionKey"])["status"]
        == "finalized"
    )
    assert len(provider.requests) == 1 and len(boundary.studios) == 1


def test_retained_generation_and_actual_cache_cannot_be_replaced_by_status_claims(
    tmp_path: Path,
) -> None:
    session, boundary, provider, service, accepted = setup(tmp_path)
    key = accepted["decisionKey"]
    session.run("generate-omission", decision_key=key)
    directory = session.root / "decisions" / key
    handoff = load_operator_json(directory / "row-handoff.json")
    replacement = handoff["replacements"][0]
    targets = [
        Path(replacement["assetRecordPath"]),
        Path(replacement["timingPath"]),
        Path(replacement["origin"]),
        directory / "build" / "compiler-dependencies.json",
        directory / "build" / "materialization-plan.json",
        directory / "generation.json",
    ]
    synthesis = service.cache.read(
        "synthesis", replacement["requestHash"][7:], "synthesis.json"
    )
    asset = service.cache.read(
        "assets", f"{replacement['blockId']}/{replacement['assetId']}", "asset.json"
    )
    assert synthesis is not None and asset is not None
    normalized = service.cache.read(
        "normalization",
        asset.metadata["asset"]["normalization_hash"][7:],
        "normalization.json",
    )
    assert normalized is not None
    targets.extend(
        [synthesis.path / "synthesis.json", normalized.path / "normalization.json"]
    )
    original = session.pointer.read_bytes()
    for path in targets:
        raw = path.read_bytes()
        if path == Path(replacement["origin"]):
            altered = bytearray(raw)
            altered[-1] ^= 1
            path.write_bytes(altered)
        else:
            value = load_operator_json(path)
            if path == Path(replacement["assetRecordPath"]):
                value["asset"]["text_hash"] = "sha256:" + "0" * 64
            elif path == Path(replacement["timingPath"]):
                value["marks"][0]["time_ms"] += 40
            elif path.name == "compiler-dependencies.json":
                value["narration"][0]["audioHash"] = session.build.dependencies[
                    "narration"
                ][0]["audioHash"]
            elif path.name == "materialization-plan.json":
                value[next(iter(value))]["origin"] = str(session.root / "unrelated.wav")
            elif path.name == "synthesis.json":
                value["requestIds"] = ["forged-provider-trace"]
            elif path.name == "normalization.json":
                value["paddingSamples"] += 1
            else:
                value["status"] = "complete"
            path.write_bytes(_receipt_bytes(value))
        with pytest.raises(ProofBuildError):
            session.run("rebuild", decision_key=key)
        path.write_bytes(raw)
        assert len(provider.requests) == 1 and len(boundary.studios) == 1
        assert session.pointer.read_bytes() == original


def test_pending_native_resume_and_pointer_publication_recovery_use_same_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import roundtrip_proof as proof

    session, boundary, provider, _service, accepted = setup(tmp_path)
    key = accepted["decisionKey"]
    old = session.pointer.read_bytes()
    session.run("generate-omission", decision_key=key)
    session.native_provider = None
    result = session.run("rebuild", decision_key=key)
    assert result["status"] != "complete" and session.pointer.read_bytes() == old
    assert len(boundary.studios) == 1 and len(provider.requests) == 1
    session.native_provider = boundary.native
    # The durable job's explicit audited resume API is required after waiting;
    # an adapter becoming available does not silently retry a stopped stage.
    pending = PreparedBuild(Path(accepted["revisionRoot"]))
    pending.run()
    assert pending.store is not None
    pending.store.resume(pending.document["projectId"], pending.job_id)
    assert session.run("rebuild", decision_key=key)["status"] == "complete"
    actual = proof._replace_pointer

    def interrupted(path: Path, value: dict[str, Any]) -> None:
        actual(path, value)
        raise RuntimeError("injected stop after pointer publication")

    monkeypatch.setattr(proof, "_replace_pointer", interrupted)
    with pytest.raises(RuntimeError, match="injected stop"):
        session.run("promote", decision_key=key)
    published = session.pointer.read_bytes()
    assert published != old
    monkeypatch.setattr(proof, "_replace_pointer", actual)
    assert session.run("promote", decision_key=key)["status"] == "promoted"
    assert session.pointer.read_bytes() == published
    assert len(boundary.studios) == 2 and len(provider.requests) == 1


def test_generation_binding_link_alias_refuses_before_provider(tmp_path: Path) -> None:
    session, boundary, provider, _service, accepted = setup(tmp_path)
    directory = session.root / "decisions" / accepted["decisionKey"]
    target = directory / "independent.json"
    target.write_bytes(b"{}\n")
    (directory / "generation-inputs.json").symlink_to(target)
    with pytest.raises(ProofBuildError):
        session.run("generate-omission", decision_key=accepted["decisionKey"])
    assert not provider.requests and len(boundary.studios) == 1


def test_rejected_omission_cannot_request_generation_or_rebuild(tmp_path: Path) -> None:
    session, boundary, provider, _service, rejected = setup(tmp_path, choice="reject")
    original = session.pointer.read_bytes()
    assert rejected["status"] == "rejected"
    for action in ("generate-omission", "rebuild"):
        with pytest.raises(ProofBuildError, match="explicitly accepted omission"):
            session.run(action, decision_key=rejected["decisionKey"])
    assert session.pointer.read_bytes() == original and not provider.requests
    assert len(boundary.studios) == 1
