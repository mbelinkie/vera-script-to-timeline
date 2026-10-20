"""#215 product plumbing: --narration-evidence reaches the admission entry points."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_controller_v2 as controller
from vera_timeline_agent import qualification_output_package_v2 as package
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent import workflow_v2_cli as cli

TARGET = [
    "--project-uid",
    "project",
    "--timeline-uid",
    "timeline",
    "--project-name",
    "Disposable",
    "--timeline-name",
    "Qualification",
]


def _evidence_args(tmp_path: Path) -> tuple[list[str], dict[str, dict[str, Path]]]:
    args = [
        "--narration-evidence",
        "block-1",
        str(tmp_path / "t1.json"),
        str(tmp_path / "m1.json"),
        "--narration-evidence",
        "block-2",
        str(tmp_path / "t2.json"),
        str(tmp_path / "m2.json"),
    ]
    expected = {
        f"block-{n}": {
            "timing": tmp_path / f"t{n}.json",
            "measurement": tmp_path / f"m{n}.json",
        }
        for n in (1, 2)
    }
    return args, expected


def test_output_prepare_cli_threads_repeatable_narration_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def prepare(_root: Path, **kwargs: Any) -> dict[str, bool]:
        captured.update(kwargs)
        return {"prepared": True}

    monkeypatch.setattr(controller, "prepare_output_session", prepare)
    evidence, expected = _evidence_args(tmp_path)
    argv = ["output-prepare", "--output", str(tmp_path / "s"), "--profile"]
    argv += [package.MATRIX_PROFILE, "--package", str(tmp_path / "p"), *TARGET]
    argv += ["--case-id", "mixed", *evidence]
    assert cli.main(argv) == 0
    assert captured["narration_evidence_paths"] == expected
    captured.clear()
    assert cli.main(argv[: -len(evidence)]) == 0
    assert captured["narration_evidence_paths"] is None


def test_output_revised_cli_threads_narration_evidence_and_refuses_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def prepare(_root: Path, **kwargs: Any) -> dict[str, bool]:
        captured.update(kwargs)
        return {"prepared": True}

    monkeypatch.setattr(proof, "prepare_revised_output_session", prepare)
    evidence, expected = _evidence_args(tmp_path)
    argv = ["output-revised", "--proof-session", str(tmp_path / "ps")]
    argv += ["--proof-sha256", "0" * 64, "--package", str(tmp_path / "p")]
    argv += ["--output", str(tmp_path / "o"), *TARGET, *evidence]
    assert cli.main(argv) == 0
    assert captured["narration_evidence_paths"] == expected
    assert cli._narration_evidence_paths([["b", "t", "m"]]) is not None
    with pytest.raises(ValueError, match="duplicate narration evidence"):
        cli._narration_evidence_paths([["b", "t", "m"], ["b", "t2", "m2"]])


class _Stop(Exception):
    pass


def test_prepare_output_session_forwards_evidence_to_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def admit(_root: Path, **kwargs: Any) -> None:
        seen.update(kwargs)
        raise _Stop

    monkeypatch.setattr(package, "admit_qualification_package_v2", admit)
    _, expected = _evidence_args(tmp_path)
    with pytest.raises(_Stop):
        controller.prepare_output_session(
            tmp_path / "session",
            profile=package.MATRIX_PROFILE,
            target={},
            case_id="c",
            narration_evidence_paths=expected,
        )
    assert seen["narration_evidence_paths"] == expected


def test_prepare_revised_output_session_forwards_evidence_to_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight = tmp_path / "preflight.json"
    preflight.write_bytes(b"{}")
    fake = SimpleNamespace(
        prepare_revised_preflight=lambda: preflight,
        baseline=SimpleNamespace(context={"target": {"timelineUid": "old"}}),
    )
    monkeypatch.setattr(proof, "QualificationOutputProofV2", lambda *_: fake)
    seen: dict[str, Any] = {}

    def admit(_root: Path, **kwargs: Any) -> None:
        seen.update(kwargs)
        raise _Stop

    monkeypatch.setattr(package, "admit_qualification_revision_v2", admit)
    _, expected = _evidence_args(tmp_path)
    with pytest.raises(_Stop):
        proof.prepare_revised_output_session(
            tmp_path / "revised",
            proof_session=tmp_path / "ps",
            proof_sha256="0" * 64,
            package_root=tmp_path / "pkg",
            preparation_paths={},
            target={"timelineUid": "new"},
            narration_evidence_paths=expected,
        )
    assert seen["narration_evidence_paths"] == expected


def test_host_measured_review_pin_binds_the_retained_measurement_bytes() -> None:
    import hashlib

    from vera_timeline_agent import qualification_output_v2 as host
    from vera_timeline_agent.qualification_output_records_v2 import (
        OutputConsistencyError,
    )

    artifact = b'{"measured":true}'
    digest = hashlib.sha256(artifact).hexdigest()
    record = {
        "verification": {
            "method": "measured_audio_boundaries/v1",
            "measurementArtifactHash": "sha256:" + digest,
        }
    }
    host_proof = SimpleNamespace(review=artifact)
    assert host._narration_review_pin(record, host_proof) == "sha256:" + digest
    with pytest.raises(OutputConsistencyError, match="differ from the pinned hash"):
        host._narration_review_pin(record, SimpleNamespace(review=artifact + b" "))
    record["verification"]["method"] = "unknown/v9"
    with pytest.raises(OutputConsistencyError, match="not supported"):
        host._narration_review_pin(record, host_proof)


def test_regenerate_cli_refuses_a_non_campaign_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from vera_timeline_agent import roundtrip_v2_narration as narration

    monkeypatch.delenv(narration.TEST_LEDGER_ENV, raising=False)

    class FakeProof:
        def __init__(self, *_: Any) -> None:
            pass

        def regenerate_row(self, **_: Any) -> None:
            raise AssertionError("must refuse before regenerating")

    monkeypatch.setattr(proof, "QualificationOutputProofV2", FakeProof)
    monkeypatch.setattr(
        narration,
        "production_narration_service",
        lambda *a, **k: SimpleNamespace(),
    )
    argv = ["output-proof-step", "--session", str(tmp_path / "s")]
    argv += ["--session-sha256", "0" * 64, "--action", "regenerate"]
    argv += ["--cache-dir", str(tmp_path / "c"), "--aws-data-policy"]
    argv += ["provider_terms_accepted", "--ledger", str(tmp_path / "ledger.json")]
    assert cli.main(argv) != 0
    assert "approved campaign ledger" in capsys.readouterr().err
