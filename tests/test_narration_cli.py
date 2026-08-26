from __future__ import annotations

import io
from pathlib import Path

from vera_timeline_agent.narration.cli import CliExit, run_cli
from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
)
from vera_timeline_agent.narration.service import MATTHEW_PROFILE_ID

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "tests/data/slice_1_1/minimal.script-document.json"
TORTURE = ROOT / "tests/data/slice_1_1/torture.script-document.json"


class CliFakeProvider:
    adapter_version = "cli-fake/v1"

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail
        self.requests: list[SynthesisRequest] = []

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        return f"<speak>{request.text}</speak>".encode()

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.calls += 1
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("test provider unavailable")
        # A non-silent 440 Hz signed PCM signal, precomputed deterministically.
        import math
        import struct

        audio = b"".join(
            struct.pack("<h", round(7000 * math.sin(2 * math.pi * 440 * i / 16000)))
            for i in range(8000)
        )
        return ProviderResult(
            audio_bytes=audio,
            audio_format="pcm_s16le",
            sample_rate=16000,
            channels=1,
            provider_input=self.prepare_input(request),
            timing_marks=(
                ProviderTimingMark(
                    kind="sentence",
                    time_ms=0,
                    start_byte=0,
                    end_byte=len(request.text.encode()),
                    start_utf16=0,
                    end_utf16=len(request.text.encode("utf-16-le")) // 2,
                    value=request.text,
                ),
            ),
            provenance={
                "provider": "fake",
                "region": "test",
                "engine": "test",
                "voiceId": "test",
                "voiceVersion": "v1",
            },
            request_ids=("cli-fake",),
        )


def args(script: Path, cache: Path) -> list[str]:
    return [
        str(script),
        "--cache",
        str(cache),
        "--aws-data-policy",
        "provider_terms_accepted",
    ]


def test_preflight_is_deterministic_and_never_calls_provider(tmp_path: Path) -> None:
    provider = CliFakeProvider()
    stdout = io.StringIO()
    stderr = io.StringIO()

    code = run_cli(
        [*args(TORTURE, tmp_path / "cache"), "--preflight-only"],
        stdout=stdout,
        stderr=stderr,
        provider=provider,
    )

    assert code == CliExit.OK
    assert stderr.getvalue() == ""
    assert provider.calls == 0
    assert "active narration blocks: 1" in stdout.getvalue()
    assert "billed characters (audio + marks): 62" in stdout.getvalue()
    assert f"profile: {MATTHEW_PROFILE_ID}" in stdout.getvalue()
    assert "excluded narration is not synthesized" in stdout.getvalue()
    assert not (tmp_path / "cache").exists()


def test_cli_selects_joanna_as_named_alternative_without_silent_attestation(
    tmp_path: Path,
) -> None:
    provider = CliFakeProvider()
    stdout = io.StringIO()

    code = run_cli(
        [
            str(MINIMAL),
            "--cache",
            str(tmp_path / "cache"),
            "--voice-profile",
            "aws-polly-joanna-neural-en-us-v1",
            "--aws-data-policy",
            "provider_terms_accepted",
            "--confirm-provider-call",
        ],
        stdout=stdout,
        stderr=io.StringIO(),
        provider=provider,
    )

    assert code == CliExit.OK
    assert provider.calls == 1
    assert provider.requests[0].profile.voice_id == "Joanna"
    assert "profile: aws-polly-joanna-neural-en-us-v1" in stdout.getvalue()

    missing_attestation = run_cli(
        [
            str(MINIMAL),
            "--cache",
            str(tmp_path / "other-cache"),
            "--voice-profile",
            MATTHEW_PROFILE_ID,
            "--preflight-only",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        provider=provider,
    )
    assert missing_attestation == CliExit.USAGE


def test_cli_reports_generated_then_all_reused_in_block_order(tmp_path: Path) -> None:
    provider = CliFakeProvider()
    first_out = io.StringIO()
    second_out = io.StringIO()
    live_args = [*args(TORTURE, tmp_path / "cache"), "--confirm-provider-call"]

    first_code = run_cli(
        live_args, stdout=first_out, stderr=io.StringIO(), provider=provider
    )
    second_code = run_cli(
        live_args, stdout=second_out, stderr=io.StringIO(), provider=provider
    )

    assert first_code == second_code == CliExit.OK
    assert provider.calls == 1
    assert (
        "synthesis=generated normalization=generated status=ready"
        in first_out.getvalue()
    )
    assert "synthesis=reused normalization=reused status=ready" in second_out.getvalue()
    assert "summary: ready=1 failed=0 generated=0 reused=1" in second_out.getvalue()
    assert "Unused alternative" not in first_out.getvalue()


def test_cli_provider_failure_is_nonzero_and_reports_placeholder(
    tmp_path: Path,
) -> None:
    stdout = io.StringIO()

    code = run_cli(
        [*args(MINIMAL, tmp_path / "cache"), "--confirm-provider-call"],
        stdout=stdout,
        stderr=io.StringIO(),
        provider=CliFakeProvider(fail=True),
    )

    assert code == CliExit.PROVIDER
    assert "status=failed" in stdout.getvalue()
    assert "provider: test provider unavailable" in stdout.getvalue()


def test_cli_fails_before_network_when_confirmation_is_missing(tmp_path: Path) -> None:
    provider = CliFakeProvider()
    stderr = io.StringIO()

    code = run_cli(
        args(MINIMAL, tmp_path / "cache"),
        stdout=io.StringIO(),
        stderr=stderr,
        provider=provider,
    )

    assert code == CliExit.USAGE
    assert provider.calls == 0
    assert "--confirm-provider-call" in stderr.getvalue()


def test_cli_rejects_invalid_json_and_cost_ceiling_before_network(
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    provider = CliFakeProvider()
    assert (
        run_cli(
            [*args(invalid, tmp_path / "cache"), "--preflight-only"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            provider=provider,
        )
        == CliExit.VALIDATION
    )

    assert (
        run_cli(
            [
                *args(MINIMAL, tmp_path / "cache"),
                "--confirm-provider-call",
                "--max-cost-usd",
                "0",
            ],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            provider=provider,
        )
        == CliExit.PREFLIGHT
    )
    assert (
        run_cli(
            [
                *args(MINIMAL, tmp_path / "cache"),
                "--confirm-provider-call",
                "--max-cost-usd",
                "nan",
            ],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            provider=provider,
        )
        == CliExit.PREFLIGHT
    )
    assert provider.calls == 0
