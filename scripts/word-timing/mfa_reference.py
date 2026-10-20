#!/usr/bin/env python3
"""Independent MFA reference for #182 measured boundaries (local only).

CI never runs this script.

Aligns a normalized narration WAV to its script words with the repository's
existing MfaAligner and compares the Montreal Forced Aligner's word intervals to
the measured onsets and audible ends in a ``narration-measurement/v1`` artifact:

    VERA_MFA_COMMAND="micromamba run -n mfa python" \\
    uv run python scripts/word-timing/mfa_reference.py \\
        --measurement DIR/narration-measurements/ASSET.measurement.json \\
        --wav narration.wav --out mfa-report.json

If VERA_MFA_COMMAND is unset the micromamba env ``mfa`` is used
(MAMBA_ROOT_PREFIX defaults to ~/.local/share/micromamba). Pass ``--mfa-result
FILE`` (an ``alignment-artifact/v1`` JSON) to compare against a recorded MFA run
without running MFA.

MFA only sees the audio and the script words.  Measured onsets are passed to
its VAD stage purely to assign words to speech segments; MFA decides the times.
Corpus gate: p95 absolute error <= 150 ms for onsets (and for measured ends).
"""

from __future__ import annotations

import argparse
import array
import hashlib
import io
import json
import math
import os
import sys
import tempfile
import wave
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

