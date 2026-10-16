"""Small installed-build check of the accepted zero-order-hold sampling route."""

import hashlib
import json
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path


def run(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(args, input=data, capture_output=True, check=True).stdout


def main() -> None:
    results = []
    with tempfile.TemporaryDirectory() as scratch:
        for rate in ("24000/1001", "24", "25", "30000/1001", "30"):
            source = Path(scratch) / "source.mkv"
            # Every decoded frame has a distinct constant luma value.
            frames = b"".join(bytes([16 + n * 3]) * 256 for n in range(60))
            run(
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "-s",
                "16x16",
                "-framerate",
                rate,
                "-i",
                "pipe:0",
                "-c:v",
                "ffv1",
                str(source),
                data=frames,
            )
            common = (
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(source),
                "-vf",
            )
            suffix = (
                "-frames:v",
                "40",
                "-fps_mode",
                "passthrough",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "pipe:1",
            )
            fps = "fps=24000/1001:start_time=0:round=up:eof_action=pass"
            legacy = run(
                *common, "trim=start_frame=3,setpts=PTS-STARTPTS," + fps, *suffix
            )
            raw = run(
                *common,
                f"trim=start_frame=3,settb=expr={1 / Fraction(rate)},setpts=N," + fps,
                *suffix,
            )
            observed = [round((raw[i] - 16) / 3) for i in range(0, len(raw), 256)]
            expected = [
                3 + int(j * Fraction(rate) / Fraction(24000, 1001)) for j in range(40)
            ]
            assert observed == expected, (rate, observed, expected)
            results.append(
                {
                    "rate": rate,
                    "sourceHash": "sha256:"
                    + hashlib.sha256(source.read_bytes()).hexdigest(),
                    "expected": expected,
                    "legacyObserved": [
                        round((legacy[i] - 16) / 3) for i in range(0, len(legacy), 256)
                    ],
                    "observed": observed,
                    "verifiedCommand": [
                        *common,
                        f"trim=start_frame=3,settb=expr={1 / Fraction(rate)},setpts=N,"
                        + fps,
                        *suffix,
                    ],
                }
            )
    record = {
        "instrument": "16x16 FFV1 numbered-luma MKV (sampling-route experiment only)",
        "ffmpeg": run("ffmpeg", "-version").decode(),
        "ffprobe": run("ffprobe", "-version").decode(),
        "results": results,
    }
    encoded = json.dumps(record, indent=2)
    if len(sys.argv) == 2:
        with Path(sys.argv[1]).open("x") as output:
            output.write(encoded + "\n")
        print("Wrote sampling-route evidence to", sys.argv[1])
    else:
        print(encoded)


if __name__ == "__main__":
    main()
