"""The retry CLI exposes the explicit plan and request, including install handoff."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from vera_timeline_agent import qualification_output_controller_v2 as controller
from vera_timeline_agent import workflow_v2_cli as cli


@pytest.mark.parametrize("command", ["output-retry-plan", "output-retry"])
def test_retry_commands_reopen_exact_session_and_print_reviewable_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    session = tmp_path / "session.json"
    approval = tmp_path / "approval.json"
    result = tmp_path / "retry.json"
    result.write_bytes(b"retry")
    handoff = tmp_path / "handoff.json"
    handoff.write_bytes(b"handoff")
    seen: list[tuple[Path, str]] = []
    prepared: list[Path] = []

    def prepare(path: Path) -> Path:
        prepared.append(path)
        return result

    fake = SimpleNamespace(
        prepare_render_retry_plan=prepare,
        prepare_render_retry_request=prepare,
        native_operator_handoff_path=lambda _: handoff,
    )

    def load(path: Path, digest: str) -> SimpleNamespace:
        seen.append((path, digest))
        return fake

    monkeypatch.setattr(controller, "load_output_session", load)
    option, path = (
        ("--output", result)
        if command == "output-retry-plan"
        else ("--approval", approval)
    )
    assert (
        cli.main(
            [
                command,
                "--session",
                str(session),
                "--session-sha256",
                "a" * 64,
                option,
                str(path),
            ]
        )
        == 0
    )
    assert seen == [(session, "a" * 64)]
    assert prepared == [path]
    printed = capsys.readouterr().out
    assert str(result) in printed
    if command == "output-retry":
        assert str(handoff) in printed
