"""Benchmark runner (called by bench.sh inside the kit's own tools environment).

Decodes the public-domain LibriVox MP3, resamples to 16 kHz mono (soxr, so no
ffmpeg is needed), then times the #45 pipelines with the engines bench.sh
installed:

- Research profile: Parakeet -> MFA (no script);
- Script to Timeline local profile: the same recognition -> script
  reconciliation against the public-domain text -> MFA.

Writes bench-results.json (machine, versions, per-stage seconds, real-time
factors, every aligned word time) and, when reference-intel.json is present,
compares word times unit by unit to that reference run. The audio and text
are public domain; nothing private is read or written.
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import os
import platform
import subprocess
import sys
import time
import wave
from pathlib import Path


def sysctl(name: str) -> str:
    try:
        return subprocess.run(
            ["sysctl", "-n", name], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def versions(python: Path, names: list[str]) -> dict[str, str]:
    code = (
        "import importlib.metadata as m, json, sys\n"
        "out = {}\n"
        "for n in sys.argv[1:]:\n"
        "    try:\n"
        "        out[n] = m.version(n)\n"
        "    except m.PackageNotFoundError:\n"
        "        pass\n"
        "print(json.dumps(out))\n"
    )
    try:
        done = subprocess.run(
            [str(python), "-c", code, *names],
            capture_output=True,
            text=True,
            check=True,
        )
        return dict(json.loads(done.stdout))
    except (OSError, subprocess.CalledProcessError, ValueError):
        return {}


def decode(mp3: Path, wav: Path) -> float:
    import numpy as np
    import soundfile as sf
    import soxr

    x, sr = sf.read(str(mp3), dtype="float32", always_2d=True)
    y = soxr.resample(x.mean(axis=1), sr, 16000, quality="HQ")
    pcm = np.clip(np.round(y * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())
    return len(pcm) / 16000


def compare(mine: list[list], ref: list[list]) -> dict:
    """Unit-by-unit start/end differences in ms, keyed by (tokenIndex, sub, text)."""
    r = {(t, s, x): (a, b) for t, s, x, a, b in ref if a is not None}
    d_on, d_off, missing = [], [], 0
    for t, s, x, a, b in mine:
        if a is None:
            continue
        if (t, s, x) not in r:
            missing += 1
            continue
        ra, rb = r[(t, s, x)]
        d_on.append(abs(a - ra))
        d_off.append(abs(b - rb))
    if not d_on:
        return {"comparable": 0, "unmatched": missing}
    q = sorted(d_on + d_off)
    return {
        "comparable": len(d_on),
        "unmatched": missing,
        "identical": sum(a == 0 and b == 0 for a, b in zip(d_on, d_off, strict=True)),
        "medianMs": q[len(q) // 2],
        "p95Ms": q[int(0.95 * (len(q) - 1))],
        "maxMs": q[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--mp3", type=Path, required=True)
    parser.add_argument("--setup-seconds", type=float, default=0.0)
    args = parser.parse_args()
    kit, work = args.kit, args.work
    code_root = kit / "code" if (kit / "code").exists() else kit.parents[1]  # src/
    sys.path.insert(0, str(code_root))
    from vera_word_timing.adapters.local_engines import (
        EngineConfig,
        MfaAligner,
        ParakeetRecognizer,
    )
    from vera_word_timing.artifacts import AudioRef, file_hash
    from vera_word_timing.conformance import check_alignment
    from vera_word_timing.ports import ProjectPolicy
    from vera_word_timing.script_reconcile import reconcile

    wav = work / "gettysburg-16k.wav"
    t0 = time.monotonic()
    duration = decode(args.mp3, wav)
    t_decode = time.monotonic() - t0
    with wave.open(str(wav)) as w:
        audio = AudioRef(wav, file_hash(wav), w.getframerate(), w.getnframes())
    snap = next(
        (work / "hf").glob(
            "hub/models--istupakov--parakeet-tdt-0.6b-v3-onnx/snapshots/*"
        ),
        None,
    )
    envs = work / "envs"
    mfa_bin = envs / "mfa/bin"
    config = EngineConfig(
        tools_python=Path(sys.executable),
        parakeet_python=envs / "parakeet/bin/python",
        parakeet_model_glob=str(snap) if snap else None,
        mfa_command=(str(mfa_bin / "python"),),
        # Not "mfa-home": MFA rejects a corpus whose path string starts with
        # its root dir (".bench/mfa"), a plain prefix check.
        mfa_home=work / "aligner-work",
        mfa_env={
            "MFA_ROOT_DIR": str(work / "mfa"),
            "PATH": f"{mfa_bin}:{os.environ.get('PATH', '')}",
        },
        work_dir=work / "engine-work",
    )
    policy = ProjectPolicy()
    timings: dict[str, float] = {"decodeResample": t_decode}
    t = time.monotonic()
    recognition = ParakeetRecognizer(config).recognise(
        audio, language="en", policy=policy
    )
    timings["parakeet"] = time.monotonic() - t
    t = time.monotonic()
    research = MfaAligner(config).align(audio, recognition, policy=policy)
    timings["mfaResearch"] = time.monotonic() - t
    script = (kit / "gettysburg.txt").read_text()
    dictionary = (
        work / "mfa/pretrained_models/dictionary/english_us_arpa.dict"
    ).read_text(errors="ignore")
    t = time.monotonic()
    rcn = reconcile(recognition, script, dictionary)
    timings["reconcile"] = time.monotonic() - t
    t = time.monotonic()
    stt = MfaAligner(config).align(
        audio, recognition, policy=policy, reconciliation=rcn
    )
    timings["mfaScriptToTimeline"] = time.monotonic() - t

    def rows(ali: dict) -> list[list]:
        return [
            [w["tokenIndex"], w["sub"], w["text"], w["startMs"], w["endMs"]]
            for w in ali["words"]
        ]

    fails = check_alignment(audio, recognition, research) + check_alignment(
        audio, recognition, stt, rcn
    )
    result = {
        "schema": "vera-word-timing-bench/v1",
        "machine": {
            "chip": sysctl("machdep.cpu.brand_string"),
            "model": sysctl("hw.model"),
            "cores": sysctl("hw.ncpu"),
            "memoryBytes": sysctl("hw.memsize"),
            "macos": platform.mac_ver()[0],
            "arch": platform.machine(),
        },
        "versions": {
            "tools": versions(
                Path(sys.executable),
                ["silero-vad", "torch", "onnxruntime", "numpy", "soxr"],
            ),
            "parakeet": versions(
                config.parakeet_python or Path(), ["onnx-asr", "onnxruntime", "numpy"]
            ),
            "mfa": versions(mfa_bin / "python", ["montreal-forced-aligner", "kalpy"]),
            "packages": {n: md.version(n) for n in ("jsonschema",)},
        },
        "audio": {
            "source": "LibriVox gettysburg_address_librivox (public domain)",
            "seconds": round(duration, 2),
            "wavHash": audio.original_hash,
        },
        "setupSeconds": args.setup_seconds,
        "timingsSeconds": {k: round(v, 2) for k, v in timings.items()},
        "realTimeFactor": {k: round(v / duration, 3) for k, v in timings.items()},
        "conformance": "PASS" if not fails else fails[:10],
        "recognitionTokens": len(recognition["tokens"]),
        "transcript": " ".join(t["display"] for t in recognition["tokens"]),
        "research": {"artifactId": research["artifactId"], "words": rows(research)},
        "scriptToTimeline": {
            "artifactId": stt["artifactId"],
            "words": rows(stt),
            "scriptMatched": sum(u["scriptIndex"] is not None for u in rcn["units"]),
        },
    }
    ref_path = kit / "reference-intel.json"
    if ref_path.exists():
        ref = json.loads(ref_path.read_text())
        result["vsReference"] = {
            "referenceMachine": ref.get("machine", {}).get("chip"),
            "sameTranscript": ref.get("transcript") == result["transcript"],
            "research": compare(result["research"]["words"], ref["research"]["words"]),
            "scriptToTimeline": compare(
                result["scriptToTimeline"]["words"], ref["scriptToTimeline"]["words"]
            ),
        }
    out = kit / "bench-results.json"
    out.write_text(json.dumps(result, indent=1))
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("machine", "timingsSeconds", "realTimeFactor", "conformance")
            },
            indent=1,
        )
    )
    if "vsReference" in result:
        print(json.dumps(result["vsReference"], indent=1))
    print(f"\nDone. Send this file back: {out}")


if __name__ == "__main__":
    main()
