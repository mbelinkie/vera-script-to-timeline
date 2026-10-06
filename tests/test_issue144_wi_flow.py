from pathlib import Path

from issue144_wi_demo import run_demo


def test_actual_cli_file_wi_composition_generation_and_replay(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "demo")
    assert result["status"] == "complete"
    assert result["evidenceLevel"] == "synthetic_injected"
    assert result["providerRequests"] == 1
    assert result["nativeTargets"] == 2
    assert result["proofLinkCalls"] == 6
    assert result["pictureOnlyRefused"] is True
    assert Path(result["comparisonPath"]).is_file()
