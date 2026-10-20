#!/usr/bin/env python3
"""Independent MFA reference for #182 measured boundaries (local only).

CI never runs this script.

EVALUATION-ONLY independent reference: aligns a narration WAV to the exact
script words by running the MFA engine (adapters/engines/mfa_engine.py)
directly (the production MfaAligner port refuses reference text by design,
D-P009), then compares the Montreal Forced Aligner's word intervals to
the measured onsets and audible ends in a ``narration-measurement/v1`` artifact:

    VERA_MFA_COMMAND="micromamba run -n mfa python" \\
    uv run python scripts/word-timing/mfa_reference.py \\
        --measurement DIR/narration-measurements/ASSET.measurement.json \\
        --wav narration.wav --out mfa-report.json

If VERA_MFA_COMMAND is unset the micromamba env ``mfa`` is used
(MAMBA_ROOT_PREFIX defaults to ~/.local/share/micromamba). Pass ``--mfa-result
FILE`` (an ``alignment-artifact/v1`` JSON) to compare against a recorded MFA run
without running MFA.

MFA only sees the audio and the script words (one segment spanning the row);
it never sees the measured times.
Inputs are bound: the WAV's sha256 must equal the measurement artifact's asset
audio hash, and a recorded ``--mfa-result`` must record that same audio hash.
Corpus gate: p95 absolute error <= 150 ms for onsets (and for measured ends),
and every token with a measured onset must be aligned by MFA (100% coverage).
"""

from __future__ import annotations

import argparse
import array
import hashlib
import io
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import wave
from collections.abc import Sequence
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
        "onsetCoverage": {
            "aligned": len(onset_errors),
            "total": len(tokens),
            "complete": not unaligned,
        },
        "audibleEndAbstained": abstained,
        # Every token carries a measured onset, so an unaligned token is an
        # unverified onset and fails the gate.
        "corpusGatePass": bool(
            onset["pass"] and not unaligned and (ends["pass"] or not end_errors)
        ),
    }


