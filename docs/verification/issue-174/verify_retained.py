"""Read-only independent hash, sampling and synchronization evidence checks."""

import argparse
import hashlib
import io
import json
import math
import subprocess
import wave
from fractions import Fraction
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def fraction(value: dict[str, int]) -> Fraction:
    return Fraction(value["numerator"], value["denominator"])


def decode_ordinals(path: Path) -> tuple[int, ...]:
    """Re-decode the retained hashed picture without trusting case.json."""
    raw = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-fps_mode",
            "passthrough",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    frame_size = 64 * 64 * 3
    if len(raw) % frame_size:
        raise AssertionError(f"partial decoded frame in {path}")
    ordinals: list[int] = []
    for start in range(0, len(raw), frame_size):
        frame = raw[start : start + frame_size]
        value = 0
        for bit in range(12):
            row, column = divmod(bit, 4)
            x = 4 + column * 15 + 5
            y = 4 + row * 14 + 5
            position = (y * 64 + x) * 3
            if sum(frame[position : position + 3]) >= 384:
                value |= 1 << bit
        ordinals.append(value)
    return tuple(ordinals)


def decode_audio_samples(path: Path, stream_index: int) -> tuple[int, ...]:
    raw = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(path),
            "-map",
            f"0:{stream_index}",
            "-vn",
            "-sn",
            "-dn",
            "-c:a",
            "pcm_s24le",
            "-f",
            "wav",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    with wave.open(io.BytesIO(raw), "rb") as stream:
        if stream.getsampwidth() != 3:
            raise AssertionError("retained PCM source is not 24-bit")
        channels = stream.getnchannels()
        payload = stream.readframes(stream.getnframes())
    stride = channels * 3
    return tuple(
        int.from_bytes(payload[offset : offset + 3], "little", signed=True)
        for offset in range(0, len(payload), stride)
    )


