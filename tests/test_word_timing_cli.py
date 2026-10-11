"""The vera-word-timing JSON CLI, driven as an external caller would."""

from __future__ import annotations

import json
import wave
from pathlib import Path
from typing import Any

import pytest
from vera_word_timing.artifacts import schema_errors
from vera_word_timing.cli import REFUSED, main

JSON3 = {
    "events": [
        {
            "tStartMs": 500,
            "dDurationMs": 3000,
            "segs": [
                {"utf8": "kai"},
                {"utf8": " is", "tOffsetMs": 300},
                {"utf8": " three", "tOffsetMs": 500},
            ],
        }
    ]
}


def wav(path: Path, seconds: float = 5.0) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return path


def run(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, Any]]:
    code = main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_recognise_captions_then_reconcile(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    audio = wav(tmp_path / "a.wav")
    caps = tmp_path / "a.json3"
    caps.write_text(json.dumps(JSON3))
    code, rec = run(
        [
            "recognise",
            "--engine",
            "youtube",
            "--audio",
            str(audio),
            "--captions",
            str(caps),
        ],
        capsys,
    )
    assert code == 0 and schema_errors(rec) == []
    assert [t["display"] for t in rec["tokens"]] == ["kai", "is", "three"]
    rec_path = tmp_path / "rec.json"
    rec_path.write_text(json.dumps(rec))
    script, dictionary = tmp_path / "s.txt", tmp_path / "d.dict"
    script.write_text("KAJ [kai] is three.")
    dictionary.write_text("is X\nthree X\n")
    code, rcn = run(
        [
            "reconcile",
            "--recognition",
            str(rec_path),
            "--script",
            str(script),
            "--dictionary",
            str(dictionary),
        ],
        capsys,
    )
    assert code == 0 and schema_errors(rcn) == []
    assert rcn["units"][0]["text"] == "kaj" and rcn["units"][0]["heard"] == "kai"


def test_missing_engine_is_a_refusal_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for var in (
        "VERA_PARAKEET_PYTHON",
        "VERA_PARAKEET_MODEL_GLOB",
        "VERA_TOOLS_PYTHON",
    ):
        monkeypatch.delenv(var, raising=False)
    code, out = run(
        ["recognise", "--engine", "parakeet", "--audio", str(wav(tmp_path / "a.wav"))],
        capsys,
    )
    assert code == REFUSED
    assert (
        out["schemaVersion"] == "port-refusal/v1" and out["code"] == "runtime-missing"
    )
    assert schema_errors(out) == []


def test_cloud_without_consent_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(
        [
            "recognise",
            "--engine",
            "elevenlabs",
            "--audio",
            str(wav(tmp_path / "a.wav")),
        ],
        capsys,
    )
    assert code == REFUSED and out["code"] == "consent-missing"


def test_bad_audio_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "x.wav"
    bad.write_text("not audio")
    code, out = run(
        [
            "recognise",
            "--engine",
            "youtube",
            "--audio",
            str(bad),
            "--captions",
            str(bad),
        ],
        capsys,
    )
    assert code == REFUSED and out["code"] == "input-invalid"


def test_bad_language_and_missing_files_are_sanitised_refusals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    audio = wav(tmp_path / "a.wav")
    caps = tmp_path / "a.json3"
    caps.write_text(json.dumps(JSON3))
    code, out = run(
        [
            "recognise",
            "--engine",
            "youtube",
            "--audio",
            str(audio),
            "--captions",
            str(caps),
            "--language",
            "en-x",
        ],
        capsys,
    )
    assert code == REFUSED and out["code"] == "input-invalid"
    missing = tmp_path / "secret-folder" / "nope.json"
    code, out = run(
        [
            "reconcile",
            "--recognition",
            str(missing),
            "--script",
            str(caps),
            "--dictionary",
            str(caps),
        ],
        capsys,
    )
    assert code == REFUSED and "secret-folder" not in json.dumps(out)
