"""Exercise the local aligner's CLI with generated audio and fake processes."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

import pytest
from vera_word_timing import cli
from vera_word_timing.adapters import local_engines
from vera_word_timing.artifacts import AudioRef, file_hash, schema_errors
from vera_word_timing.fake import FakeRecognizer
from vera_word_timing.ports import ProjectPolicy

_FAKE_ENGINE = """\
import json, os, signal, subprocess, sys, time, wave
from pathlib import Path

root = Path(os.environ["VERA_TEST_JOB"])
engine = Path(sys.argv[1]).name
if engine == "reader":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    with wave.open(str(root / "audio.wav")) as audio:
        audio.readframes(1)
        pending = root / "reader.pending"
        pending.write_text(str(os.getpid()))
        pending.rename(root / "reader.pid")
        time.sleep(60)
    sys.exit()

if engine == "mfa_engine.py":
    (root / "mfa.started").touch()

if engine == os.environ.get("VERA_TEST_HOLD_ENGINE"):
    subprocess.Popen([sys.executable, __file__, "reader"])
    time.sleep(60)
elif engine == "silero_vad_engine.py":
    print(json.dumps({"speechRegions": [[0.1, 0.9]], "durationSec": 2.0}))
elif engine == "mfa_engine.py":
    output = Path(sys.argv[sys.argv.index("--out") + 1])
    output.write_text(json.dumps({
        "words": [{"i": 0, "start": 0.25, "end": 0.5, "status": "aligned"}]
    }))
else:
    sys.exit("unexpected fake engine: " + engine)