def sha256_hash(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _same_hash(left: object, right: str) -> bool:
    if not isinstance(left, str):
        return False
    return left.removeprefix("sha256:") == right.removeprefix("sha256:")


def bind_inputs(
    artifact: dict[str, Any],
    wav_bytes: bytes,
    alignment: dict[str, Any] | None = None,
) -> None:
    """Refuse unless the WAV (and a recorded MFA result) are the measured audio."""

    expected = artifact.get("asset", {}).get("audioHash")
    if not isinstance(expected, str):
        raise ValueError("measurement artifact records no asset audio hash")
    actual = sha256_hash(wav_bytes)
    if not _same_hash(expected, actual):
        raise ValueError(
            f"WAV sha256 {actual} differs from the measurement artifact's "
            f"asset audio hash {expected}"
        )
    if alignment is not None:
        recorded = alignment.get("identity", {}).get("audio", {}).get("hash")
        if not _same_hash(recorded, actual):
            raise ValueError(
                f"recorded MFA result audio identity {recorded!r} is not the "
                f"measured WAV {actual}"
            )


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
        width = handle.getsampwidth()
        if handle.getnchannels() != 1 or width not in (2, 3):
            raise ValueError("mono 16-bit or 24-bit WAV required")
        rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    if width == 3:
        # VERA's normalized assets are PCM-24; reduce to 16-bit for MFA input.
        samples = array.array(
            "h",
            (
                int.from_bytes(raw[i : i + 3], "little", signed=True) >> 8
                for i in range(0, len(raw) - len(raw) % 3, 3)
            ),
        )
        if sys.byteorder == "big":
            samples.byteswap()
    else:
        samples = array.array("h")
        samples.frombytes(raw)
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


ENGINE = (
    Path(__file__).resolve().parents[2]
    / "packages/word-timing/src/vera_word_timing/adapters/engines/mfa_engine.py"
)
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")


def spoken_pieces(text: str) -> list[str]:
    """Lower-case word pieces MFA will see for one script token (hyphens split)."""

    return _WORD.findall(text.lower().replace("\u2019", "'"))


def build_segments(
    artifact: dict[str, Any], audio_name: str, frames: int
) -> dict[str, Any]:
    """One segment spanning the whole row with the exact script words."""

    words = []
    for index, row in enumerate(artifact["tokens"]):
        pieces = spoken_pieces(row["quotedText"])
        for sub, piece in enumerate(pieces):
            words.append(
                {"i": index, "text": piece, **({"sub": sub} if len(pieces) > 1 else {})}
            )
    return {
        "audio": audio_name,
        "offsetSec": 0.0,
        "segments": [
            {"id": "s000", "start": 0.0, "end": frames / 16_000, "words": words}
        ],
    }


def mfa_command_and_env() -> tuple[list[str], dict[str, str]]:
    command = shlex.split(os.environ.get("VERA_MFA_COMMAND", ""))
    env = {
        k: v for k in ("MAMBA_ROOT_PREFIX", "VERA_MFA_HOME") if (v := os.environ.get(k))
    }
    if root := os.environ.get("VERA_MFA_ROOT_DIR"):
        env["MFA_ROOT_DIR"] = root
    if not command:
        micromamba = shutil.which("micromamba") or str(
            Path.home() / ".local/bin/micromamba"
        )
        command = [micromamba, "run", "-n", "mfa", "python"]
        env.setdefault(
            "MAMBA_ROOT_PREFIX", str(Path.home() / ".local/share/micromamba")
        )
    return command, env


def expected_units(artifact: dict[str, Any]) -> dict[tuple[int, int], str]:
    """Every (token index, sub-word index) -> piece the aligner must align."""

    units: dict[tuple[int, int], str] = {}
    for index, row in enumerate(artifact["tokens"]):
        for sub, piece in enumerate(spoken_pieces(row["quotedText"])):
            units[(index, sub)] = piece
    return units


def _unit_key(
    index: object, sub: object, units: dict[tuple[int, int], str]
) -> tuple[int, int]:
    if (
        not isinstance(index, int)
        or isinstance(index, bool)
        or not isinstance(sub, int)
        or isinstance(sub, bool)
        or (index, sub) not in units
    ):
        raise ValueError(
            f"aligner unit (token {index!r}, sub {sub!r}) is not part of the "
            "measured script tokens"
        )
    return (index, sub)


def _collect_intervals(
    artifact: dict[str, Any],
    spans: dict[tuple[int, int], tuple[float, float] | None],
    units: dict[tuple[int, int], str],
) -> list[tuple[float, float] | None]:
    """A token is aligned only if every one of its sub-word pieces is."""

    out: list[tuple[float, float] | None] = []
    for index, _token in enumerate(artifact["tokens"]):
        keys = sorted(key for key in units if key[0] == index)
        parts = [spans.get(key) for key in keys]
        if not keys or any(part is None for part in parts):
            out.append(None)
        else:
            present = [part for part in parts if part is not None]
            out.append((present[0][0], present[-1][1]))
    return out


def intervals_from_engine(
    result: dict[str, Any], artifact: dict[str, Any]
) -> list[tuple[float, float] | None]:
    """Map engine rows (seconds) to one (startMs, endMs) per script token.

    Rows must be exactly units of the measured script tokens; a token whose
    pieces are not all aligned (a missing, failed or unbounded piece) is
    unaligned and fails the coverage gate.
    """

    units = expected_units(artifact)
    spans: dict[tuple[int, int], tuple[float, float] | None] = {}
    for row in result["words"]:
        key = _unit_key(row.get("i"), row.get("sub", 0), units)
        if key in spans:
            raise ValueError(f"duplicate aligner unit {key}")
        ok = (
            row.get("status") == "aligned"
            and row.get("start") is not None
            and row.get("end") is not None
        )
        spans[key] = (row["start"] * 1000.0, row["end"] * 1000.0) if ok else None
    return _collect_intervals(artifact, spans, units)


def run_mfa(
    artifact: dict[str, Any], wav_bytes: bytes
) -> tuple[list[tuple[float, float] | None], dict[str, Any]]:
    """Run the MFA engine directly on the exact script text (evaluation-only).

    Deliberately bypasses the production MfaAligner port, which refuses
    reference text (D-P009); this script is the evaluation-only exception.
    """

    command, extra_env = mfa_command_and_env()
    wav16, frames = downsample_16k(wav_bytes)
    with tempfile.TemporaryDirectory(prefix="vera-mfa-ref-") as directory:
        audio_dir = Path(directory) / "audio"
        audio_dir.mkdir()
        (audio_dir / "narration16k.wav").write_bytes(wav16)
        seg_file, out = Path(directory) / "segments.json", Path(directory) / "r.json"
        seg_file.write_text(
            json.dumps(build_segments(artifact, "narration16k.wav", frames))
        )
        cmd = [
            *command,
            str(ENGINE),
            "--segments",
            str(seg_file),
            "--audio-dir",
            str(audio_dir),
            "--out",
            str(out),
            "--variant",
            "english_us_arpa",
            "-j",
            "1",
        ]
        done = subprocess.run(
            cmd,
            env={**os.environ, **extra_env},
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if done.returncode != 0 or not out.exists():
            raise RuntimeError(
                f"MFA engine failed ({done.returncode}): {done.stderr[-2000:]}"
            )
        result = json.loads(out.read_text())
    provenance = {
        "kind": "evaluation-only independent reference (exact script text)",
        "variant": result.get("variant"),
        **result.get("provenance", {}),
    }
    return intervals_from_engine(result, artifact), provenance


def intervals_from_alignment(
    alignment: dict[str, Any], artifact: dict[str, Any]
) -> list[tuple[float, float] | None]:
    """Map a recorded alignment/v1 result to one interval per script token.

    The recorded words must be the measurement's own script words: each unit's
    (tokenIndex, sub) and text must match the expected piece.  A token is
    aligned only when every one of its pieces is present with bounds.
    """

    units = expected_units(artifact)
    spans: dict[tuple[int, int], tuple[float, float] | None] = {}
    for word in alignment["words"]:
        key = _unit_key(word.get("tokenIndex"), word.get("sub"), units)
        if key in spans:
            raise ValueError(f"duplicate aligner unit {key}")
        if word.get("text") != units[key]:
            raise ValueError(
                f"recorded unit {key} text {word.get('text')!r} is not the "
                f"measured script word {units[key]!r}"
            )
        ok = (
            word.get("status") != "unaligned"
            and word.get("startMs") is not None
            and word.get("endMs") is not None
        )
        spans[key] = (float(word["startMs"]), float(word["endMs"])) if ok else None
    return _collect_intervals(artifact, spans, units)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mfa-result", type=Path, default=None)
    options = parser.parse_args(argv)
    artifact = json.loads(options.measurement.read_text(encoding="utf-8"))
    tokens = tokens_from_artifact(artifact)
    wav_bytes = options.wav.read_bytes()
    provenance: dict[str, Any] | None = None
    try:
        if options.mfa_result is not None:
            alignment = json.loads(options.mfa_result.read_text(encoding="utf-8"))
            bind_inputs(artifact, wav_bytes, alignment)
            intervals = intervals_from_alignment(alignment, artifact)
            provenance = alignment.get("identity", {}).get("aligner")
        else:
            bind_inputs(artifact, wav_bytes)
            intervals, provenance = run_mfa(artifact, wav_bytes)
    except ValueError as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    report = compare(tokens, intervals)
    report["aligner"] = provenance
    report["evaluationOnly"] = True
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
