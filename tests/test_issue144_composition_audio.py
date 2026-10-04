from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from test_issue144_audio_evidence import (
    TARGET,
    _program,
    _receipt,
    _wav,
    _write,
)
from test_issue144_audio_evidence import (
    case as case,
)
from vera_timeline_agent.roundtrip_audio import verify_omission_evidence
from vera_timeline_agent.roundtrip_build import load_operator_json


def test_compiled_auxiliary_geometry_is_separate_from_primary_supports_and_mix(
    case: tuple[Path, str, list[list[float]]],
) -> None:
    root, baseline_hash, samples = case
    current = load_operator_json(root / "observation-a.json")
    current["routes"][1]["segments"][0].update(recordEnd=55, sourceEnd=55)
    current["routes"][2]["segments"][0].update(recordStart=25, sourceStart=25)
    profile = load_operator_json(root / "profile.json")
    # This auxiliary word is actually trimmed. It must never become a primary
    # narration omission or obstruct a separately authorized source trim.
    profile["sources"][1]["supports"] = [
        {"tokenId": "auxiliary-only", "startSample": 65 * 1920, "endSample": 70 * 1920}
    ]
    _write(root, "profile.json", profile)
    _receipt(root, "calibration.json", "baseline.json", "reference.wav")
    for name in ("observation-a.json", "observation-b.json"):
        _write(root, name, current)
    (root / "edited.wav").write_bytes(_wav(_program(samples, current["routes"])))
    _receipt(root, "render.json", "observation-a.json", "edited.wav")
    expected = {r["id"]: copy.deepcopy(r) for r in current["routes"][1:]}

    def verify(allowance: dict[str, Any] | None) -> dict[str, Any]:
        return verify_omission_evidence(
            root,
            baseline_hash=baseline_hash,
            target=TARGET,
            row_id="row-0",
            primary_source_id="source-0",
            evidence_level="synthetic_injected",
            expected_auxiliary_routes=allowance,
        )

    assert verify(None)["status"] == "refused"
    report = verify(expected)
    assert report["status"] == "supported", report
    assert report["omittedTokenIds"] == ["charlie"]
    assert report["expectedAuxiliaryRoutes"] == expected
    assert len(report["channels"]) == 2 and all(
        c["consistent"] for c in report["channels"]
    )
    malformed = [
        {},
        {next(iter(expected)): next(iter(expected.values()))},
        {**expected, "unknown": next(iter(expected.values()))},
        {"audio:1": current["routes"][0], "audio:2": current["routes"][1]},
    ]
    for field, value in (("uid", "forged"), ("recordStart", 1), ("sourceEnd", 56)):
        altered = copy.deepcopy(expected)
        altered["audio:2"]["segments"][0][field] = value
        malformed.append(altered)
    changed_control = copy.deepcopy(expected)
    changed_control["audio:2"]["controls"]["gainDb"] = 1
    malformed.append(changed_control)
    for allowance in malformed:
        assert verify(allowance)["status"] == "refused", allowance
    raw = (root / "edited.wav").read_bytes()
    (root / "edited.wav").write_bytes(_wav([[0.0] * len(samples[0])] * 2))
    _receipt(root, "render.json", "observation-a.json", "edited.wav")
    assert verify(expected)["status"] == "refused"
    (root / "edited.wav").write_bytes(raw)
