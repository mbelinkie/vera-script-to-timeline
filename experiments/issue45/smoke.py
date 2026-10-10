"""Real-engine smoke run: adapters + conformance on a local recording.

Runs a recogniser adapter (Parakeet, or YouTube captions with --captions) and
the MFA adapter through `check_pair`, writes both artifacts to --out, and, when
--reference RESULT.json is given (a prior aligner run on the same text),
reports how closely the adapter's word times match it. Engine runtimes come
from the VERA_* environment variables (see adapters/local_engines.py).
Prints aggregates only; private audio and transcripts stay where they are.

Usage:
  python -m experiments.issue45.smoke --audio X-16k.wav --out DIR
      [--captions X.en.json3] [--reference RESULT.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import wave
from pathlib import Path

from experiments.issue45.adapters.local_engines import (
    EngineConfig,
    MfaAligner,
    ParakeetRecognizer,
)
from experiments.issue45.adapters.youtube_captions import YouTubeCaptionRecognizer
from experiments.issue45.artifacts import AudioRef, file_hash
from experiments.issue45.conformance import check_alignment, check_pair
from experiments.issue45.ports import ProjectPolicy, RecognizerPort


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--captions", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument(
        "--full-conformance",
        action="store_true",
        help="also run check_pair (runs each engine twice)",
    )
    args = parser.parse_args()
    with wave.open(str(args.audio)) as w:
        audio = AudioRef(
            args.audio, file_hash(args.audio), w.getframerate(), w.getnframes()
        )
    config = EngineConfig.from_env()
    recognizer: RecognizerPort = (
        YouTubeCaptionRecognizer(args.captions)
        if args.captions
        else ParakeetRecognizer(config)
    )
    aligner = MfaAligner(config)
    policy = ProjectPolicy()
    t0 = time.monotonic()
    rec = recognizer.recognise(audio, language="en", policy=policy)
    t1 = time.monotonic()
    ali = aligner.align(audio, rec, policy=policy)
    t2 = time.monotonic()
    fails = check_alignment(audio, rec, ali)
    if args.full_conformance:
        fails += check_pair(recognizer, aligner, audio, language="en", policy=policy)
    args.out.mkdir(parents=True, exist_ok=True)
    kind = rec["identity"]["recognizer"]["kind"]
    (args.out / f"{kind}.recognition.json").write_text(json.dumps(rec, indent=1))
    (args.out / f"{kind}.alignment.json").write_text(json.dumps(ali, indent=1))
    words = ali["words"]
    acoustic = sum(w["status"] == "acoustic" for w in words)
    print(
        f"recogniser {kind}: {len(rec['tokens'])} tokens in {t1 - t0:.1f}s; "
        f"MFA: {acoustic}/{len(words)} units acoustic in {t2 - t1:.1f}s"
    )
    print("conformance:", "PASS" if not fails else f"{len(fails)} failures")
    for f in fails[:10]:
        print("  ", f)
    if args.reference:
        ref = {
            (r["i"], r.get("sub", 0)): r
            for r in json.loads(args.reference.read_text())["words"]
            if r["status"] == "aligned"
        }
        d_on, d_off = [], []
        for w in words:
            r = ref.get((w["tokenIndex"], w["sub"]))
            if r and w["status"] == "acoustic":
                d_on.append(abs(w["startMs"] - round(r["start"] * 1000)))
                d_off.append(abs(w["endMs"] - round(r["end"] * 1000)))
        if d_on:
            print(
                f"vs reference: {len(d_on)} shared units; onset |diff| median "
                f"{statistics.median(d_on):.0f} ms max {max(d_on)}; offset median "
                f"{statistics.median(d_off):.0f} ms max {max(d_off)}; identical "
                f"{sum(a == 0 and b == 0 for a, b in zip(d_on, d_off, strict=True))}"
            )


if __name__ == "__main__":
    main()
