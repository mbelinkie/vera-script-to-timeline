from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypedDict

import pytest
from vera_timeline_agent import resolve_test_queue_reverse as reverse


class _ReverseArguments(TypedDict):
    proof_path: Path
    proof_sha256: str
    pristine_result_path: Path
    pristine_result_sha256: str
    edited_result_path: Path
    edited_result_sha256: str
    fresh_session_path: Path
    fresh_session_sha256: str
    fresh_result_path: Path
    fresh_result_sha256: str


def native_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    target = {
        "projectUid": "fresh-project-uid",
        "timelineUid": "fresh-timeline-uid",
        "projectName": "VERA312 synthetic fresh",
        "timelineName": "VERA312 synthetic fresh",
    }
    items: list[dict[str, Any]] = [
        {
            "itemUid": f"item-{i}",
            "eventId": f"picture-{i:02d}" if i <= 2 else f"event-{i}",
            "sourceId": f"source-{i}",
            "mediaUid": f"media-{i}",
            "kind": "video" if i <= 2 else "audio",
            "trackId": "V1" if i <= 2 else "A1",
            "recordStart": 0 if i == 1 else 327 if i == 2 else 480,
            "recordDuration": 327 if i == 1 else 120 if i == 2 else 60,
            "sourceStart": 0,
            "sourceDuration": 327 if i == 1 else 120 if i == 2 else 60,
            "linkedItemUids": [],
            "online": True,
            "enabled": True,
            "speed": {"numerator": 1, "denominator": 1},
            "sourceMappingSha256": f"source-sha-{i}",
        }
        for i in range(1, 12)
    ]
    geometry: dict[str, Any] = {
        "rate": {"numerator": 24000, "denominator": 1001},
        "extentFrames": 1407,
        "context": {"target": target, "phase": "pristine"},
        "tracks": [{"trackId": f"track-{i}"} for i in range(6)],
        "items": items,
        "sourceMappings": [
            {"sourceId": f"source-{i}", "sha256": f"hash-{i}"} for i in range(1, 12)
        ],
    }
    edited = copy.deepcopy(geometry)
    edited["context"]["phase"] = "edited"
    edited["items"][0]["recordDuration"] += 24
    edited["items"][0]["sourceDuration"] += 24
    edited["items"][1]["recordStart"] += 24
    edited["items"][1]["recordDuration"] -= 24
    edited["items"][1]["sourceDuration"] -= 24
    return geometry, edited


def test_supported_boundary_exact_native_geometry() -> None:
    before, after = native_pair()
    assert reverse.verify_supported_boundary(before, after) == {
        "leftItemUid": "item-1",
        "rightItemUid": "item-2",
        "fromFrame": 327,
        "toFrame": 351,
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b, a: a["items"][0].update(recordDuration=350),
        lambda b, a: a["items"][1].update(recordStart=352),
        lambda b, a: a["items"][1].update(sourceStart=24),
        lambda b, a: a["items"][3].update(recordDuration=61),
        lambda b, a: a["items"][0].update(sourceMappingSha256="changed"),
        lambda b, a: a["items"][1].update(mediaUid="foreign-native-media"),
        lambda b, a: a["sourceMappings"][1].update(sha256="changed-source"),
        lambda b, a: a["context"]["target"].update(timelineUid="wrong"),
        lambda b, a: a.update(rate="24"),
        lambda b, a: a.update(rate="24000/1001"),
        lambda b, a: a["rate"].update(denominator=1000),
        lambda b, a: a["rate"].update(extra=1),
        lambda b, a: a.update(extentFrames=1406),
        lambda b, a: a["items"].pop(),
        lambda b, a: a["items"][1].update(recordDuration=96, sourceDuration=97),
        lambda b, a: a["tracks"].append({"trackId": "extra"}),
    ],
)
def test_supported_boundary_refuses_mutations(
    mutation: Callable[[dict[str, Any], dict[str, Any]], object],
) -> None:
    before, after = native_pair()
    mutation(before, after)
    with pytest.raises(reverse.ReverseRefusal):
        reverse.verify_supported_boundary(before, after)


