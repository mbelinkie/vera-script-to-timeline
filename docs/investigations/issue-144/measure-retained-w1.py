"""Offline numerical checks of published W1 PCM; no speech classifier/native calls."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import platform
import subprocess
import sys
import tempfile
import wave
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KIT = "out/issue149-workflow-reruns-20261002-kit-01"
RATE = 48_000
FRAME = 1_920
EXTENT = 399 * FRAME


def verified_bytes(path: str, records: dict[str, dict[str, object]]) -> bytes:
    row = records[path]
    published = ROOT / str(row["published"])
    payload = published.read_bytes()
    if hashlib.sha256(payload).hexdigest() != row["publishedSha256"]:
        raise ValueError(f"Published hash mismatch: {path}")
    decoded = gzip.decompress(payload) if row["compressed"] else payload
    if hashlib.sha256(decoded).hexdigest() != row["decodedPublishedSha256"]:
        raise ValueError(f"Decoded hash mismatch: {path}")
    return decoded


def wav_samples(payload: bytes) -> array[float]:
    with wave.open(io.BytesIO(payload), "rb") as stream:
        if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) != (
            RATE,
            1,
            2,
        ):
            raise ValueError("Expected retained PCM16 mono at 48 kHz")
        values = array("h", stream.readframes(stream.getnframes()))
    if sys.byteorder != "little":
        values.byteswap()
    return array("d", (value / 32768 for value in values))


def movie_samples(path: Path, channels: int, frames: int) -> list[array[float]]:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    streams = json.loads(probe.stdout)["streams"]
    audio = [item for item in streams if item["codec_type"] == "audio"]
    video = [item for item in streams if item["codec_type"] == "video"]
    if len(audio) != 1 or len(video) != 1:
        raise ValueError("Expected one complete audio/video stream")
    if (
        audio[0]["codec_name"] != "pcm_s16le"
        or audio[0]["sample_rate"] != str(RATE)
        or audio[0]["channels"] != channels
        or video[0]["avg_frame_rate"] != "25/1"
        or int(video[0]["nb_frames"]) != frames
    ):
        raise ValueError("Retained stream facts differ")
    decoded = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "f32le",
            "-c:a",
            "pcm_f32le",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    values = array("f", decoded.stdout)
    if sys.byteorder != "little":
        values.byteswap()
    if len(values) != frames * FRAME * channels:
        raise ValueError("Incomplete decoded output")
    return [array("d", values[channel::channels]) for channel in range(channels)]


def solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    augmented = [[*row, value] for row, value in zip(matrix, rhs, strict=True)]
    for column in range(len(rhs)):
        pivot = max(
            range(column, len(rhs)), key=lambda row: abs(augmented[row][column])
        )
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        if abs(divisor) < 1e-12:
            raise ValueError("Route attribution is singular")
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(len(rhs)):
            if row != column:
                multiplier = augmented[row][column]
                augmented[row] = [
                    value - multiplier * pivot_value
                    for value, pivot_value in zip(
                        augmented[row], augmented[column], strict=True
                    )
                ]
    return [row[-1] for row in augmented]


def fit(routes: list[array[float]], program: array[float]) -> list[float]:
    gram = [
        [math.fsum(x * y for x, y in zip(left, right, strict=True)) for right in routes]
        for left in routes
    ]
    rhs = [
        math.fsum(x * y for x, y in zip(route, program, strict=True))
        for route in routes
    ]
    return solve(gram, rhs)


def measure(
    routes: list[array[float]], program: array[float], gains: list[float]
) -> dict[str, float]:
    residual = array(
        "d",
        (
            actual
            - math.fsum(
                gain * route[index] for gain, route in zip(gains, routes, strict=True)
            )
            for index, actual in enumerate(program)
        ),
    )
    window = RATE // 50
    energy = math.fsum(value * value for value in residual[:window])
    peak = energy
    for index in range(window, len(residual)):
        energy += residual[index] ** 2 - residual[index - window] ** 2
        peak = max(peak, energy)
    return {
        "programRms": math.sqrt(
            math.fsum(value * value for value in program) / len(program)
        ),
        "residualRms": math.sqrt(
            math.fsum(value * value for value in residual) / len(residual)
        ),
        "maximumSliding20msResidualRms": math.sqrt(peak / window),
    }


def main(output: Path) -> None:
    publication = json.loads(
        (ROOT / "docs/investigations/issue-141/publication-manifest.json").read_text()
    )
    records = {row["source"]: row for row in publication["records"]}
    used: list[str] = []

    def load(name: str) -> bytes:
        path = f"{KIT}/{name}"
        used.append(path)
        return verified_bytes(path, records)

    manifest = json.loads(load("media/manifest.json"))
    charlie = next(
        word
        for word in manifest["files"]["a1_alpha.wav"]["words"]
        if word["word"] == "charlie"
    )
    support_start, support_end = charlie["start_sample"], charlie["end_sample"]
    half_end = support_start + (support_end - support_start) // 2
    a1, a2, a3 = [
        wav_samples(load(f"media/{name}.wav"))
        for name in ("a1_alpha", "a2_numbers", "a3_bed")
    ]
    full = [route[:EXTENT] for route in (a1, a2, a3)]
    cut_a1 = array("d", [0.0]) * EXTENT
    cut_a1[: 99 * FRAME] = a1[: 99 * FRAME]
    cut_a1[100 * FRAME : 349 * FRAME] = a1[150 * FRAME : 399 * FRAME]
    cut_routes = [cut_a1, full[1], full[2]]
    with tempfile.TemporaryDirectory(prefix="vera144-retained-w1-") as directory:
        root = Path(directory)
        movies: dict[str, list[array[float]]] = {}
        for name in ("W1-picture-only-cut-01", "W1-linked-cut-01", "W1-disabled-A1-01"):
            path = root / f"{name}.mov"
            path.write_bytes(load(f"renders/{name}.mov"))
            movies[name] = movie_samples(path, 2, 399)
        base = root / "base.mov"
        base.write_bytes(load("media/base.mov"))
        if movie_samples(base, 1, 400)[0] != a1:
            raise ValueError("Embedded source PCM differs from published narration PCM")
    gains = [fit(full, channel) for channel in movies["W1-picture-only-cut-01"]]
    findings: dict[str, object] = {}
    for name, routes in (
        ("W1-picture-only-cut-01", full),
        ("W1-linked-cut-01", cut_routes),
        ("W1-disabled-A1-01", full),
    ):
        findings[name] = [
            measure(routes, channel, gain)
            for channel, gain in zip(movies[name], gains, strict=True)
        ]
    injected = [array("d", channel) for channel in movies["W1-linked-cut-01"]]
    # Synthetic adversarial overlay on retained PCM, not a new native case.
    for channel, sign in zip(injected, (1, -1), strict=True):
        for index, value in enumerate(a1[support_start:half_end]):
            channel[100 * FRAME + index] += sign * value
    findings["syntheticHalfCharlieOppositeChannelOverlay"] = [
        measure(cut_routes, channel, gain)
        for channel, gain in zip(injected, gains, strict=True)
    ]
    # Boundary probes expose the sensitivity limit. These are deliberately
    # adulterated arrays, not additional native renders or absence verdicts.
    boundary_cases: dict[str, object] = {}
    quarter = (support_end - support_start) // 4
    for name, start, end, scale in (
        ("quarterHead", support_start, support_start + quarter, 1.0),
        ("quarterTail", support_end - quarter, support_end, 1.0),
        ("headToNextFrame", support_start, (support_start // FRAME + 1) * FRAME, 1.0),
        ("tailFromLastFrame", support_end // FRAME * FRAME, support_end, 1.0),
        ("halfAtThreePercent", support_start, half_end, 0.03),
        ("halfAtTwoPointFivePercent", support_start, half_end, 0.025),
        ("halfAtTwoPercent", support_start, half_end, 0.02),
        ("halfAtOnePointFivePercent", support_start, half_end, 0.015),
        ("tenSamples", support_start, support_start + 10, 1.0),
    ):
        channels = [array("d", channel) for channel in movies["W1-linked-cut-01"]]
        for channel, sign in zip(channels, (1, -1), strict=True):
            for index, value in enumerate(a1[start:end]):
                channel[100 * FRAME + index] += sign * scale * value
        metrics = [
            measure(cut_routes, channel, gain)
            for channel, gain in zip(channels, gains, strict=True)
        ]
        boundary_cases[name] = {
            "supportSliceSamples": [start, end],
            "overlayScale": scale,
            "measurements": metrics,
            "passesProposedNumericalLimitsDespiteInjectedResidue": all(
                row["residualRms"] <= 0.0004
                and row["maximumSliding20msResidualRms"] <= 0.006
                for row in metrics
            ),
        }
    result = {
        "schemaVersion": "issue-144-retained-w1-measurements/v1",
        "purpose": "Offline numerical reconstruction, not a speech-deletion classifier",
        "nativeActions": 0,
        "analysisCodeSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "ffmpeg": subprocess.run(
            ["ffmpeg", "-version"], check=True, capture_output=True, text=True
        ).stdout.splitlines()[0],
        "sampleRate": RATE,
        "samplesPerChannel": EXTENT,
        "channels": 2,
        "targetSupportSamples": [support_start, support_end],
        "oppositeChannelOverlayCancelsWhenAveraged": array(
            "d",
            (
                (left + right) / 2
                for left, right in zip(injected[0], injected[1], strict=True)
            ),
        )
        == movies["W1-linked-cut-01"][0],
        "gainsFromUnchangedPictureOnlyAudio": gains,
        "inputs": {path: records[path]["decodedPublishedSha256"] for path in used},
        "measurements": findings,
        "syntheticBoundaryProbes": boundary_cases,
        "proposedNumericalLimits": {"wholeRms": 0.0004, "maximum20msRms": 0.006},
        "qualification": (
            "Numerical limits cannot rule out arbitrarily quiet/short residue. "
            "They must not become a general speech absence classifier; require "
            "frozen source/support provenance and complete supported route evidence."
        ),
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "measurements": findings,
                "boundaryProbes": boundary_cases,
                "gains": gains,
            }
        )
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
