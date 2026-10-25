"""Setup refuses incomplete fixture declarations before creating a target."""

import json
from pathlib import Path

import pytest
from vera_timeline_agent.issue312_package import prepare_package


def test_incomplete_sources_cannot_create_package_or_preparations(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources.json"
    speech = tmp_path / "speech.json"
    sources.write_text(json.dumps({"complete": False}))
    speech.write_text(json.dumps({"rows": []}))
    output = tmp_path / "attempt"
    with pytest.raises(ValueError, match="complete verified source set"):
        prepare_package(sources, speech, output)
    assert not output.exists()


def test_wrong_narration_density_refuses_before_output(tmp_path: Path) -> None:
    sources = tmp_path / "sources.json"
    speech = tmp_path / "speech.json"
    sources.write_text(json.dumps({"complete": True, "plan": {"narrationRows": 6}}))
    speech.write_text(json.dumps({"rows": [{"alternate": False}]}))
    output = tmp_path / "attempt"
    with pytest.raises(ValueError, match="density"):
        prepare_package(sources, speech, output)
    assert not output.exists()