def read_wav_samples(path: Path) -> tuple[int, int, tuple[int, ...]]:
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 3:
            raise AssertionError("retained sidecar is not 24-bit")
        channels = stream.getnchannels()
        payload = stream.readframes(stream.getnframes())
        stride = channels * 3
        samples = tuple(
            int.from_bytes(payload[offset : offset + 3], "little", signed=True)
            for offset in range(0, len(payload), stride)
        )
        return stream.getframerate(), channels, samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    root = parser.parse_args().directory.resolve()
    record = json.loads((root / "qualification.json").read_bytes())
    checked = 0
    maximum_residual, maximum_drift = 0.0, 0.0
    for case in record["cases"]:
        assert (
            digest(root / case["case"] / "case.json")
            == (record["caseRecordHashes"][case["case"]])
        )
        for path_key, hash_key in (
            ("source", "sourceHash"),
            ("receipt", "receiptHash"),
            ("video", "videoHash"),
            ("audioPath", "audioHash"),
            ("operatorPair", "operatorPairHash"),
        ):
            if path_key in case:
                assert digest(root / case[path_key]) == case[hash_key], case["case"]
                checked += 1
        receipt = json.loads((root / case["receipt"]).read_bytes())
        source_rate = fraction(case["descriptor"]["logicalSourceBounds"]["frameRate"])
        target = fraction(receipt["binding"]["targetRate"])
        duration = fraction(case["requestedRange"]["duration"])
        origin = case["descriptor"]["sourceFrameMap"]["packageFrameZeroLogicalFrame"]
        pre_handle = fraction(case["requestedRange"]["preHandle"])
        post_handle = fraction(case["requestedRange"]["postHandle"])
        start = (
            Fraction(case["requestedRange"]["sourceInFrame"] - origin, 1) / source_rate
            - pre_handle
        )
        end = (
            Fraction(case["requestedRange"]["sourceInFrame"] - origin, 1) / source_rate
            + duration
            + post_handle
        )
        expected = [
            math.floor((start + Fraction(j, 1) / target) * source_rate)
            for j in range(math.ceil((end - start) * target))
        ]
        assert case["expectedSelectedOrdinals"] == expected
        actual = decode_ordinals(root / case["video"])
        if receipt["binding"]["mode"] == "derived_cfr":
            assert actual == tuple(expected), case["case"]
            selected = actual
        else:
            decoded_count = case["descriptor"]["sourceFrameMap"][
                "decodedPackageFrameCount"
            ]
            assert actual == tuple(range(decoded_count)), case["case"]
            selected = tuple(actual[index] for index in expected)
        assert case["decodedSelectedOrdinals"] == list(selected)
        assert all(
            Fraction(index, 1) / source_rate
            <= start + j / target
            < Fraction(index + 1, 1) / source_rate
            and start + j / target < end
            for j, index in enumerate(expected)
        )
        assert (
            Fraction(0)
            <= fraction(case["geometry"]["sourceCoverSurplus"])
            < 1 / source_rate
        )
        assert (
            Fraction(0)
            <= fraction(case["geometry"]["terminalQuantization"])
            < 1 / target
        )
        assert case["independentRepeatVideoHash"] == case["videoHash"]
        if case["audio"]:
            audio = case["audio"]
            assert fraction(audio["endpointError"]) <= Fraction(1, 48000)
            mapping = case["descriptor"]["sourceFrameMap"]["sourceAudioStreamMappings"][
                0
            ]
            sample_rate = mapping["sampleRate"]
            picture_origin = fraction(
                case["descriptor"]["sourceFrameMap"]["packageVideoPtsOrigin"]
            )
            audio_origin = fraction(mapping["packagePtsOrigin"])
            expected_first = math.ceil(
                (picture_origin + start - audio_origin) * sample_rate
            )
            expected_exclusive = math.ceil(
                (picture_origin + end - audio_origin) * sample_rate
            )
            assert audio["sourceFirstSample"] == expected_first
            assert audio["sourceExclusiveSample"] == expected_exclusive
            assert audio["decodedSamples"] == (
                audio["resampledExclusiveSample"] - audio["resampledFirstSample"]
            )
            boundary_offset = fraction(audio["boundaryOffset"])
            delivered_time = fraction(audio["deliveredTimeAtFirstSample"])
            expected_delivered_time = boundary_offset + (
                start if receipt["binding"]["mode"] == "verified_reuse" else Fraction(0)
            )
            assert delivered_time == expected_delivered_time
            assert case["independentRepeatAudioHash"] == case["audioHash"]
            source_stream = next(
                stream
                for stream in receipt["sourceProbe"]["streams"]
                if stream.get("index") == mapping["streamIndex"]
            )
            if (
                receipt["binding"]["mode"] == "verified_reuse"
                and sample_rate == 48000
                and source_stream.get("codec_name") == "pcm_s24le"
            ):
                source_samples = decode_audio_samples(
                    root / case["source"], mapping["streamIndex"]
                )
                output_rate, output_channels, output_samples = read_wav_samples(
                    root / case["audioPath"]
                )
                assert output_rate == 48000
                assert output_channels == source_stream["channels"]
                assert (
                    output_samples
                    == source_samples[
                        audio["sourceFirstSample"] : audio["sourceExclusiveSample"]
                    ]
                )
            compiler_probe = case.get("compilerBindingProbe")
            if compiler_probe is not None:
                assert compiler_probe["sourceAudioSampleRange"] == {
                    "startFrame": expected_first,
                    "endFrame": expected_exclusive,
                }
        if "syncMeasurements" in case:
            sync = case["syncMeasurements"]
            assert sync["sourceTruthMaxResidualMilliseconds"] <= 1
            assert sync["sourceTruthDriftMilliseconds"] <= 1
            assert sync["outputTruthMaxResidualMilliseconds"] <= 1
            assert sync["outputTruthDriftMilliseconds"] <= 1
            maximum_residual = max(
                maximum_residual, sync["outputTruthMaxResidualMilliseconds"]
            )
            maximum_drift = max(maximum_drift, sync["outputTruthDriftMilliseconds"])
    print(
        json.dumps(
            {
                "cases": len(record["cases"]),
                "artifactHashesVerified": checked,
                "maximumSyncResidualMilliseconds": maximum_residual,
                "maximumSyncDriftMilliseconds": maximum_drift,
                "humanVisualAudibleAcceptance": "pending",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
