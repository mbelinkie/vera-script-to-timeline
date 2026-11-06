"""Explicitly synthetic command never pretends to produce application evidence."""

import json
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.build_composition_cli import main, simulate
from vera_timeline_agent.build_jobs import BuildJobStore, BuildRequest


@pytest.mark.parametrize("mode", ["free", "studio"])
def test_synthetic_pipeline_runs_all_unskipped_stages_without_external_effects(
    mode: str,
) -> None:
    result = simulate(mode)
    assert result["simulationOnly"] is True
    assert result["actualApplicationEvidence"] is False
    assert result["realProviderCalls"] == 0
    assert result["nativeMutations"] == 0
    assert result["uploadedFiles"] == 0
    assert result["stages"]["verifying_import_package"] == "complete"
    assert result["stages"]["rendering_mp4"] == "skipped"
    assert result["status"] == ("ready_to_import" if mode == "free" else "complete")


def test_local_status_does_not_start_or_change_any_job(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = BuildJobStore(tmp_path / "jobs")
    job = store.submit(BuildRequest("project", "frozen-rev", "submit", "studio"))
    before = store.status("project", job)

    def refuse_writer(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("status attempted to construct a migrating/writable store")

    monkeypatch.setattr(BuildJobStore, "__init__", refuse_writer)
    assert (
        main(
            [
                "status",
                "--store",
                str(tmp_path / "jobs"),
                "--project-id",
                "project",
                "--job-id",
                job,
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["readOnly"] is True
    assert output["job"]["status"] == "queued"
    assert output["job"] == before


def test_status_refuses_missing_store_without_creating_one(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(SystemExit) as error:
        main(["status", "--store", str(missing), "--project-id", "x", "--job-id", "j"])
    assert error.value.code == 2
    assert not missing.exists()