"""


@pytest.fixture
def job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    audio_path = tmp_path / "audio.wav"
    with wave.open(str(audio_path), "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 32000)
    audio_ref = AudioRef(audio_path, file_hash(audio_path), 16000, 32000)
    recognition = FakeRecognizer(["hello"], start=0.5).recognise(
        audio_ref, language="en", policy=ProjectPolicy()
    )
    (tmp_path / "recognition.json").write_text(json.dumps(recognition))

    engine = tmp_path / "fake_engine.py"
    engine.write_text(_FAKE_ENGINE)
    tools_python = tmp_path / "tools-python"
    tools_python.write_text(
        f'#!/bin/sh\nexec {shlex.join([sys.executable, str(engine)])} "$@"\n'
    )
    tools_python.chmod(0o755)
    monkeypatch.setenv("VERA_TOOLS_PYTHON", str(tools_python))
    monkeypatch.setenv("VERA_MFA_COMMAND", shlex.join([sys.executable, str(engine)]))
    monkeypatch.setenv("VERA_MFA_HOME", str(tmp_path / "mfa"))
    monkeypatch.setenv("VERA_TEST_JOB", str(tmp_path))
    return tmp_path


def _align(job: Path, *, cancel: bool = True) -> int:
    args = [
        "align",
        "--audio",
        str(job / "audio.wav"),
        "--recognition",
        str(job / "recognition.json"),
        "--out",
        str(job / "alignment.json"),
    ]
    if cancel:
        args += ["--cancel-file", str(job / "cancel")]
    return cli.main(args)


def _refusal(capsys: pytest.CaptureFixture[str], code: str) -> None:
    record = json.loads(capsys.readouterr().out)
    assert schema_errors(record) == []
    assert record["schemaVersion"] == "port-refusal/v1"
    assert record["port"] == "aligner"
    assert record["code"] == code


def test_cancel_before_cli_opens_inputs(
    job: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (job / "cancel").touch()
    # A missing input would otherwise refuse before opening either engine.
    (job / "audio.wav").unlink()
    output = job / "alignment.json"
    output.write_text("existing artifact")

    assert _align(job) == 3
    _refusal(capsys, "cancelled")
    assert output.read_text() == "existing artifact"
    assert not (job / "mfa").exists()


def _wait_for_reader(pid_file: Path) -> int:
    deadline = time.monotonic() + 5
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    return int(pid_file.read_text())


def _ps(pid: int, field: str) -> str:
    return subprocess.run(
        ["ps", "-ww", "-o", f"{field}=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.mark.slow
@pytest.mark.parametrize(
    ("engine", "during_launch", "uncertain"),
    [
        ("silero_vad_engine.py", False, False),
        ("mfa_engine.py", True, False),
        ("mfa_engine.py", True, True),
    ],
)
def test_cancellation_stops_engine_and_resistant_reader(
    job: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    engine: str,
    during_launch: bool,
    uncertain: bool,
) -> None:
    monkeypatch.setenv("VERA_TEST_HOLD_ENGINE", engine)
    monkeypatch.setattr(
        local_engines, "_STOP_GRACE", ((signal.SIGTERM, 0.25), (signal.SIGKILL, 3.0))
    )
    launch = subprocess.Popen
    proc: subprocess.Popen[str] | None = None
    reader: int | None = None
    pid_file = job / "reader.pid"

    def request_cancel() -> None:
        nonlocal reader
        reader = _wait_for_reader(pid_file)
        state = _ps(reader, "state")
        assert state and not state.startswith("Z")
        (job / "cancel").touch()

    def launch_engine(cmd: list[str], **kwargs: Any) -> subprocess.Popen[str]:
        nonlocal proc
        started = launch(cmd, **kwargs)
        if not any(Path(arg).name == engine for arg in cmd):
            return started
        proc = started
        if during_launch:
            request_cancel()
        else:
            communicate = started.communicate

            def cancel_during_wait(*args: Any, **options: Any) -> tuple[str, str]:
                request_cancel()
                return communicate(*args, **options)

            monkeypatch.setattr(started, "communicate", cancel_during_wait)
        return started

    if uncertain:
        stop = local_engines._stop_group

        def lose_confirmation(process: subprocess.Popen[str]) -> bool:
            assert stop(process)
            return False

        monkeypatch.setattr(local_engines, "_stop_group", lose_confirmation)
    monkeypatch.setattr(subprocess, "Popen", launch_engine)

    try:
        assert _align(job) == 3
        _refusal(capsys, "shutdown-unconfirmed" if uncertain else "cancelled")
        assert not (job / "alignment.json").exists()
        assert proc is not None and proc.poll() is not None
        assert reader is not None
        state = _ps(reader, "state")
        assert not state or state.startswith("Z"), (
            f"audio reader is still alive: {state}"
        )
        if engine == "mfa_engine.py":
            with (job / "mfa" / ".vera-mfa.lock").open() as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        if proc is not None and proc.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=3)
        if reader is not None and str(job / "fake_engine.py") in _ps(reader, "command"):
            with contextlib.suppress(ProcessLookupError):
                os.kill(reader, signal.SIGKILL)


def test_cancel_during_mfa_lock_contention_preserves_the_incumbent(
    job: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    home = job / "mfa"
    home.mkdir()
    path = home / ".vera-mfa.lock"
    flock = fcntl.flock

    def cancel_on_contention(fd: Any, operation: int) -> None:
        # Bound the test even if the invocation regresses to a blocking lock.
        assert operation & fcntl.LOCK_NB
        try:
            flock(fd, operation)
        except BlockingIOError:
            (job / "cancel").touch()
            raise

    with path.open("w") as incumbent, path.open("w") as contender:
        flock(incumbent, fcntl.LOCK_EX)
        monkeypatch.setattr(fcntl, "flock", cancel_on_contention)

        assert _align(job) == 3
        _refusal(capsys, "cancelled")
        assert not (job / "mfa.started").exists()
        assert not (job / "alignment.json").exists()
        with pytest.raises(BlockingIOError):
            flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
        flock(incumbent, fcntl.LOCK_UN)
        flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.slow
def test_opt_in_without_request_preserves_normal_alignment(
    job: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _align(job, cancel=False) == 0
    output = job / "alignment.json"
    baseline = output.read_bytes()
    artifact = json.loads(baseline)
    assert schema_errors(artifact) == []
    assert artifact["words"][0]["status"] == "acoustic"

    assert _align(job) == 0
    assert output.read_bytes() == baseline
    assert capsys.readouterr().out == ""
