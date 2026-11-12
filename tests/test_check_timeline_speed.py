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
    *,
    frames: str = "720",
    duration: str = "30.000",
    total: str = "20.00",
    elapsed: str = "0.40",
) -> str:
    return (
        "preflight: PASS (0.02s)\n"
        f"Resolve step + check: PASS ({elapsed}s)\n"
        f"PASS: {frames} frames ({duration}s timeline); total {total}s\n"
    )


def cli_args(output: Path) -> list[str]:
    return [
        "check_timeline_speed.py",
        "--short-script",
        "short.json",
        "--short-inputs",
        "short-inputs.json",
        "--short-preparation-seconds",
        "12.34",
        "--long-script",
        "long.json",
        "--long-inputs",
        "long-inputs.json",
        "--long-preparation-seconds",
        "56.78",
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
        printed.count(
            "| Case | Preparation (s) | Timeline (s) | Build plus check (s) | Result |"
        )
        == 1
    )
    assert "| short | 12.34 | 30.000 | 20.00 | PASS |" in printed
    assert "| long | 56.78 | 30.000 | 20.00 | PASS |" in printed
    assert "| Stage | Seconds |" not in printed
    assert "This check does not cover the default 23.976 fps route." in printed


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
            build_output(frames="240", duration="10.000", total="10.50")
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
    assert "| short | 12.34 | 10.000 | 10.50 | FAIL |" in printed
    assert "| long | 56.78 | 30.000 | 20.00 | PASS |" in printed


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

    result = module.run_case(
        "short", Path("short.json"), Path("inputs.json"), Path("out")
    )
    assert result is not None and result[2] is False


def test_speed_gate_rejects_margin_within_printed_rounding_precision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load()

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command,
            0,
            build_output(
                frames="240", duration="10.000", total="10.00", elapsed="0.10"
            ),
        ),
    )

    result = module.run_case(
        "short", Path("short.json"), Path("inputs.json"), Path("out")
    )
    assert result is not None and result[2] is False


def test_run_case_rejects_timeline_duration_inconsistent_with_24fps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load()

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, 0, build_output(frames="750", duration="30.000")
        ),
    )

    assert (
        module.run_case("short", Path("short.json"), Path("inputs.json"), Path("out"))
        is None
    )


@pytest.mark.parametrize(
    "option", ("--short-preparation-seconds", "--long-preparation-seconds")
)
def test_main_requires_both_preparation_times(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    option: str,
) -> None:
    module = load()
    output = tmp_path / "run"
    arguments = cli_args(output)
    index = arguments.index(option)
    del arguments[index : index + 2]
    monkeypatch.setattr(sys, "argv", arguments)

    with pytest.raises(SystemExit) as error:
        module.main()

    assert error.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize("value", ("nan", "inf", "-inf", "-0.1"))
def test_main_rejects_nonfinite_or_negative_preparation_times(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    module = load()
    output = tmp_path / "run"
    arguments = cli_args(output)
    arguments[arguments.index("--short-preparation-seconds") + 1] = value
    monkeypatch.setattr(sys, "argv", arguments)

    with pytest.raises(SystemExit) as error:
        module.main()

    assert error.value.code == 2
    assert not output.exists()
