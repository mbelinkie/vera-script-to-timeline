"""Polly timing campaign (#182): guarded generation, measurement, omission envelopes.

    python -m vera_timeline_agent.narration.campaign generate --doc SCRIPT.json \\
        --cache DIR --aws-data-policy provider_terms_accepted --confirm-provider-call
    python -m vera_timeline_agent.narration.campaign measure --cache DIR \\
        --asset BLOCK_ID/ASSET_ID --block FROZEN_V2_BLOCK_OR_DOCUMENT.json --out DIR
    python -m vera_timeline_agent.narration.campaign omission \\
        --evidence DIR/narration-measurements/ASSET_ID.boundary-evidence.json \\
        --token TOKEN_ID

``generate`` wraps the existing NarrationService unchanged.  A cumulative cost
ledger outside the repository refuses any live call that would take the total
past the cap, and records a row only for calls that really reached the
provider (cache hits cost nothing and record nothing).
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import math
import os
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Never, Protocol, TextIO, cast

from vera_timeline_agent.narration.cache import CacheError, NarrationCache
from vera_timeline_agent.narration.cli import (
    CliExit,
    _active_blocks,
    _validate_script,
)
from vera_timeline_agent.narration.measure import (
    MeasurementError,
    load_asset,
    measure_asset,
)
from vera_timeline_agent.narration.models import (
    NarrationAudioAsset,
    canonical_json_bytes,
)
from vera_timeline_agent.narration.normalize import MediaToolError, Normalizer
from vera_timeline_agent.narration.omission_envelope import (
    EnvelopeRefused,
    omission_envelope_report,
)
from vera_timeline_agent.narration.polly import (
    PollyError,
    PollyProvider,
)
from vera_timeline_agent.narration.provider import SpeechSynthesisProvider
from vera_timeline_agent.narration.service import (
    MATTHEW_PROFILE_ID,
    VOICE_PROFILES,
    BlockPlan,
    NarrationService,
    ServiceConfig,
    voice_profile,
)

CAP_MICRO_USD = 1_000_000
LEDGER_VERSION = "polly-campaign-ledger/v1"


def default_ledger_path() -> Path:
    return Path.home() / "Library/Application Support/VERA/polly-campaign/ledger.json"


class LedgerError(RuntimeError):
    pass


class CapExceeded(RuntimeError):
    pass


def _micro(usd: float) -> int:
    return math.ceil(round(usd * 1_000_000, 6))


class Ledger:
    """Append-only cumulative record of real provider calls."""

    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.path = path
        self.clock = clock

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        directory = self.path.parent
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        descriptor = os.open(directory / "ledger.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LedgerError(f"ledger is unreadable: {error}") from error
        if (
            not isinstance(value, dict)
            or value.get("schemaVersion") != LEDGER_VERSION
            or not isinstance(value.get("rows"), list)
        ):
            raise LedgerError("ledger has an unexpected shape")
        rows = value["rows"]
        for row in rows:
            if not isinstance(row, dict) or not isinstance(
                row.get("estimatedCostUsd"), int | float
            ):
                raise LedgerError("ledger row is malformed")
        return cast(list[dict[str, Any]], rows)

    def cumulative_micro_usd(self) -> int:
        return sum(_micro(float(row["estimatedCostUsd"])) for row in self.rows())

    def check(
        self, additional_micro_usd: int, cap_micro_usd: int = CAP_MICRO_USD
    ) -> None:
        total = self.cumulative_micro_usd() + additional_micro_usd
        if total > cap_micro_usd:
            raise CapExceeded(
                f"cumulative ${total / 1e6:.6f} would exceed the "
                f"${cap_micro_usd / 1e6:.2f} campaign cap"
            )

    def append(
        self,
        *,
        request_hash: str,
        block_id: str,
        characters: int,
        estimated_cost_usd: float,
        request_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        row = {
            "requestHash": request_hash,
            "blockId": block_id,
            "characters": characters,
            "estimatedCostUsd": estimated_cost_usd,
            "requestIds": list(request_ids),
            "at": self.clock().isoformat(),
        }
        with self._locked():
            rows = self.rows()
            rows.append(row)
            payload = json.dumps(
                {"schemaVersion": LEDGER_VERSION, "rows": rows},
                indent=2,
                sort_keys=True,
            )
            descriptor, temporary = tempfile.mkstemp(
                dir=self.path.parent, prefix=".ledger-"
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(payload + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temporary, 0o600)
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return row


class PlannableService(Protocol):
    def plan_block(self, block: dict[str, Any]) -> BlockPlan: ...

    def process_block(self, block: dict[str, Any]) -> NarrationAudioAsset: ...


@dataclass
class GenerateReport:
    assets: list[NarrationAudioAsset] = field(default_factory=list)
    generated: list[NarrationAudioAsset] = field(default_factory=list)
    reused: list[NarrationAudioAsset] = field(default_factory=list)
    failed: list[NarrationAudioAsset] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def request_ids(self) -> list[str]:
        return [rid for asset in self.generated for rid in asset.request_ids]


def run_generate(
    service: PlannableService,
    document: dict[str, Any],
    ledger: Ledger,
    *,
    cap_micro_usd: int = CAP_MICRO_USD,
) -> GenerateReport:
    """Generate every active narration block, billing only real provider calls."""

    blocks = sorted(
        _active_blocks(document),
        key=lambda block: (str(block.get("orderKey", "")), str(block.get("id", ""))),
    )
    plans = [(block, service.plan_block(block)) for block in blocks]
    # Distinct uncached requests only: identical requests share one cache entry.
    uncached = {
        plan.request_hash: _micro(plan.estimated_cost_usd)
        for _block, plan in plans
        if not plan.cached
    }
    ledger.check(sum(uncached.values()), cap_micro_usd)

    report = GenerateReport()
    for block, _upfront in plans:
        # Re-plan right before each block: an identical earlier block may have
        # filled the cache, and the ledger may have grown.
        plan = service.plan_block(block)
        if not plan.cached:
            ledger.check(_micro(plan.estimated_cost_usd), cap_micro_usd)
        asset = service.process_block(block)
        report.assets.append(asset)
        if asset.status == "failed":
            report.failed.append(asset)
        elif asset.synthesis_disposition == "generated":
            report.generated.append(asset)
            report.rows.append(
                ledger.append(
                    request_hash=asset.request_hash,
                    block_id=asset.block_id,
                    characters=plan.characters,
                    estimated_cost_usd=plan.estimated_cost_usd,
                    request_ids=asset.request_ids,
                )
            )
        else:
            report.reused.append(asset)
    return report


# ------------------------------------------------------------------------ CLI


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise ValueError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="python -m vera_timeline_agent.narration.campaign",
        description="Polly timing campaign: generate, measure, omission envelope.",
    )
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    generate = sub.add_parser("generate")
    generate.add_argument("--doc", type=Path, required=True)
    generate.add_argument("--cache", type=Path, required=True)
    generate.add_argument(
        "--voice-profile",
        choices=tuple(sorted(VOICE_PROFILES)),
        default=MATTHEW_PROFILE_ID,
    )
    generate.add_argument(
        "--aws-data-policy",
        required=True,
        choices=("opt_out_confirmed", "provider_terms_accepted"),
    )
    generate.add_argument("--ledger", type=Path, default=None)
    generate.add_argument("--confirm-provider-call", action="store_true")

    measure = sub.add_parser("measure")
    measure.add_argument("--cache", type=Path, required=True)
    measure.add_argument("--asset", required=True, help="BLOCK_ID/ASSET_ID")
    measure.add_argument(
        "--block",
        type=Path,
        required=True,
        help="frozen v2 narration block JSON, or a v2 ScriptDocument containing it",
    )
    measure.add_argument("--out", type=Path, required=True)
    measure.add_argument(
        "--artifact-locator",
        default=None,
        help="project-relative artifact path under --out "
        "(default narration-measurements/ASSET_ID.measurement.json)",
    )

    omission = sub.add_parser("omission")
    omission.add_argument("--evidence", type=Path, required=True)
    omission.add_argument("--token", required=True)
    omission.add_argument("--out", type=Path, default=None)
    return parser


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _select_block(value: Any, block_id: str) -> Mapping[str, Any]:
    if isinstance(value, dict) and value.get("type") == "narration":
        return value
    if isinstance(value, dict) and isinstance(value.get("activeDraft"), dict):
        for block in value["activeDraft"].get("blocks", []):
            if isinstance(block, dict) and block.get("id") == block_id:
                return block
    raise MeasurementError([f"no frozen narration block {block_id} in input"])


def run_campaign(
    arguments: list[str],
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    provider: SpeechSynthesisProvider | None = None,
    ledger_path: Path | None = None,
    validator: Callable[[Path], tuple[dict[str, Any] | None, str]] = _validate_script,
    normalizer: Normalizer | None = None,
) -> int:
    try:
        try:
            options = _parser().parse_args(arguments)
        except ValueError as error:
            stderr.write(f"USAGE_ERROR: {error}\n")
            return CliExit.USAGE
        if options.command == "generate":
            return _generate(
                options, stdout, stderr, provider, ledger_path, validator, normalizer
            )
        if options.command == "measure":
            return _measure(options, stdout, stderr)
        return _omission(options, stdout, stderr)
    except (OSError, json.JSONDecodeError) as error:
        stderr.write(f"READ_ERROR: {error}\n")
        return CliExit.READ
    except MeasurementError as error:
        stderr.write("MEASUREMENT_REFUSED:\n")
        for reason in error.reasons:
            stderr.write(f"  - {reason}\n")
        return CliExit.VALIDATION
    except EnvelopeRefused as error:
        stderr.write(f"ENVELOPE_REFUSED: {error}\n")
        return CliExit.VALIDATION
    except (CapExceeded, LedgerError) as error:
        stderr.write(f"PREFLIGHT_ERROR: {error}\n")
        return CliExit.PREFLIGHT
    except MediaToolError as error:
        stderr.write(f"MEDIA_TOOL_ERROR: {error}\n")
        return CliExit.MEDIA_TOOL
    except (PollyError, CacheError) as error:
        stderr.write(f"PROVIDER_OR_CACHE_ERROR: {error}\n")
        return CliExit.PROVIDER
    except Exception as error:
        stderr.write(f"INTERNAL_ERROR: {error}\n")
        return CliExit.INTERNAL


def _generate(
    options: argparse.Namespace,
    stdout: TextIO,
    stderr: TextIO,
    provider: SpeechSynthesisProvider | None,
    ledger_path: Path | None,
    validator: Callable[[Path], tuple[dict[str, Any] | None, str]],
    normalizer: Normalizer | None,
) -> int:
    doc = cast(Path, options.doc)
    if not doc.is_file():
        stderr.write(f"READ_ERROR: ScriptDocument is not a file: {doc}\n")
        return CliExit.READ
    document, validation = validator(doc)
    if document is None:
        stderr.write(f"VALIDATION_ERROR:\n{validation}\n")
        return CliExit.VALIDATION
    ledger = Ledger(
        ledger_path or cast(Path | None, options.ledger) or default_ledger_path()
    )
    profile = voice_profile(cast(str, options.voice_profile))
    service = NarrationService(
        cache=NarrationCache(cast(Path, options.cache)),
        provider=provider or PollyProvider(),
        normalizer=normalizer or Normalizer(),
        config=ServiceConfig(
            profile=profile,
            data_policy_attestation=cast(str, options.aws_data_policy),
            max_cost_usd=1.0,
        ),
    )
    blocks = _active_blocks(document)
    plans = [service.plan_block(block) for block in blocks]
    new_cost = sum(
        {
            p.request_hash: _micro(p.estimated_cost_usd) for p in plans if not p.cached
        }.values()
    )
    stdout.write("VERA Polly campaign preflight\n")
    stdout.write(f"active narration blocks: {len(blocks)}\n")
    stdout.write(f"cached (no call): {sum(p.cached for p in plans)}\n")
    stdout.write(f"estimated new charge: ${new_cost / 1e6:.6f}\n")
    stdout.write(f"campaign spent so far: ${ledger.cumulative_micro_usd() / 1e6:.6f}\n")
    stdout.write(f"campaign cap: ${CAP_MICRO_USD / 1e6:.2f}\n")
    ledger.check(new_cost)
    if not options.confirm_provider_call and new_cost:
        stderr.write("USAGE_ERROR: live generation requires --confirm-provider-call\n")
        return CliExit.USAGE
    report = run_generate(service, document, ledger)
    for asset in report.assets:
        disposition = (
            "failed"
            if asset.status == "failed"
            else "generated"
            if asset in report.generated
            else "reused"
        )
        stdout.write(
            f"block={asset.block_id} revision={asset.block_revision} "
            f"asset={asset.asset_id} {disposition} "
            f"request_ids={','.join(asset.request_ids) or '-'}\n"
        )
        if asset.failure_reason:
            stdout.write(f"  failure={asset.failure_reason}\n")
    stdout.write(
        f"summary: generated={len(report.generated)} reused={len(report.reused)} "
        f"failed={len(report.failed)} "
        f"request_ids={','.join(report.request_ids) or '-'}\n"
    )
    return CliExit.PROVIDER if report.failed else CliExit.OK


def _measure(options: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    asset_key = cast(str, options.asset)
    block_id, _, asset_id = asset_key.partition("/")
    cache = NarrationCache(cast(Path, options.cache))
    loaded = load_asset(cache, asset_key)
    block = _select_block(_read_json(cast(Path, options.block)), block_id)
    locator = (
        cast(str | None, options.artifact_locator)
        or f"narration-measurements/{asset_id}.measurement.json"
    )
    if locator.startswith("/") or ".." in Path(locator).parts or "\n" in locator:
        raise MeasurementError(["artifact locator must be project-relative"])
    result = measure_asset(loaded, block, artifact_locator=locator)
    out = cast(Path, options.out)
    artifact_path = out / locator
    evidence_path = artifact_path.with_name(f"{asset_id}.boundary-evidence.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(result.artifact_bytes)
    evidence_path.write_bytes(canonical_json_bytes(result.evidence))
    stdout.write(f"measurement artifact: {artifact_path}\n")
    stdout.write(f"boundary evidence: {evidence_path}\n")
    stdout.write(
        f"lag: {result.artifact['lag']['milliseconds']} ms "
        f"(correlation {result.artifact['lag']['correlation']})\n"
    )
    for row in result.artifact["tokens"]:
        end = (
            f"{row['audibleEndSamples'] / 48:.1f} ms"
            if row["audibleEndSamples"] is not None
            else f"absent ({row['endReason']})"
        )
        stdout.write(
            f"  {row['quotedText']!r}: onset {row['onsetSamples'] / 48:.1f} ms, "
            f"end {end}\n"
        )
    return CliExit.OK


def _omission(options: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    evidence = _read_json(cast(Path, options.evidence))
    report = omission_envelope_report(evidence, cast(str, options.token))
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if options.out is not None:
        cast(Path, options.out).write_text(text, encoding="utf-8")
    stdout.write(text)
    if not report["uniquelySafe"]:
        stderr.write("ENVELOPE_REFUSED: " + "; ".join(report["refusalReasons"]) + "\n")
        return CliExit.VALIDATION
    return CliExit.OK


def main() -> None:
    raise SystemExit(run_campaign(sys.argv[1:]))


if __name__ == "__main__":
    main()
