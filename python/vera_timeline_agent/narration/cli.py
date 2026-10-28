from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import replace
from enum import IntEnum
from pathlib import Path
from typing import Any, Never, TextIO, cast

from vera_timeline_agent.narration.cache import CacheError, NarrationCache
from vera_timeline_agent.narration.configuration import (
    DEFAULT_PROFILE_ID,
    pricing_for,
    provider_for,
)
from vera_timeline_agent.narration.models import SynthesisSettings
from vera_timeline_agent.narration.normalize import MediaToolError, Normalizer
from vera_timeline_agent.narration.provider import (
    SpeechProviderError,
    SpeechSynthesisProvider,
)
from vera_timeline_agent.narration.service import (
    VOICE_PROFILES,
    NarrationService,
    ServiceConfig,
    voice_profile,
)
from vera_timeline_agent.narration.stage_directions import is_direction_only

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class CliExit(IntEnum):
    OK = 0
    FAILED_ASSET = 1
    VALIDATION = 2
    PROVIDER = 3
    MEDIA_TOOL = 4
    PREFLIGHT = 5
    USAGE = 64
    READ = 66
    INTERNAL = 70


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise ValueError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="python -m vera_timeline_agent.narration",
        description="Generate immutable temporary narration assets per active block.",
    )
    parser.add_argument("script", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument(
        "--voice-profile",
        choices=tuple(sorted(VOICE_PROFILES)),
        default=DEFAULT_PROFILE_ID,
        help="Named project voice profile (default: configured Inworld profile).",
    )
    parser.add_argument(
        "--aws-data-policy",
        choices=("opt_out_confirmed", "provider_terms_accepted"),
    )
    parser.add_argument(
        "--data-policy",
        choices=("fish_terms_accepted", "inworld_terms_accepted"),
    )
    parser.add_argument("--model", help="Explicit provider model; never falls back.")
    parser.add_argument(
        "--voice-id", help="Existing provider voice ID; creates no voice."
    )
    parser.add_argument(
        "--voice-version", help="Version label for immutable cache identity."
    )
    parser.add_argument("--rate", default="100%", help="Speaking speed, e.g. 110%%.")
    parser.add_argument("--max-cost-usd", type=float, default=1.0)
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--confirm-provider-call", action="store_true")
    return parser


def _validate_script(path: Path) -> tuple[dict[str, Any] | None, str]:
    command = [
        "node",
        "packages/contracts/src/script-validator-cli.ts",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return None, f"could not run ScriptDocument validator: {error}"
    if result.returncode != 0:
        return None, (result.stdout + result.stderr).strip()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, f"could not read validated ScriptDocument: {error}"
    if not isinstance(value, dict):
        return None, "validated ScriptDocument was not a JSON object"
    return cast(dict[str, Any], value), result.stdout.strip()


def _active_blocks(document: dict[str, Any]) -> list[dict[str, Any]]:
    active_draft = cast(dict[str, Any], document["activeDraft"])
    blocks = cast(list[dict[str, Any]], active_draft["blocks"])
    return [
        block
        for block in blocks
        if block.get("type") == "narration"
        and block.get("state") == "active"
        and not is_direction_only(block)
    ]


def run_cli(
    arguments: list[str],
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    provider: SpeechSynthesisProvider | None = None,
) -> int:
    try:
        try:
            options = _parser().parse_args(arguments)
        except ValueError as error:
            stderr.write(f"USAGE_ERROR: {error}\n")
            return CliExit.USAGE
        script = cast(Path, options.script)
        if not script.is_file():
            stderr.write(f"READ_ERROR: ScriptDocument is not a file: {script}\n")
            return CliExit.READ
        document, validation_output = _validate_script(script)
        if document is None:
            stderr.write(f"VALIDATION_ERROR:\n{validation_output}\n")
            return CliExit.VALIDATION
        blocks = _active_blocks(document)
        for option, value in (
            ("--model", options.model),
            ("--voice-id", options.voice_id),
            ("--voice-version", options.voice_version),
            ("--rate", options.rate),
        ):
            if value is not None and not value.strip():
                stderr.write(f"USAGE_ERROR: {option} must not be empty\n")
                return CliExit.USAGE
        selected_profile = voice_profile(cast(str, options.voice_profile))
        selected_profile = replace(
            selected_profile,
            engine=(
                options.model if options.model is not None else selected_profile.engine
            ),
            voice_id=(
                options.voice_id
                if options.voice_id is not None
                else selected_profile.voice_id
            ),
            voice_version=(
                options.voice_version
                if options.voice_version is not None
                else selected_profile.voice_version
            ),
        )
        if options.aws_data_policy and options.data_policy:
            stderr.write("USAGE_ERROR: choose one provider-specific data policy\n")
            return CliExit.USAGE
        policy_attestation = options.data_policy or options.aws_data_policy
        if not policy_attestation:
            stderr.write("USAGE_ERROR: an explicit provider data policy is required\n")
            return CliExit.USAGE
        expected_attestation = {
            "aws_polly": options.aws_data_policy,
            "fish_audio": "fish_terms_accepted",
            "inworld": "inworld_terms_accepted",
        }.get(selected_profile.provider)
        if policy_attestation != expected_attestation:
            stderr.write("USAGE_ERROR: data policy does not match selected provider\n")
            return CliExit.USAGE
        try:
            pricing = pricing_for(selected_profile)
        except ValueError as error:
            stderr.write(f"PREFLIGHT_ERROR: {error}\n")
            return CliExit.PREFLIGHT
        if not math.isfinite(options.max_cost_usd) or options.max_cost_usd < 0:
            stderr.write(
                "PREFLIGHT_ERROR: cost ceiling must be finite and nonnegative\n"
            )
            return CliExit.PREFLIGHT
        estimated_cost = sum(pricing.estimate(block["text"]) for block in blocks)
        stdout.write("VERA temporary narration preflight\n")
        stdout.write(f"script: {script}\n")
        stdout.write(f"validation: {validation_output.splitlines()[0]}\n")
        stdout.write(f"active narration blocks: {len(blocks)}\n")
        units = sum(pricing.units(block["text"]) for block in blocks)
        if pricing.unit == "utf16_units":
            stdout.write(f"billed characters: {units}\n")
        elif pricing.unit == "characters":
            stdout.write(f"billed characters (audio + marks): {units * 2}\n")
        else:
            stdout.write(f"billed UTF-8 bytes (audio + timing): {units}\n")
        stdout.write(f"estimated maximum charge: ${estimated_cost:.6f}\n")
        stdout.write(f"cost ceiling: ${options.max_cost_usd:.6f}\n")
        stdout.write(f"provider data policy attestation: {policy_attestation}\n")
        stdout.write(f"profile: {selected_profile.profile_id}\n")
        stdout.write(f"voice: {selected_profile.voice_id}\n")
        stdout.write(f"model: {selected_profile.engine}; rate: {options.rate}\n")
        stdout.write("normalization: vera-temporary-narration-v1\n")
        stdout.write("excluded narration is not synthesized\n")
        if estimated_cost > options.max_cost_usd:
            stderr.write("PREFLIGHT_ERROR: estimated charge exceeds cost ceiling\n")
            return CliExit.PREFLIGHT
        selected_provider = provider or provider_for(selected_profile)
        config = ServiceConfig(
            profile=selected_profile,
            settings=SynthesisSettings(rate=options.rate),
            data_policy_attestation=policy_attestation,
            max_cost_usd=options.max_cost_usd,
        )
        # Capability checks are pure; credentials and transport stay in live preflight.
        for block in blocks:
            selected_provider.prepare_input(config.request_for(block))
        if options.preflight_only:
            stdout.write(
                "preflight complete; no provider call or cache write occurred\n"
            )
            return CliExit.OK
        if not options.confirm_provider_call:
            stderr.write(
                "USAGE_ERROR: live generation requires --confirm-provider-call; "
                "use --preflight-only to inspect without network access\n"
            )
            return CliExit.USAGE

        normalizer = Normalizer()
        # Resolve and verify local capabilities before any provider call.
        tool_fingerprint = normalizer.tool_fingerprint
        stdout.write(f"media tool fingerprint: {tool_fingerprint}\n")
        service = NarrationService(
            cache=NarrationCache(cast(Path, options.cache)),
            provider=selected_provider,
            normalizer=normalizer,
            config=config,
        )
        assets = service.process_document(document)
        for asset in assets:
            stdout.write(
                f"block={asset.block_id} revision={asset.block_revision} "
                f"synthesis={asset.synthesis_disposition} "
                f"normalization={asset.normalization_disposition} "
                f"status={asset.status}\n"
            )
            stdout.write(f"  audio={asset.locators['audio']}\n")
            if asset.failure_reason is not None:
                stdout.write(f"  failure={asset.failure_reason}\n")
        failed = [asset for asset in assets if asset.status == "failed"]
        generated = sum(asset.synthesis_disposition == "generated" for asset in assets)
        reused = sum(asset.synthesis_disposition == "reused" for asset in assets)
        stdout.write(
            f"summary: ready={len(assets) - len(failed)} failed={len(failed)} "
            f"generated={generated} reused={reused}\n"
        )
        if failed:
            return (
                CliExit.MEDIA_TOOL
                if all(
                    asset.failure_reason is not None
                    and asset.failure_reason.startswith("media_tool:")
                    for asset in failed
                )
                else CliExit.PROVIDER
            )
        return CliExit.OK
    except MediaToolError as error:
        stderr.write(f"MEDIA_TOOL_ERROR: {error}\n")
        return CliExit.MEDIA_TOOL
    except (SpeechProviderError, CacheError) as error:
        stderr.write(f"PROVIDER_OR_CACHE_ERROR: {error}\n")
        return CliExit.PROVIDER
    except Exception as error:
        stderr.write(f"INTERNAL_ERROR: {error}\n")
        return CliExit.INTERNAL


def main() -> None:
    raise SystemExit(run_cli(sys.argv[1:]))
