"""Explicit local recovery of retained Fish audio; no synthesis or retries.

Prepare a candidate with the shared MFA engine, then admit only with an
independently checked reference. The ordinary reference-text ASR port is unchanged.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from vera_word_timing.adapters.local_engines import (
    ENGINES,
    EngineConfig,
    _mfa_lock,
    run_engine,
)
from vera_word_timing.artifacts import with_id
from vera_word_timing.normalize import normalise_token
from vera_word_timing.ports import PortRefusal

from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.fish import FishError, _source_words, timing_marks
from vera_timeline_agent.narration.fish_stream import parse_timestamp_stream
from vera_timeline_agent.narration.models import canonical_json_bytes, sha256_bytes
from vera_timeline_agent.narration.normalize import Normalizer
from vera_timeline_agent.narration.recovery import (
    RecoveryError,
    RecoverySource,
    admit_local_acoustic_recovery,
    prepare_recovery_audio,
)


def _json(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def retained_source(
    cache: NarrationCache, asset_key: str, quarantine_key: str, document: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    """Verify the failed cache entry, matching quarantine and exact frozen source."""
    entry = cache.read("assets", asset_key, "asset.json")
    captured = cache.read("quarantine", quarantine_key, "response.json")
    if entry is None or captured is None:
        raise RecoveryError("failed asset or retained response is unavailable")
    asset = entry.metadata["asset"]
    if asset["status"] != "failed" or asset["provider"] != "fish_audio":
        raise RecoveryError("recovery requires an explicitly failed Fish asset")
    if asset_key != f"{asset['block_id']}/{asset['asset_id']}":
        raise RecoveryError("failed asset identity differs from cache key")
    if captured.metadata["synthesisKey"] != asset["request_hash"].removeprefix(
        "sha256:"
    ):
        raise RecoveryError("retained response belongs to a different request")
    blocks = [
        b for b in document["activeDraft"]["blocks"] if b.get("id") == asset["block_id"]
    ]
    if len(blocks) != 1:
        raise RecoveryError("one matching frozen narration block is required")
    block = blocks[0]
    if (
        block["version"] != asset["block_revision"]
        or sha256_bytes(block["text"].encode()) != asset["text_hash"]
    ):
        raise RecoveryError("frozen script differs from retained synthesis")
    response = captured.files["provider-response.sse"]
    raw, snapshots = parse_timestamp_stream([response])
    if len(raw) % 2 or not snapshots:
        raise RecoveryError("retained PCM or chunk inventory is incomplete")
    final = snapshots[-1]
    end = Fraction(str(final["offset"])) + Fraction(
        str(final["alignment"]["audio_duration"])
    )
    if abs(end - Fraction(len(raw) // 2, 44100)) > Fraction(1, 20):
        raise RecoveryError("retained alignment duration differs from audio")
    try:
        timing_marks(block["text"], snapshots, len(raw) // 2)
    except FishError as error:
        # All source-coverage checks precede this particular refusal. Other
        # defects require their own recovery proof, not permissive remapping.
        if str(error) != "Fish word alignment has non-increasing word starts":
            raise RecoveryError(
                "retained failure is not the supported tied-start case"
            ) from error
    else:
        raise RecoveryError("retained native timing is already usable")
    spans = _source_words(block["text"])
    expected = [
        (
            len(block["text"][:a].encode("utf-16-le")) // 2,
            len(block["text"][:b].encode("utf-16-le")) // 2,
        )
        for a, b in spans
    ]
    if expected != [(t["startOffset"], t["endOffset"]) for t in block["tokens"]]:
        raise RecoveryError("native source spans differ from frozen token inventory")
    return asset, block, response, raw


def prepare_candidate(
    source: RecoverySource, out: Path, config: EngineConfig
) -> dict[str, Any]:
    """Run the existing shared MFA engine on the known synthetic transcript."""
    prepared = prepare_recovery_audio(source.normalized_wav_bytes)
    (out / "engine.wav").write_bytes(prepared.wav_bytes)
    words: list[dict[str, Any]] = []
    for index, token in enumerate(source.block["tokens"]):
        pieces = normalise_token(token["value"], "en")
        if not pieces:
            raise RecoveryError("a frozen token has no supported spoken form")
        words.extend(
            {"i": index, "sub": sub, "text": text} for sub, text in enumerate(pieces)
        )
    spec = {
        "audio": "engine.wav",
        "segments": [
            {
                "id": "s000",
                "start": 0,
                "end": prepared.duration_samples / 16000,
                "words": words,
            }
        ],
    }
    _json(out / "segments.json", spec)
    model_home = config.mfa_home or Path.home() / ".local/share/vera/word-timing-v2"
    model_root = Path(config.mfa_env.get("MFA_ROOT_DIR", model_home / "cache/mfa"))
    isolated = out / "runtime"
    for kind, name in (
        ("acoustic", "english_us_arpa.zip"),
        ("dictionary", "english_us_arpa.dict"),
        ("g2p", "english_us_arpa.zip"),
    ):
        target = isolated / "cache/mfa/pretrained_models" / kind / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(model_root / "pretrained_models" / kind / name, target)
    command = config.mfa_command
    if not command:
        raise RecoveryError("configure VERA_MFA_COMMAND before local recovery")
    cmd = [
        *command,
        str(ENGINES / "mfa_engine.py"),
        "--segments",
        str(out / "segments.json"),
        "--audio-dir",
        str(out),
        "--out",
        str(out / "mfa.json"),
        "--variant",
        "english_us_arpa",
        "--jobs",
        "2",
    ]
    if sys.platform == "darwin":
        cmd = [
            "/usr/bin/sandbox-exec",
            "-p",
            "(version 1)(allow default)(deny network*)",
            *cmd,
        ]
    else:
        raise RecoveryError(
            "private recovery currently requires macOS network-denied execution"
        )
    env = {
        **config.mfa_env,
        "MFA_ROOT_DIR": str(isolated / "cache/mfa"),
        "VERA_MFA_HOME": str(isolated),
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
    }
    with _mfa_lock(model_home):
        run_engine(cmd, port="aligner", env=env, timeout=config.timeout_s)
    result = json.loads((out / "mfa.json").read_text())
    expected = [(w["i"], w["sub"]) for w in words]
    if [(w.get("i"), w.get("sub", 0)) for w in result["words"]] != expected:
        raise RecoveryError("MFA omitted, duplicated or reordered transcript units")
    mapped = []
    for index, token in enumerate(source.block["tokens"]):
        parts = [w for w in result["words"] if w["i"] == index]
        if not parts or any(w["status"] != "aligned" for w in parts):
            raise RecoveryError("MFA abstained on a required frozen word")
        mapped.append(
            {
                "tokenId": token["id"],
                "startMs": round(parts[0]["start"] * 1000),
                "endMs": round(parts[-1]["end"] * 1000),
            }
        )
    return with_id(
        {
            "schemaVersion": "synthetic-acoustic-candidate/v1",
            "audioHash": sha256_bytes(source.normalized_wav_bytes),
            "preparedAudioHash": prepared.prepared_hash,
            "textHash": sha256_bytes(source.block["text"].encode()),
            "blockId": source.block["id"],
            "blockRevision": source.block["version"],
            "engine": {"id": "A-MFA", "provenance": result["provenance"]},
            "words": mapped,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument(
        "--asset", required=True, help="failed cache key: block-id/asset-hash"
    )
    parser.add_argument("--quarantine", required=True)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args(argv)
    out = args.out.resolve()
    try:
        asset, block, response, raw = retained_source(
            NarrationCache(args.cache),
            args.asset,
            args.quarantine,
            json.loads(args.document.read_text()),
        )
        if not args.reference:
            out.mkdir(parents=True, exist_ok=False, mode=0o700)
            normalized = Normalizer().normalize_pcm(raw, sample_rate=44100, channels=1)
            (out / "normalized.wav").write_bytes(normalized.wav_bytes)
            _json(
                out / "normalization.json",
                {k: v for k, v in asdict(normalized).items() if k != "wav_bytes"},
            )
        wav = (out / "normalized.wav").read_bytes()
        info = json.loads((out / "normalization.json").read_text())
        prepared = prepare_recovery_audio(wav)
        source = RecoverySource(
            block=block,
            failed_asset_id=asset["asset_id"],
            request_hash=asset["request_hash"],
            response_hash=sha256_bytes(response),
            raw_audio_bytes=raw,
            raw_audio_format="pcm_s16le_44100_mono",
            normalized_wav_bytes=wav,
            prepared_wav_bytes=prepared.wav_bytes,
            sample_rate=48000,
            duration_samples=info["duration_samples"],
            normalization_provenance={
                **info,
                "sourceAudioHash": sha256_bytes(raw),
                "normalizedAudioHash": sha256_bytes(wav),
            },
        )
        if not args.reference:
            candidate = prepare_candidate(source, out, EngineConfig.from_env())
            _json(out / "candidate.json", candidate)
            print(
                "Local acoustic candidate prepared; "
                "admission pending independent review."
            )
            return 0
        candidate = json.loads((out / "candidate.json").read_text())
        result = admit_local_acoustic_recovery(
            source, candidate, json.loads(args.reference.read_text())
        )
        target = out / "admitted" / result.evidence["audio"]["cacheAssetId"]
        target.mkdir(parents=True, exist_ok=False)
        audio_path = target / result.evidence["audio"]["locator"]
        audio_path.parent.mkdir(parents=True)
        audio_path.write_bytes(wav)
        artifact_path = (
            target / result.evidence["verification"]["measurementArtifactLocator"]
        )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(result.artifact_bytes)
        _json(target / "boundary-evidence.json", result.evidence)
        print("Checked acoustic result published under a new immutable identity.")
        return 0
    except (ValueError, OSError, KeyError, PortRefusal) as error:
        # Private engine details remain in local engine logs.
        print(
            f"Local recovery refused ({type(error).__name__}); "
            "original evidence retained.",
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
