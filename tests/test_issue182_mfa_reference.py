from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/word-timing/mfa_reference.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mfa_reference", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_percentile_is_nearest_rank() -> None:
    module = load()
    assert module.percentile([], 0.5) is None
    assert module.percentile([10, 20, 30, 40], 0.5) == 20
    assert module.percentile([10, 20, 30, 40], 0.95) == 40


def token(i: int, onset: float, end: float | None) -> dict[str, object]:
    return {
        "tokenId": f"t{i}",
        "quotedText": f"w{i}",
        "onsetMs": onset,
        "audibleEndMs": end,
    }


def test_compare_reports_errors_abstentions_and_the_gate() -> None:
    module = load()
    tokens = [token(0, 100, 400), token(1, 520, None), token(2, 820, 1120)]
    mfa = [(110.0, 380.0), (500.0, 800.0), (900.0, 1100.0)]
    report = module.compare(tokens, mfa)
    assert report["onset"]["count"] == 3
    assert report["onset"]["p50Ms"] == 20
    assert report["onset"]["p95Ms"] == 80
    assert report["audibleEnd"]["count"] == 2  # connected word abstained
    assert report["audibleEndAbstained"] == ["t1"]
    assert report["corpusGatePass"] is True

    far = module.compare([token(0, 100, 400)], [(300.0, 600.0)])
    assert far["onset"]["pass"] is False and far["corpusGatePass"] is False


def test_compare_requires_one_interval_per_token_and_tolerates_unaligned() -> None:
    module = load()
    with pytest.raises(ValueError):
        module.compare([token(0, 1, 2)], [])
    report = module.compare([token(0, 1, 2), token(1, 3, 4)], [None, (3.0, 4.0)])
    assert report["mfaUnaligned"] == ["t0"]


def test_recorded_fixture_round_trip(tmp_path: Path) -> None:
    module = load()
    artifact = {
        "asset": {
            "sampleRate": 48000,
            "durationSamples": 96000,
            "cacheAssetId": "a" * 64,
        },
        "tokens": [
            {
                "tokenId": "t0",
                "quotedText": "one",
                "onsetSamples": 4800,
                "audibleEndSamples": 19200,
            },
            {
                "tokenId": "t1",
                "quotedText": "two",
                "onsetSamples": 28800,
                "audibleEndSamples": None,
            },
        ],
    }
    alignment = {
        "identity": {"aligner": {"id": "montreal-forced-aligner"}},
        "words": [
            {
                "tokenIndex": 0,
                "sub": 0,
                "startMs": 110,
                "endMs": 410,
                "status": "acoustic",
            },
            {
                "tokenIndex": 1,
                "sub": 0,
                "startMs": 590,
                "endMs": 900,
                "status": "acoustic",
            },
        ],
    }
    (tmp_path / "m.json").write_text(json.dumps(artifact))
    (tmp_path / "a.json").write_text(json.dumps(alignment))
    code = module.main(
        [
            "--measurement",
            str(tmp_path / "m.json"),
            "--wav",
            str(tmp_path / "unused.wav"),
            "--mfa-result",
            str(tmp_path / "a.json"),
            "--out",
            str(tmp_path / "r.json"),
        ]
    )
    assert code == 0
    report = json.loads((tmp_path / "r.json").read_text())
    assert report["onset"]["count"] == 2 and report["audibleEnd"]["count"] == 1
