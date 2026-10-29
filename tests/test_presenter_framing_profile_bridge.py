"""One process-level check of Python calibration -> TS pin -> Python admission."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from vera_timeline_agent.presenter_framing import validate_profile_snapshot


@pytest.mark.slow
def test_captured_values_roundtrip_through_the_actual_typescript_profile_cli() -> None:
    root = Path(__file__).parents[1]
    fixture = root / "packages/contracts/test/fixtures/presenter-framing"
    prior_bytes = (fixture / "profile.json").read_bytes()
    prior = json.loads(prior_bytes)
    captured = {
        "status": "sample_readback_complete",
        "message": "Synthetic captured-value boundary test; not native evidence.",
        "context": prior["context"],
        "observed_transforms": copy.deepcopy(
            {"wide": prior["wide"], "tight": prior["tight"]}
        ),
        "color_limitations": [],
    }
    captured["observed_transforms"]["tight"]["Pan"] = 0.625
    node = shutil.which("node")
    assert node is not None, "The pinned Node runtime is required for this bridge."
    result = subprocess.run(
        [node, str(root / "packages/contracts/src/presenter-framing-profile-cli.ts")],
        input=json.dumps({"calibration": captured, "prior": prior, "id": prior["id"]}),
        text=True,
        capture_output=True,
        check=True,
        timeout=60,
        cwd=root,
    )
    output = json.loads(result.stdout)
    profile = output["profile"]
    pin = {key: profile[key] for key in ("id", "version", "profileHash")}
    verified = validate_profile_snapshot(
        profile,
        canonical_content_json=output["profileContentJson"],
        expected_pin=pin,
    )
    assert verified["tight"]["Pan"] == 0.625
    assert verified["version"] == prior["version"] + 1
    assert verified["profileHash"] != prior["profileHash"]
    assert (fixture / "profile.json").read_bytes() == prior_bytes