GATE_P95_MS = 150.0
SCHEMA = "mfa-reference-comparison/v1"


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Nearest-rank percentile; None for an empty sample."""

    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def _stats(errors: list[dict[str, Any]]) -> dict[str, Any]:
    values = [row["absErrorMs"] for row in errors]
    p50, p95 = percentile(values, 0.50), percentile(values, 0.95)
    return {
        "count": len(values),
        "p50Ms": p50,
        "p95Ms": p95,
        "maxMs": max(values) if values else None,
        "pass": p95 is not None and p95 <= GATE_P95_MS,
        "errors": errors,
    }


def compare(
    tokens: Sequence[dict[str, Any]],
    mfa_words: Sequence[tuple[float, float] | None],
) -> dict[str, Any]:
    """Compare measured tokens to MFA intervals (ms).

    ``tokens``: dicts with ``tokenId``, ``quotedText``, ``onsetMs`` and
    ``audibleEndMs`` (None where the measurement abstained).  ``mfa_words``
    aligns by position; None means MFA could not align that word.
    Absent measured ends are not errors: they are reported as abstentions.
    """

    if len(tokens) != len(mfa_words):
        raise ValueError("one MFA interval (or None) is required per token")
    onset_errors: list[dict[str, Any]] = []
    end_errors: list[dict[str, Any]] = []
    unaligned: list[str] = []
    abstained: list[str] = []
    for token, interval in zip(tokens, mfa_words, strict=True):
        if interval is None:
            unaligned.append(token["tokenId"])
            continue
        start, end = interval
        onset_errors.append(
            {
                "tokenId": token["tokenId"],
                "quotedText": token["quotedText"],
                "mfaMs": start,
                "measuredMs": token["onsetMs"],
                "absErrorMs": abs(token["onsetMs"] - start),
            }
        )
        if token["audibleEndMs"] is None:
            abstained.append(token["tokenId"])
            continue
        end_errors.append(
            {
                "tokenId": token["tokenId"],
                "quotedText": token["quotedText"],
                "mfaMs": end,
                "measuredMs": token["audibleEndMs"],
                "absErrorMs": abs(token["audibleEndMs"] - end),
            }
        )
    onset, ends = _stats(onset_errors), _stats(end_errors)
    return {
        "schemaVersion": SCHEMA,
        "gateP95Ms": GATE_P95_MS,
        "onset": onset,
        "audibleEnd": ends,
        "mfaUnaligned": unaligned,
        "audibleEndAbstained": abstained,
        "corpusGatePass": onset["pass"] and (ends["pass"] or not end_errors),
    }


def tokens_from_artifact(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    rate = int(artifact["asset"]["sampleRate"])
    rows = []
    for row in artifact["tokens"]:
        end = row["audibleEndSamples"]
        rows.append(
            {
                "tokenId": row["tokenId"],
                "quotedText": row["quotedText"],
                "onsetMs": row["onsetSamples"] * 1000 / rate,
                "audibleEndMs": None if end is None else end * 1000 / rate,
            }
        )
    return rows


def downsample_16k(wav_bytes: bytes) -> tuple[bytes, int]:
    """48 kHz mono 16-bit -> 16 kHz (boxcar mean of three); returns (wav, frames)."""

    with wave.open(io.BytesIO(wav_bytes)) as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise ValueError("mono 16-bit WAV required")
        rate = handle.getframerate()
        samples = array.array("h")
        samples.frombytes(handle.readframes(handle.getnframes()))
    if sys.byteorder == "big":
        samples.byteswap()
    if rate != 48_000:
        raise ValueError("48 kHz WAV required")
    out = array.array(
        "h",
        (
            (samples[i] + samples[i + 1] + samples[i + 2]) // 3
            for i in range(0, len(samples) - 2, 3)
        ),
    )
    if sys.byteorder == "big":
        out.byteswap()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16_000)
        writer.writeframes(out.tobytes())
    return buffer.getvalue(), len(out)


def run_mfa(
    artifact: dict[str, Any], wav_bytes: bytes
) -> tuple[list[tuple[float, float] | None], dict[str, Any]]:
    from vera_word_timing.adapters.local_engines import EngineConfig, MfaAligner
    from vera_word_timing.artifacts import (
        AudioRef,
        RecognizerInfo,
        Token,
        recognition_artifact,
    )
    from vera_word_timing.ports import ProjectPolicy

    config = EngineConfig.from_env()
    if not config.mfa_command:
        config = replace(
            config,
            mfa_command=("micromamba", "run", "-n", "mfa", "python"),
            mfa_env={
                "MAMBA_ROOT_PREFIX": os.environ.get(
                    "MAMBA_ROOT_PREFIX",
                    str(Path.home() / ".local/share/micromamba"),
                ),
                **config.mfa_env,
            },
        )
    wav16, frames = downsample_16k(wav_bytes)
    rate = int(artifact["asset"]["sampleRate"])
    rows = artifact["tokens"]
    with tempfile.TemporaryDirectory(prefix="vera-mfa-ref-") as directory:
        path = Path(directory) / "narration16k.wav"
        path.write_bytes(wav16)
        audio = AudioRef(
            path=path,
            original_hash="sha256:" + hashlib.sha256(wav_bytes).hexdigest(),
            sample_rate=16_000,
            duration_samples=frames,
        )
        tokens = []
        for index, row in enumerate(rows):
            start = row["onsetSamples"] / rate
            stop = (
                rows[index + 1]["onsetSamples"] / rate
                if index + 1 < len(rows)
                else artifact["asset"]["durationSamples"] / rate
            )
            tokens.append(Token(row["quotedText"], "word", start, stop, "segment"))
        recognition = recognition_artifact(
            audio,
            RecognizerInfo("reference-text", "vera", "script", "1"),
            tokens,
            language="en",
            consent_policy=None,
        )
        alignment = MfaAligner(config).align(audio, recognition, policy=ProjectPolicy())
    return intervals_from_alignment(alignment, len(rows)), alignment["identity"][
        "aligner"
    ]


def intervals_from_alignment(
    alignment: dict[str, Any], token_count: int
) -> list[tuple[float, float] | None]:
    spans: dict[int, list[dict[str, Any]]] = {}
    for word in alignment["words"]:
        spans.setdefault(word["tokenIndex"], []).append(word)
    result: list[tuple[float, float] | None] = []
    for index in range(token_count):
        parts = spans.get(index, [])
        if not parts or any(p["startMs"] is None or p["endMs"] is None for p in parts):
            result.append(None)
        else:
            result.append((float(parts[0]["startMs"]), float(parts[-1]["endMs"])))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mfa-result", type=Path, default=None)
    options = parser.parse_args(argv)
    artifact = json.loads(options.measurement.read_text(encoding="utf-8"))
    tokens = tokens_from_artifact(artifact)
    provenance: dict[str, Any] | None = None
    if options.mfa_result is not None:
        alignment = json.loads(options.mfa_result.read_text(encoding="utf-8"))
        intervals = intervals_from_alignment(alignment, len(tokens))
        provenance = alignment.get("identity", {}).get("aligner")
    else:
        intervals, provenance = run_mfa(artifact, options.wav.read_bytes())
    report = compare(tokens, intervals)
    report["aligner"] = provenance
    report["asset"] = artifact["asset"]["cacheAssetId"]
    options.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        f"onset p50={report['onset']['p50Ms']} p95={report['onset']['p95Ms']} ms; "
        f"end p50={report['audibleEnd']['p50Ms']} "
        f"p95={report['audibleEnd']['p95Ms']} ms; "
        f"gate(p95<={GATE_P95_MS:.0f}) pass={report['corpusGatePass']}"
    )
    return 0 if report["corpusGatePass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
