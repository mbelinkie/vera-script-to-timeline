from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

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
    # An unaligned token with a measured onset fails the gate even though the
    # remaining errors are tiny.
    assert report["onset"]["pass"] is True
    assert report["onsetCoverage"] == {"aligned": 1, "total": 2, "complete": False}
    assert report["corpusGatePass"] is False


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
                "text": "one",
                "startMs": 110,
                "endMs": 410,
                "status": "acoustic",
            },
            {
                "tokenIndex": 1,
                "sub": 0,
                "text": "two",
                "startMs": 590,
                "endMs": 900,
                "status": "acoustic",
            },
        ],
    }
    wav = b"RIFF-fake-wav-bytes"
    digest = module.sha256_hash(wav)
    artifact["asset"]["audioHash"] = digest  # type: ignore[index]
    alignment["identity"]["audio"] = {"hash": digest}  # type: ignore[index]
    (tmp_path / "unused.wav").write_bytes(wav)
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


def test_run_mfa_invokes_engine_directly_with_exact_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io
    import subprocess
    import wave

    module = load()
    monkeypatch.delenv("VERA_MFA_COMMAND", raising=False)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(48000)
        writer.writeframes(b"\x00\x00" * 48000)
    artifact = {
        "tokens": [
            {"quotedText": "Hello,"},
            {"quotedText": "well-known"},
            {"quotedText": "--"},
        ]
    }
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen["cmd"] = cmd
        segments = json.loads(Path(cmd[cmd.index("--segments") + 1]).read_text())
        seen["segments"] = segments
        result = {
            "variant": "english_us_arpa",
            "provenance": {"packages": {"montreal-forced-aligner": "3"}},
            "words": [
                {"i": 0, "start": 0.1, "end": 0.4, "status": "aligned"},
                {"i": 1, "sub": 0, "start": 0.5, "end": 0.6, "status": "aligned"},
                {"i": 1, "sub": 1, "start": 0.6, "end": 0.9, "status": "aligned"},
            ],
        }
        Path(cmd[cmd.index("--out") + 1]).write_text(json.dumps(result))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    intervals, provenance = module.run_mfa(artifact, buffer.getvalue())
    cmd = seen["cmd"]
    assert isinstance(cmd, list)
    assert cmd[1:4] == ["run", "-n", "mfa"] and str(module.ENGINE) in cmd
    assert cmd[cmd.index("--variant") + 1] == "english_us_arpa"
    (segment,) = seen["segments"]["segments"]  # type: ignore[index]
    assert segment["end"] == 1.0
    assert [w["text"] for w in segment["words"]] == ["hello", "well", "known"]
    assert intervals == [(100.0, 400.0), (500.0, 900.0), None]
    assert "evaluation-only" in provenance["kind"]


def _bound_case(tmp_path: Path, module: ModuleType) -> list[str]:
    wav = b"measured-audio"
    digest = module.sha256_hash(wav)
    artifact = {
        "asset": {"sampleRate": 48000, "cacheAssetId": "c" * 64, "audioHash": digest},
        "tokens": [
            {
                "tokenId": "t0",
                "quotedText": "one",
                "onsetSamples": 4800,
                "audibleEndSamples": 19200,
            }
        ],
    }
    alignment = {
        "identity": {"aligner": {}, "audio": {"hash": digest}},
        "words": [
            {"tokenIndex": 0, "sub": 0, "text": "one", "startMs": 100, "endMs": 400}
        ],
    }
    (tmp_path / "w.wav").write_bytes(wav)
    (tmp_path / "m.json").write_text(json.dumps(artifact))
    (tmp_path / "a.json").write_text(json.dumps(alignment))
    return [
        "--measurement",
        str(tmp_path / "m.json"),
        "--wav",
        str(tmp_path / "w.wav"),
        "--mfa-result",
        str(tmp_path / "a.json"),
        "--out",
        str(tmp_path / "r.json"),
    ]


def test_inputs_are_bound_to_the_measured_audio(tmp_path: Path) -> None:
    module = load()
    arguments = _bound_case(tmp_path, module)
    assert module.main(arguments) == 0
    # A different WAV is refused.
    (tmp_path / "w.wav").write_bytes(b"some other audio")
    assert module.main(arguments) == 2
    # A recorded MFA result for different audio is refused.
    (tmp_path / "w.wav").write_bytes(b"measured-audio")
    alignment = json.loads((tmp_path / "a.json").read_text())
    alignment["identity"]["audio"]["hash"] = module.sha256_hash(b"elsewhere")
    (tmp_path / "a.json").write_text(json.dumps(alignment))
    assert module.main(arguments) == 2
    # Missing identity is refused too.
    del alignment["identity"]["audio"]
    (tmp_path / "a.json").write_text(json.dumps(alignment))
    assert module.main(arguments) == 2


def test_partially_aligned_hyphenated_token_is_unaligned() -> None:
    module = load()
    artifact = {"tokens": [{"quotedText": "twenty-one"}, {"quotedText": "two"}]}
    engine = {
        "words": [
            {"i": 0, "sub": 0, "start": 0.1, "end": 0.4, "status": "aligned"},
            {"i": 0, "sub": 1, "start": None, "end": None, "status": "failed"},
            {"i": 1, "start": 0.5, "end": 0.9, "status": "aligned"},
        ]
    }
    assert module.intervals_from_engine(engine, artifact) == [None, (500.0, 900.0)]
    # A piece that is simply absent from the result is also unaligned.
    del engine["words"][1]
    assert module.intervals_from_engine(engine, artifact)[0] is None
    recorded = {
        "words": [
            {"tokenIndex": 0, "sub": 0, "text": "twenty", "startMs": 100, "endMs": 400},
            {"tokenIndex": 1, "sub": 0, "text": "two", "startMs": 500, "endMs": 900},
        ]
    }
    assert module.intervals_from_alignment(recorded, artifact) == [
        None,
        (500.0, 900.0),
    ]
    tokens = [token(0, 100, 400), token(1, 500, 900)]
    report = module.compare(tokens, module.intervals_from_alignment(recorded, artifact))
    assert report["onsetCoverage"]["complete"] is False
    assert report["corpusGatePass"] is False


def test_recorded_words_must_match_the_measured_tokens(tmp_path: Path) -> None:
    module = load()
    arguments = _bound_case(tmp_path, module)
    assert module.main(arguments) == 0
    alignment = json.loads((tmp_path / "a.json").read_text())
    mutations: list[Callable[[list[dict[str, Any]]], object]] = [
        lambda w: w[0].update(text="uno"),
        lambda w: w[0].update(tokenIndex=3),
        lambda w: w.append(dict(w[0])),
        lambda w: w[0].pop("text"),
    ]
    for mutate in mutations:
        broken = json.loads(json.dumps(alignment))
        mutate(broken["words"])
        (tmp_path / "a.json").write_text(json.dumps(broken))
        assert module.main(arguments) == 2