def test_receipt_gate_checks_real_verifier_and_fresh_rebuild(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    before, after = native_pair()
    context_before, context_after = before["context"], after["context"]
    proof = SimpleNamespace(
        baseline=SimpleNamespace(context=context_before),
        edited=SimpleNamespace(context=context_after),
        accepted_revision=lambda: (
            {"outcome": "accept"},
            {"revision": {"manifestJson": json.dumps({"events": [1, 2]})}},
        ),
    )
    receipts = {
        tmp_path / "pristine.json": {
            "action": "capture_post",
            "status": "complete",
            "context": context_before,
            "target": context_before["target"],
            "nativeGeometry": before,
        },
        tmp_path / "edited.json": {
            "action": "capture_post",
            "status": "complete",
            "context": context_after,
            "target": context_after["target"],
            "nativeGeometry": after,
        },
    }
    fresh_target = {
        **context_before["target"],
        "projectUid": "new-project-uid",
        "timelineUid": "new-timeline-uid",
        "projectName": "VERA Delivery new disposable target",
        "timelineName": "VERA Delivery new disposable target",
    }
    fresh_context = {**context_before, "phase": "rebuild", "target": fresh_target}
    fresh = SimpleNamespace(
        context=fresh_context,
        revised_preflight=(tmp_path / "signed-revision.json", "a" * 64),
        admission=SimpleNamespace(manifest={"events": [1, 2]}),
    )
    receipts[tmp_path / "fresh.json"] = {
        "action": "capture_post",
        "status": "complete",
        "context": fresh_context,
        "target": fresh_target,
        "nativeGeometry": after,
    }
    monkeypatch.setattr(reverse, "QualificationOutputProofV2", lambda *args: proof)
    monkeypatch.setattr(
        reverse, "verify_native_result", lambda path, sha: receipts[path]
    )
    monkeypatch.setattr(reverse, "load_output_session", lambda *args: fresh)
    monkeypatch.setattr(
        reverse,
        "_load_terminal_output_with_comparison",
        lambda controller: (object(), {"status": "compared_consistent"}),
    )
    arguments: _ReverseArguments = {
        "proof_path": tmp_path / "proof.json",
        "proof_sha256": "b" * 64,
        "pristine_result_path": tmp_path / "pristine.json",
        "pristine_result_sha256": "c" * 64,
        "edited_result_path": tmp_path / "edited.json",
        "edited_result_sha256": "d" * 64,
        "fresh_session_path": tmp_path / "fresh-session.json",
        "fresh_session_sha256": "e" * 64,
        "fresh_result_path": tmp_path / "fresh.json",
        "fresh_result_sha256": "f" * 64,
    }
    assert reverse.verify_reverse_receipts(**arguments)["status"] == "verified"
    # No approved revision, absent readback, swapped target or substituted
    # accepted manifest may be converted into native completion.
    proof.accepted_revision = lambda: ({"outcome": "reject"}, {})
    with pytest.raises(reverse.ReverseRefusal, match="accepted revision"):
        reverse.verify_reverse_receipts(**arguments)
    proof.accepted_revision = lambda: (
        {"outcome": "accept"},
        {"revision": {"manifestJson": json.dumps({"events": [1, 2]})}},
    )
    receipts[tmp_path / "edited.json"]["status"] = "uncertain"
    with pytest.raises(reverse.ReverseRefusal, match="complete authenticated"):
        reverse.verify_reverse_receipts(**arguments)
    receipts[tmp_path / "edited.json"]["status"] = "complete"
    fresh.context = {**fresh_context, "target": context_before["target"]}
    with pytest.raises(reverse.ReverseRefusal, match="independent fresh target"):
        reverse.verify_reverse_receipts(**arguments)
    fresh.context = fresh_context
    fresh.revised_preflight = None
    with pytest.raises(reverse.ReverseRefusal, match="signed accepted-revision"):
        reverse.verify_reverse_receipts(**arguments)
    fresh.revised_preflight = (tmp_path / "signed-revision.json", "a" * 64)
    fresh.admission.manifest = {"other": "manifest"}
    with pytest.raises(reverse.ReverseRefusal, match="accepted manifest"):
        reverse.verify_reverse_receipts(**arguments)
    fresh.admission.manifest = {"events": [1, 2]}
    receipts[tmp_path / "fresh.json"]["status"] = "uncertain"
    with pytest.raises(reverse.ReverseRefusal, match="final native capture"):
        reverse.verify_reverse_receipts(**arguments)
    receipts[tmp_path / "fresh.json"]["status"] = "complete"
    monkeypatch.setattr(
        reverse,
        "_load_terminal_output_with_comparison",
        lambda controller: (_ for _ in ()).throw(ValueError("not compared")),
    )
    with pytest.raises(ValueError, match="not compared"):
        reverse.verify_reverse_receipts(**arguments)


def test_cli_refuses_missing_evidence_without_printing_private_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hidden = tmp_path / "private-host-native-evidence.json"
    result = reverse.main(
        [
            "--proof",
            str(hidden),
            "--proof-sha256",
            "a" * 64,
            "--pristine",
            str(hidden),
            "--pristine-sha256",
            "b" * 64,
            "--edited",
            str(hidden),
            "--edited-sha256",
            "c" * 64,
            "--fresh-session",
            str(hidden),
            "--fresh-session-sha256",
            "d" * 64,
            "--fresh-capture",
            str(hidden),
            "--fresh-capture-sha256",
            "e" * 64,
        ]
    )
    assert result == 2
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "status": "blocked",
        "reason": "unverified_reverse_chain",
    }
    assert str(tmp_path) not in output
