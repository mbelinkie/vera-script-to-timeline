from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from enum import IntEnum
from pathlib import Path
from typing import Any, Never, TextIO, cast

from vera_timeline_agent.narration.cache import CacheError, NarrationCache
from vera_timeline_agent.narration.normalize import MediaToolError, Normalizer
from vera_timeline_agent.narration.polly import (
    PRICE_USD_PER_MILLION_CHARACTERS,
    PollyError,
    PollyProvider,
)
from vera_timeline_agent.narration.provider import SpeechSynthesisProvider
from vera_timeline_agent.narration.service import (
    MATTHEW_PROFILE_ID,
    VOICE_PROFILES,
    NarrationService,
    ServiceConfig,
    voice_profile,
)

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
        default=MATTHEW_PROFILE_ID,
        help="Named project voice profile (default: Matthew Neural).",
    )
    parser.add_argument(
        "--aws-data-policy",
        required=True,
        choices=("opt_out_confirmed", "provider_terms_accepted"),
    )
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
        if block.get("type") == "narration" and block.get("state") == "active"
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
        selected_profile = voice_profile(cast(str, options.voice_profile))
        if not math.isfinite(options.max_cost_usd) or options.max_cost_usd < 0:
            stderr.write(
                "PREFLIGHT_ERROR: cost ceiling must be finite and nonnegative\n"
            )
            return CliExit.PREFLIGHT
        billed_characters = sum(len(cast(str, block["text"])) for block in blocks) * 2
        estimated_cost = (
            billed_characters * (PRICE_USD_PER_MILLION_CHARACTERS / 2) / 1_000_000
        )
        # PRICE is already audio plus marks ($32/M); billed_characters is printed as
        # two requests for transparency, while cost uses authored characters once.
        estimated_cost = (
            sum(len(cast(str, block["text"])) for block in blocks)
            * PRICE_USD_PER_MILLION_CHARACTERS
            / 1_000_000
        )
        stdout.write("VERA temporary narration preflight\n")
        stdout.write(f"script: {script}\n")
        stdout.write(f"validation: {validation_output.splitlines()[0]}\n")
        stdout.write(f"active narration blocks: {len(blocks)}\n")
        stdout.write(f"billed characters (audio + marks): {billed_characters}\n")
        stdout.write(f"estimated maximum charge: ${estimated_cost:.6f}\n")
        stdout.write(f"cost ceiling: ${options.max_cost_usd:.6f}\n")
        stdout.write(f"AWS data policy attestation: {options.aws_data_policy}\n")
        stdout.write(f"profile: {selected_profile.profile_id}\n")
        stdout.write(f"voice: {selected_profile.voice_id}\n")
        stdout.write("normalization: vera-temporary-narration-v1\n")
        stdout.write("excluded narration is not synthesized\n")
        if estimated_cost > options.max_cost_usd:
            stderr.write("PREFLIGHT_ERROR: estimated charge exceeds cost ceiling\n")
            return CliExit.PREFLIGHT
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
            provider=provider or PollyProvider(),
            normalizer=normalizer,
            config=ServiceConfig(
                profile=selected_profile,
                data_policy_attestation=cast(str, options.aws_data_policy),
                max_cost_usd=cast(float, options.max_cost_usd),
            ),
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
    except (PollyError, CacheError) as error:
        stderr.write(f"PROVIDER_OR_CACHE_ERROR: {error}\n")
        return CliExit.PROVIDER
    except Exception as error:
        stderr.write(f"INTERNAL_ERROR: {error}\n")
        return CliExit.INTERNAL


def main() -> None:
    raise SystemExit(run_cli(sys.argv[1:]))
