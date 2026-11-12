"""Unit coverage for the two-case timeline speed check wrapper."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_timeline_speed.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_timeline_speed", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_output(
    *, duration: str = "30.000", total: str = "20.00", elapsed: str = "0.40"
) -> str:
    return (
        "preflight: PASS (0.02s)\n"
        f"Resolve step + check: PASS ({elapsed}s)\n"
        f"PASS: 900 frames ({duration}s timeline); total {total}s\n"
    )


def cli_args(output: Path) -> list[str]:
    return [
        "check_timeline_speed.py",
        "--short-script",
        "short.json",
        "--short-inputs",
        "short-inputs.json",
        "--long-script",
        "long.json",
        "--long-inputs",
        "long-inputs.json",
        "--output",
        str(output),
    ]


def test_main_invokes_build_cli_for_both_cases_and_prints_stages_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load()
    output = tmp_path / "run"
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, build_output())

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", cli_args(output))

    assert module.main() == 0

    assert len(calls) == 2
    for (command, kwargs), case in zip(calls, ("short", "long"), strict=True):
        assert command[:3] == [
            sys.executable,
            "-m",
            "vera_timeline_agent.build_timeline_cli",
        ]
        assert command[command.index("--script") + 1] == f"{case}.json"
        assert command[command.index("--inputs") + 1] == f"{case}-inputs.json"
        assert command[command.index("--output") + 1] == str(output / case)
        assert kwargs == {
            "text": True,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
        }

    printed = capsys.readouterr().out
    assert "preflight: PASS (0.02s)" in printed
    assert "Resolve step + check: PASS (0.40s)" in printed
    assert (
        "| Case | Timeline (s) | Resolve + check (s) | Total (s) | Result |" in printed
    )
    assert "| short | 30.000 | 0.40 | 20.00 | PASS |" in printed
    assert "| long | 30.000 | 0.40 | 20.00 | PASS |" in printed


def test_main_stops_after_a_failed_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load()
    calls: list[list[str]] = []

    def failed_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, "Resolve import: FAIL (0.10s)\n")

    monkeypatch.setattr(module.subprocess, "run", failed_run)
    monkeypatch.setattr(sys, "argv", cli_args(tmp_path / "run"))

    assert module.main() == 1
    assert len(calls) == 1
    assert calls[0][calls[0].index("--script") + 1] == "short.json"


def test_main_runs_long_case_after_short_misses_speed_bar_and_exits_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load()
    calls: list[list[str]] = []

    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        output = (
            build_output(duration="10.000", total="10.50")
            if command[command.index("--script") + 1] == "short.json"
            else build_output()
        )
        return subprocess.CompletedProcess(command, 0, output)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", cli_args(tmp_path / "run"))

    assert module.main() == 1
    assert [call[call.index("--script") + 1] for call in calls] == [
        "short.json",
        "long.json",
    ]

    printed = capsys.readouterr().out
    assert "| short | 10.000 | 0.40 | 10.50 | FAIL |" in printed
    assert "| long | 30.000 | 0.40 | 20.00 | PASS |" in printed


def test_main_stops_after_an_unverifiable_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load()
    calls: list[list[str]] = []

    def unverifiable_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command, 0, "Resolve step + check: PASS (0.40s)\n"
        )

    monkeypatch.setattr(module.subprocess, "run", unverifiable_run)
    monkeypatch.setattr(sys, "argv", cli_args(tmp_path / "run"))

    assert module.main() == 1
    assert len(calls) == 1
    assert calls[0][calls[0].index("--script") + 1] == "short.json"


def test_speed_gate_uses_full_build_total_not_resolve_step_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load()

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, 0, build_output(duration="30.000", total="31.00", elapsed="1.00")
        ),
    )

    assert (
        module.run_case("short", Path("short.json"), Path("inputs.json"), Path("out"))
        is False
    )


def test_speed_gate_rejects_margin_within_printed_rounding_precision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load()

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, 0, build_output(duration="10.005", total="10.00", elapsed="0.10")
        ),
    )

    assert (
        module.run_case("short", Path("short.json"), Path("inputs.json"), Path("out"))
        is False
    )
