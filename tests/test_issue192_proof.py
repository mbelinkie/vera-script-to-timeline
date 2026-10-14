"""New integration checks; real runtime/provider/human gates remain elsewhere."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from issue190_case import pin
from issue192_case import boundary_case, target
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.roundtrip_v2_build import R16_INPUTS
from vera_timeline_agent.roundtrip_v2_proof import ProofSessionV2
from vera_timeline_agent.roundtrip_v2_records import (
    ProofNativeError,
    publish_immutable_output,
)

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def packages(tmp_path_factory: Any) -> Any:
    root = tmp_path_factory.mktemp("issue192-new-seams")
    old = boundary_case(root / "prior", root / "prior-native")
    fresh = boundary_case(root / "fresh", root / "fresh-native", revision=True)
    return root, old, fresh


def session(packages: Any, root: Path) -> ProofSessionV2:
    _, old, _ = packages
    build, boundary, _, _ = old
    return ProofSessionV2(
        root,
        baseline=build,
        boundary=boundary,
        authenticate=lambda *_: None,
        authority=b"fake test authority only",
    )


def test_public_capture_and_host_baseline_actual_compiler_binding(
    packages: Any,
    tmp_path: Path,
) -> None:
    _, old, _ = packages
    _, boundary, resolve, _ = old
    proof = session(packages, tmp_path / "session")
    packet = proof.capture(
        target(resolve), resolve.project.timeline.mapping, "issue192_baseline"
    )
    raw = json.loads(packet["rawJson"])
    assert raw["timeline"] == proof.manifest["timeline"]
    assert (
        json.loads(packet["receiptJson"])["rawHash"]
        == pin(boundary.root / "observations/issue192_baseline.json")["sha256"]
    )
    assert "100.0" in packet["rawJson"]  # Python spelling must survive the bridge.
    assert raw["deliveryLineage"]["kind"] == "externally_supplied_target"


def test_consumption_rechecks_actual_adjacent_facts_before_pure_or_effect(
    packages: Any,
    tmp_path: Path,
) -> None:
    _, old, _ = packages
    _, _, resolve, adapter = old
    proof = session(packages, tmp_path / "session")
    packet = proof.capture(
        target(resolve), resolve.project.timeline.mapping, "issue192_current"
    )
    # Transport-only guard fixture; the genuine public test authenticates cases.
    evidence = {
        "current": packet,
        "bindingJson": proof.binding_pin
        and Path(proof.binding_pin["path"]).read_text(),
    }
    key = identity_hash(evidence)
    path = proof.root / "transport-currentness.json"
    publish_immutable_output(path, canonical_json_bytes(evidence))
    proof.authenticated_evidence[key] = proof._remember("transport-case", path, key)
    proof._observations_current(evidence)
    other = session(packages, tmp_path / "second-session")
    other.capture(target(resolve), resolve.project.timeline.mapping, "second_current")
    other_path = other.root / "transport-currentness.json"
    publish_immutable_output(other_path, canonical_json_bytes(evidence))
    other.authenticated_evidence[key] = other._remember(
        "transport-case", other_path, key
    )
    other._observations_current(evidence)
    calls = list(adapter.calls)
    resolve.project.timeline.markers = {"unexpected": {"name": "changed"}}
    try:
        with pytest.raises(ProofNativeError, match="changed before"):
            proof._observations_current(evidence)
    finally:
        resolve.project.timeline.markers = {}
    assert adapter.calls == calls


def test_early_reject_never_requests_stage_provider_or_build(
    packages: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proof = session(packages, tmp_path / "session")
    inferred = {"synthetic": "pure inference double for rejection seam only"}
    calls: list[str] = []

    def pure(mode: str, **_: Any) -> Any:
        calls.append(mode)
        assert mode == "infer", "rejection must never request a staged replacement"
        return inferred

    monkeypatch.setattr(proof, "_pure", pure)
    monkeypatch.setattr(proof, "_observations_current", lambda _: None)
    decision = {
        "schemaVersion": "issue-192-v2-inference-decision/v1",
        "inferenceHash": identity_hash(inferred),
        "outcome": "reject",
    }
    before = canonical_json_bytes(proof.baseline.document)
    result = proof.stage({}, decision, prepared_media=[])
    assert calls == ["infer"]
    assert result["outcome"] == "reject"
    assert result["providerEffects"] == result["nativeEffects"] == 0
    assert canonical_json_bytes(result["document"]) == before
    with pytest.raises(ProofNativeError, match="changed or rejected"):
        proof.proposal({}, prepared_media=[], handoff=None)


def accept_seam_double(proof: ProofSessionV2, fresh: Any) -> dict[str, Any]:
    # This is an explicit fake pure-result input for the fresh-package seam,
    # never advertised as A/B/C inference, provider truth or native acceptance.
    build, boundary, _, _ = fresh
    result = {
        "outcome": "accept",
        "document": build.document,
        "dependencies": build.dependencies,
        "history": [],
        "decisionHash": identity_hash({"fake": True}),
    }
    raw = canonical_json_bytes(result)
    path = proof.root / "revision-result.json"
    publish_immutable_output(path, raw)
    proof._remember("revision-result", path, identity_hash(result))
    proposal = {
        "document": build.document,
        "dependencies": build.dependencies,
        "manifestJson": build.manifest_path.read_text(),
        "reportJson": build.report_path.read_text(),
    }
    assert json.loads(proposal["manifestJson"]) == boundary.package.manifest
    # Only these isolated transport/readback unit checks substitute the accepted
    # revision port. They are excluded from the combined AC evidence; the new
    # public-path test obtains it through actual inference/decision/service APIs.
    vars(proof)["accepted_revision"] = lambda: (result, {"proposal": proposal}, {})
    return {"proposal": proposal}


def test_fresh_package_public_delivery_save_reopen_and_readonly_recovery(
    packages: Any,
    tmp_path: Path,
) -> None:
    _, old, fresh = packages
    proof = session(packages, tmp_path / "session")
    old_build, _, old_resolve, old_adapter = old
    new_build, boundary, resolve, adapter = fresh
    prior_inputs = {key: p["sha256"] for key, p in old_build.inputs.items()}
    prior_target = target(old_resolve)
    prior_calls = list(old_adapter.calls)
    candidate = accept_seam_double(proof, fresh)
    package = proof.prepare_rebuild(candidate, new_build)
    assert package["attestationHash"] == boundary.attestation_hash
    delivered = proof.request_fresh_delivery(new_build, boundary)
    assert delivered["status"] == "verified"
    assert adapter.calls.count("create_project") == 1
    assert adapter.calls.count("save_close_reopen") == 1
    reopened = proof.verify_reopened(
        boundary, target(resolve), resolve.project.timeline.mapping, "issue192_reopened"
    )
    assert reopened["status"] == "verified"
    assert reopened["evidenceLevel"] == "injected_execution_unqualified"
    assert proof.recover_delivery(boundary)["nativeEffects"] == 0
    calls = list(adapter.calls)
    with pytest.raises(ProofNativeError, match="read-only recovery"):
        proof.request_fresh_delivery(new_build, boundary)
    assert adapter.calls == calls
    assert old_adapter.calls == prior_calls
    assert target(old_resolve) == prior_target
    assert {
        key: pin(Path(p["path"]))["sha256"] for key, p in old_build.inputs.items()
    } == prior_inputs


@pytest.mark.parametrize(
    "attack",
    ["record", "source", "target", "disabled", "control", "links"],
)
def test_reopened_discrepancy_refuses_without_more_delivery(
    packages: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
) -> None:
    # Each attack gets independent evidence/Resolve objects over unchanged package.
    _, _, fresh = packages
    new_build, original, _, _ = fresh
    from issue190_native_fixture import FakeResolve, fake_controls
    from test_workflow_v2 import _FakeAdapter
    from vera_timeline_agent.roundtrip_v2_native import NativeProofBoundaryV2

    resolve = FakeResolve(original.package)
    adapter = _FakeAdapter()
    boundary = NativeProofBoundaryV2(
        resolve,
        attestation_path=original.attestation_path,
        attestation_hash=original.attestation_hash,
        proof_package_path=original.proof_path,
        proof_package_hash=original.binding["proofPackageHash"],
        evidence_root=tmp_path / "fresh-native",
        authenticate=lambda *_: None,
        authority=b"fake",
        code_hashes=original.code_hashes,
        read_controls=fake_controls,
        adapter_factory=lambda _: adapter,
    )
    proof = session(packages, tmp_path / "session")
    candidate = accept_seam_double(proof, (new_build, boundary, resolve, adapter))
    proof.prepare_rebuild(candidate, new_build)
    assert proof.request_fresh_delivery(new_build, boundary)["verified"]
    expected_target = target(resolve)
    item = next(iter(resolve.project.timeline.items.values()))[0]
    if attack == "record":
        item.start += 1
    elif attack == "source":
        item.source_start += 1
    elif attack == "target":
        resolve.project.timeline.uid += ":drift"
    elif attack == "disabled":
        item.enabled = False
    elif attack == "control":
        monkeypatch.setattr(boundary, "read_controls", lambda *_: {"unknown": True})
    else:
        peers = [i for group in resolve.project.timeline.items.values() for i in group]
        peers[0].links = [peers[-1]]
        peers[-1].links = [peers[0]]
    calls = list(adapter.calls)
    with pytest.raises(ProofNativeError):
        proof.verify_reopened(
            boundary, expected_target, resolve.project.timeline.mapping, "mismatch"
        )
    assert adapter.calls == calls


@pytest.mark.parametrize("attack", ["gain", "channels"])
def test_reopened_audio_view_rejects_gain_and_channel_drift(
    tmp_path: Path, attack: str
) -> None:
    from issue192_public_case import FakeAuthority, MaterializedCase

    case = MaterializedCase(tmp_path / "audio-case", FakeAuthority())
    boundary, resolve, adapter = case.native(tmp_path / "audio-native")
    receipt = boundary.capture(
        target(resolve), resolve.project.timeline.mapping, "audio_view"
    )
    raw_path = boundary.root / "observations/audio_view.json"
    assert pin(raw_path)["sha256"] == receipt["rawHash"]
    observed = json.loads(raw_path.read_bytes())
    ProofSessionV2._verify_exact_view(observed, boundary)
    narration = next(
        item
        for item in observed["items"]
        if item["authoredEvent"]["kind"] == "narration"
    )
    route = next(
        r["controls"]
        for r in observed["controls"]["routes"]
        if r["itemUid"] == narration["itemUid"]
    )
    assert route["gainDb"] == 0
    assert route["channelMap"] == "mono-dual"
    if attack == "gain":
        route["gainDb"] = -18
    else:
        route["channelMap"] = "stereo-direct"
    with pytest.raises(ProofNativeError, match="audio gain/channel mapping differs"):
        ProofSessionV2._verify_exact_view(observed, boundary)
    assert adapter.calls == []


def test_revised_real_lane_and_changed_accepted_input_refuse_before_effect(
    packages: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, fresh = packages
    proof = session(packages, tmp_path / "session")
    build, boundary, _, adapter = fresh
    candidate = accept_seam_double(proof, fresh)
    request = copy.deepcopy(proof.baseline.request)
    request["lane"] = "r16_private"
    monkeypatch.setattr(proof.baseline, "request", request)
    calls = list(adapter.calls)
    with pytest.raises(ProofNativeError, match="real revised consumer"):
        proof.prepare_rebuild(candidate, build)
    assert adapter.calls == calls
    assert boundary.recover_delivery()["nativeEffects"] == 0
    request["lane"] = "synthetic_local"
    monkeypatch.setattr(proof.baseline, "original", R16_INPUTS)
    with pytest.raises(ProofNativeError, match="real revised consumer"):
        proof.prepare_rebuild(candidate, build)
    assert adapter.calls == calls
