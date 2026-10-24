"""Offline-first, bounded public Fish/Polly timing study for issue #289."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from vera_timeline_agent.narration.configuration import (  # noqa: E402
    FISH_PROFILE_ID,
    JOANNA_PROFILE_ID,
    MATTHEW_PROFILE_ID,
    pricing_for,
    voice_profile,
)
from vera_timeline_agent.narration.fish import FishError, FishProvider  # noqa: E402
from vera_timeline_agent.narration.models import (  # noqa: E402
    SynthesisRequest,
    SynthesisSettings,
    identity_hash,
    sha256_bytes,
)
from vera_timeline_agent.narration.polly import PollyProvider  # noqa: E402
from vera_timeline_agent.narration.provider import SpeechSynthesisProvider  # noqa: E402
from vera_timeline_agent.narration.service import ServiceConfig  # noqa: E402

CORPUS = Path(__file__).with_name("issue289_corpus.json")
DEFAULT_OUTPUT = Path.home() / "Documents" / "VERA" / "issue289-public-study"
BUDGET_USD = 1.0
GENERATIONS = 3
PRICE_SOURCE = "https://aws.amazon.com/polly/pricing/"
FISH_RESPONSE_LIMIT = 256 * 1024 * 1024


def load_corpus() -> dict[str, list[dict[str, str]]]:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("corpusVersion") != "issue289-public-synthetic/v1"
    ):
        raise ValueError("unsupported issue #289 corpus")
    paired, fish_only = data.get("pairedTexts"), data.get("fishOnlyTexts")
    bands = {"short": (10, 20), "medium": (40, 60), "long": (90, 120)}
    if (
        not isinstance(paired, list)
        or len(paired) != 3
        or not isinstance(fish_only, list)
        or len(fish_only) != 7
    ):
        raise ValueError("study needs three paired texts and seven Fish-only texts")
    seen: set[str] = set()
    for row in paired:
        if not isinstance(row, dict) or set(row) != {"id", "targetWords", "text"}:
            raise ValueError("invalid corpus record")
        text_id, text = row["id"], row["text"]
        if not isinstance(text_id, str) or text_id not in bands or text_id in seen:
            raise ValueError("invalid or repeated corpus id")
        if (
            not isinstance(text, str)
            or not bands[text_id][0] <= len(text.split()) <= bands[text_id][1]
        ):
            raise ValueError(f"{text_id} text is outside its word-count band")
        if row["targetWords"] != f"{bands[text_id][0]}-{bands[text_id][1]}":
            raise ValueError(f"{text_id} word-count label is wrong")
        if text_id == "long" and len(text) <= 300:
            raise ValueError("long text must exceed 300 characters for Fish chunking")
        if len(text) > 3000:
            raise ValueError("text exceeds Polly's synchronous limit")
        seen.add(text_id)
    if seen != set(bands):
        raise ValueError("corpus must contain short, medium, and long texts")
    for row in fish_only:
        if not isinstance(row, dict) or set(row) != {"id", "text"}:
            raise ValueError("invalid Fish-only corpus record")
        text_id, text = row["id"], row["text"]
        if not isinstance(text_id, str) or text_id in seen or not isinstance(text, str):
            raise ValueError("invalid or repeated Fish-only record")
        if not 10 <= len(text.split()) <= 120:
            raise ValueError(
                f"{text_id} must contain 10-120 whitespace-delimited words"
            )
        seen.add(text_id)
    if len(seen) != 10:
        raise ValueError("Fish study must use ten distinct texts")
    return {"pairedTexts": paired, "fishOnlyTexts": fish_only}


def _request(
    run_id: str,
    provider: str,
    row: dict[str, str],
    generation: int,
    profile_id: str,
    settings: SynthesisSettings,
    attestation: str | None,
    budget_usd: float,
) -> SynthesisRequest:
    return ServiceConfig(
        profile=voice_profile(profile_id),
        settings=settings,
        data_policy_attestation=attestation,
        max_cost_usd=0.0 if provider == "fish" else budget_usd,
    ).request_for(
        {
            "id": f"{run_id}-{provider}-{row['id']}-g{generation}",
            "version": generation,
            "text": row["text"],
        }
    )


class CapturingFishProvider(FishProvider):
    """Capture Fish SSE verbatim while keeping its own authenticated transport."""

    def __init__(
        self,
        raw_path: Path,
        transport: Callable[[bytes, str], Iterable[bytes]] | None = None,
    ) -> None:
        self.raw_path, self.study_transport = raw_path, transport
        super().__init__(transport=self._capture)

    def _capture(self, payload: bytes, model: str) -> Iterable[bytes]:
        source = self.study_transport or self._authenticated_stream
        size = 0
        try:
            with self.raw_path.open("xb") as output:
                for chunk in source(payload, model):
                    size += len(chunk)
                    if size > FISH_RESPONSE_LIMIT:
                        raise FishError("Fish response exceeds the retention limit")
                    output.write(chunk)
                    yield chunk
        except BaseException:
            if self.raw_path.exists() and self.raw_path.stat().st_size == 0:
                self.raw_path.unlink()
            raise
        if size == 0:
            self.raw_path.unlink(missing_ok=True)


def _provider(name: str, raw_path: Path) -> SpeechSynthesisProvider:
    if name == "fish":
        return CapturingFishProvider(raw_path)
    if name == "polly":
        # PollyProvider configures botocore with total_max_attempts=1.
        return PollyProvider()
    raise ValueError(f"unknown provider {name!r}")


def _write_json(path: Path, value: object) -> None:
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temp.replace(path)


def _safe_error(error: Exception) -> dict[str, str]:
    message = re.sub(
        r"(?i)(api[_-]?key|authorization|bearer|token|secret|password|credential)([\s:=]+)[^\s,;]+",
        r"\1\2[REDACTED]",
        str(error),
    )
    return {"type": type(error).__name__, "message": message[:1000]}


def _fish_chunks(raw: bytes) -> dict[str, int]:
    lines = [
        line[5:].strip()
        for line in raw.decode("utf-8", "replace").splitlines()
        if line.startswith("data:")
    ]
    events = []
    for line in lines:
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                events.append(value)
        except json.JSONDecodeError:
            pass
    return {
        "sseDataEvents": len(lines),
        "audioChunks": sum("audio_base64" in event for event in events),
        "alignmentChunks": sum("alignment" in event for event in events),
    }


def _plan(
    corpus: dict[str, list[dict[str, str]]],
    run_id: str,
    fish_profile_id: str,
    polly_profile_id: str,
    settings: SynthesisSettings,
    budget_usd: float,
    fish_attestation: str | None,
    aws_attestation: str | None,
) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run_id):
        raise ValueError(
            "run id must contain only letters, digits, hyphens, or underscores"
        )
    if not 0 < budget_usd <= BUDGET_USD:
        raise ValueError("Polly budget must be positive and no more than $1.00")
    plan = []
    paired = [(row, ("fish", "polly"), GENERATIONS) for row in corpus["pairedTexts"]]
    paired.extend((row, ("fish",), 1) for row in corpus["fishOnlyTexts"])
    for row, provider_names, generations in paired:
        for name in provider_names:
            profile_id, attestation = (
                (fish_profile_id, fish_attestation)
                if name == "fish"
                else (polly_profile_id, aws_attestation)
            )
            profile = voice_profile(profile_id)
            if name == "fish" and (
                profile.provider != "fish_audio" or profile.engine != "s2.1-pro-free"
            ):
                raise ValueError("issue #289 caps Fish at its free profile")
            provider = (
                FishProvider(transport=lambda *_: ())
                if name == "fish"
                else PollyProvider(client=object())
            )
            for generation in range(1, generations + 1):
                request = _request(
                    run_id,
                    name,
                    row,
                    generation,
                    profile_id,
                    settings,
                    attestation,
                    budget_usd,
                )
                provider_input = provider.prepare_input(request)
                # Existing Polly policy is $32/M characters for audio plus speech marks.
                reserve = (
                    pricing_for(profile).estimate(request.text)
                    if name == "polly"
                    else 0.0
                )
                plan.append(
                    {
                        "provider": name,
                        "textId": row["id"],
                        "generation": generation,
                        "takeId": request.block_id,
                        "request": request,
                        "input": provider_input,
                        "reserve": reserve,
                    }
                )
    total = sum(row["reserve"] for row in plan)
    if total > budget_usd:
        raise ValueError(
            f"planned Polly upper bound ${total:.6f} exceeds ${budget_usd:.2f}"
        )
    return plan


def _pricing_record(profile_id: str) -> dict[str, Any]:
    policy = pricing_for(voice_profile(profile_id))
    return {
        "currency": "USD",
        "unit": policy.unit,
        "combinedAudioAndMarksUsdPerMillionCharacters": policy.usd_per_million,
        "policyVersion": policy.version,
        "sourceUrl": PRICE_SOURCE,
        "sourceChecked": "2026-10-24",
        "actualProviderCharge": "unknown until AWS billing data is checked",
    }


def run_study(
    output_dir: Path,
    *,
    corpus: dict[str, list[dict[str, str]]] | None = None,
    run_id: str | None = None,
    fish_profile_id: str = FISH_PROFILE_ID,
    polly_profile_id: str = JOANNA_PROFILE_ID,
    settings: SynthesisSettings | None = None,
    budget_usd: float = BUDGET_USD,
    fish_attestation: str | None = None,
    aws_attestation: str | None = None,
    provider_factory: Callable[[str, Path], SpeechSynthesisProvider] = _provider,
) -> dict[str, Any]:
    run_id = run_id or uuid.uuid4().hex
    corpus = load_corpus() if corpus is None else corpus
    settings = settings or SynthesisSettings()
    if fish_attestation != "fish_terms_accepted":
        raise ValueError("execution requires Fish data-policy attestation")
    if aws_attestation not in {"provider_terms_accepted", "opt_out_confirmed"}:
        raise ValueError("execution requires AWS data-policy attestation")
    plan = _plan(
        corpus,
        run_id,
        fish_profile_id,
        polly_profile_id,
        settings,
        budget_usd,
        fish_attestation,
        aws_attestation,
    )
    root = output_dir.expanduser().resolve()
    if root == ROOT.resolve() or ROOT.resolve() in root.parents:
        raise ValueError("study output must be outside the Git worktree")
    root.mkdir(parents=True, exist_ok=False)
    ledger: dict[str, Any] = {
        "currency": "USD",
        "budgetUsd": budget_usd,
        "reservedUsd": 0.0,
        "reservations": [],
    }
    _write_json(root / "ledger.json", ledger)
    outcomes = []

    for item in plan:
        name, take_id, request = item["provider"], item["takeId"], item["request"]
        take_dir, raw_path = root / take_id, root / take_id / "provider-response.sse"
        take_dir.mkdir()
        provider = provider_factory(name, raw_path)
        input_kind = "json" if request.profile.provider == "fish_audio" else "ssml"
        provider_input = item["input"]
        (take_dir / f"provider-input.{input_kind}").write_bytes(provider_input)
        reserve = item["reserve"]
        if reserve:
            ledger["reservedUsd"] = round(ledger["reservedUsd"] + reserve, 9)
            ledger["reservations"].append({"takeId": take_id, "reservedUsd": reserve})
            _write_json(root / "ledger.json", ledger)  # durable before the paid call
        request_record = {
            "takeId": take_id,
            "takeIdentity": identity_hash(
                {
                    "providerRequest": request.identity(
                        provider_input, provider.adapter_version
                    ),
                    "studyTakeId": take_id,
                }
            ),
            "blockId": request.block_id,
            "blockRevision": request.block_revision,
            "text": request.text,
            "textHash": sha256_bytes(request.text.encode()),
            "characters": len(request.text),
            "whitespaceWords": len(request.text.split()),
            "profile": asdict(request.profile),
            "settings": asdict(request.settings),
            "dataPolicyAttestation": request.data_policy_attestation,
            "maxCostUsd": request.max_cost_usd,
            "timingKinds": list(request.timing_kinds),
            "pricingPolicyVersion": request.pricing_policy_version,
            "providerInputFormat": input_kind,
            "providerInputBytes": len(provider_input),
            "providerInputHash": sha256_bytes(provider_input),
        }
        record: dict[str, Any] = {
            "recordVersion": "issue289-public-take/v1",
            "runId": run_id,
            "request": request_record,
            "status": "started",
            "startedAt": datetime.now(UTC).isoformat(),
            "cost": {
                "currency": "USD",
                "reservedUsd": reserve,
                "actualUsd": 0.0 if name == "fish" else None,
                "upperBoundUsd": reserve,
            },
        }
        _write_json(take_dir / "take.json", record)
        started = time.perf_counter()
        try:
            result = provider.synthesize(
                request
            )  # one call per generation; no retry loop
            raw = raw_path.read_bytes() if raw_path.exists() else None
            (take_dir / f"provider-input.{result.provider_input_format}").write_bytes(
                result.provider_input
            )
            (take_dir / "audio.pcm").write_bytes(result.audio_bytes)
            marks = [asdict(mark) for mark in result.timing_marks]
            record["native"] = {
                "audioFormat": result.audio_format,
                "sampleRate": result.sample_rate,
                "channels": result.channels,
                "audioBytes": len(result.audio_bytes),
                "audioSha256": hashlib.sha256(result.audio_bytes).hexdigest(),
                "timingMarkCount": len(marks),
                "timingMarksByKind": dict(Counter(mark["kind"] for mark in marks)),
                "timingMarks": marks,
                "requestIds": list(result.request_ids),
                "provenance": result.provenance,
                "fishChunks": _fish_chunks(raw) if raw is not None else None,
            }
            record["status"] = "succeeded"
        except Exception as error:
            files = getattr(error, "response_files", {})
            for filename, content in files.items() if isinstance(files, dict) else ():
                if (
                    filename == "provider-response.sse"
                    and isinstance(content, bytes)
                    and not raw_path.exists()
                ):
                    raw_path.write_bytes(content)
                if filename == "provider-input.json" and isinstance(content, bytes):
                    (take_dir / filename).write_bytes(content)
            record["status"], record["failure"] = "failed", _safe_error(error)
            if name == "fish" and raw_path.exists():
                record["fishChunks"] = _fish_chunks(raw_path.read_bytes())
        record["elapsedSeconds"] = round(time.perf_counter() - started, 6)
        record["completedAt"] = datetime.now(UTC).isoformat()
        _write_json(take_dir / "take.json", record)
        outcomes.append(
            {
                "takeId": take_id,
                "provider": name,
                "textId": item["textId"],
                "generation": item["generation"],
                "status": record["status"],
            }
        )

    summary = {
        "recordVersion": "issue289-public-study/v1",
        "runId": run_id,
        "denominators": {
            "perText": {
                "fish": 10,
                "polly": 3,
                "paired": len(corpus["pairedTexts"]),
                "fishOnly": len(corpus["fishOnlyTexts"]),
            },
            "perTake": {
                "fish": sum(row["provider"] == "fish" for row in outcomes),
                "polly": sum(row["provider"] == "polly" for row in outcomes),
                "total": len(outcomes),
            },
        },
        "takeCount": len(outcomes),
        "succeeded": sum(row["status"] == "succeeded" for row in outcomes),
        "failed": sum(row["status"] == "failed" for row in outcomes),
        "pollyCostUpperBound": {
            "currency": "USD",
            "reservedUsd": ledger["reservedUsd"],
            "actualUsd": None,
            "actualStatus": "unknown until AWS billing data is checked",
            "budgetUsd": budget_usd,
        },
        "pollyPricing": _pricing_record(polly_profile_id),
        "outcomes": outcomes,
    }
    _write_json(root / "study.json", summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="run 25 requests; default only prints the offline budget plan",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--budget-usd", type=float, default=BUDGET_USD)
    parser.add_argument(
        "--fish-profile", choices=(FISH_PROFILE_ID,), default=FISH_PROFILE_ID
    )
    parser.add_argument(
        "--polly-profile",
        choices=(MATTHEW_PROFILE_ID, JOANNA_PROFILE_ID),
        default=JOANNA_PROFILE_ID,
    )
    parser.add_argument("--rate", default=SynthesisSettings().rate)
    parser.add_argument("--fish-terms-accepted", action="store_true")
    parser.add_argument(
        "--aws-attestation", choices=("provider_terms_accepted", "opt_out_confirmed")
    )
    args = parser.parse_args(argv)
    run_id = uuid.uuid4().hex
    corpus, settings = load_corpus(), SynthesisSettings(rate=args.rate)
    fish_attestation = "fish_terms_accepted" if args.fish_terms_accepted else None
    try:
        plan = _plan(
            corpus,
            run_id,
            args.fish_profile,
            args.polly_profile,
            settings,
            args.budget_usd,
            fish_attestation,
            args.aws_attestation,
        )
        if not args.execute:
            print(
                json.dumps(
                    {
                        "mode": "dry-run",
                        "takeCount": len(plan),
                        "fishTakes": sum(row["provider"] == "fish" for row in plan),
                        "pollyTakes": sum(row["provider"] == "polly" for row in plan),
                        "fishTexts": 10,
                        "pollyTexts": 3,
                        "pollyReservedUpperBoundUsd": sum(
                            row["reserve"] for row in plan
                        ),
                        "budgetUsd": args.budget_usd,
                        "fishChargeCapUsd": 0,
                        "pollyPricing": _pricing_record(args.polly_profile),
                    },
                    indent=2,
                )
            )
            return 0
        if not args.fish_terms_accepted or not args.aws_attestation:
            raise ValueError(
                "execution requires --fish-terms-accepted and --aws-attestation"
            )
        result = run_study(
            args.output_dir,
            corpus=corpus,
            run_id=run_id,
            fish_profile_id=args.fish_profile,
            polly_profile_id=args.polly_profile,
            settings=settings,
            budget_usd=args.budget_usd,
            fish_attestation=fish_attestation,
            aws_attestation=args.aws_attestation,
        )
    except (ValueError, OSError) as error:
        print(json.dumps({"error": _safe_error(error)}), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"outputDir": str(args.output_dir.expanduser().resolve()), **result},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
