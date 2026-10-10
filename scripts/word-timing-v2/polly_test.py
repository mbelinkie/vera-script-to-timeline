"""How much do missing word ends matter for Polly narration, and can MFA supply them?

VERA narration uses AWS Polly neural voices. Polly speech marks give exact word
*starts*; VERA derives each word end from the next word's start (or the audio
end) and labels it `word_start_with_derived_end`. This test synthesises the
recording-B script as narration blocks (one per prompter paragraph, the same
16 kHz PCM + word/sentence marks request as `narration/polly.py`), aligns the
exact text with MFA, and reports:

- **MFA reliability on synthetic speech:** |MFA onset - Polly start|.
- **Derived-end error:** derived end - MFA end, split by what follows the word
  (connected word, a pause, or the end of the block).
- **Block-final words:** derived end (= audio end) and MFA end against an
  energy-measured audible end (last 10 ms window above -40 dBFS, the #53 quiet
  gate), i.e. how much trailing silence a "guessed" clip end would include.

Synthesis costs ~4,000 characters per voice pair (neural list price $16 per
million characters, about 6 cents). Audio and marks stay in
~/.local/share/vera/word-timing-v2/polly-test; aggregates are printed.

Usage: polly_test.py --voices Joanna,Matthew [--skip-synth]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from textnorm import word_entries

DATA = Path.home() / ".local/share/vera/word-timing-v2"
OUT = DATA / "polly-test"
SR = 16000
GAP_S = 1.0
HERE = Path(__file__).resolve().parent


def synth(text: str, voice: str, stem: Path) -> None:
    def base(
        outfile: Path,
    ) -> list[str]:  # outfile first: --speech-mark-types is a list option
        return [
            "aws",
            "polly",
            "synthesize-speech",
            str(outfile),
            "--engine",
            "neural",
            "--voice-id",
            voice,
            "--text",
            text,
        ]

    if not stem.with_suffix(".pcm").exists():
        subprocess.run(
            [
                *base(stem.with_suffix(".pcm")),
                "--output-format",
                "pcm",
                "--sample-rate",
                str(SR),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    if not stem.with_suffix(".marks").exists():
        subprocess.run(
            [
                *base(stem.with_suffix(".marks")),
                "--output-format",
                "json",
                "--speech-mark-types",
                "word",
                "sentence",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )


def pct(v: list[float], q: float) -> float:
    s = sorted(v)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))] if s else float("nan")


def summary(label: str, v: list[float]) -> str:
    if not v:
        return f"{label:44s} n   0"
    a = [abs(x) for x in v]
    return (
        f"{label:44s} n {len(v):3d}  median {statistics.median(v):6.0f}  |median| {statistics.median(a):5.0f}"
        f"  p95|.| {pct(a, 0.95):5.0f}  max {max(a):5.0f} ms"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voices", default="Joanna,Matthew")
    parser.add_argument("--skip-synth", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    blocks = [
        p.strip()
        for p in (DATA / "scripts/rec-b-prompter.txt").read_text().split("\n\n")
        if p.strip()
    ]
    env = {
        **os.environ,
        "MAMBA_ROOT_PREFIX": str(Path.home() / ".local/share/micromamba"),
    }

    for voice in args.voices.split(","):
        vdir = OUT / voice
        vdir.mkdir(exist_ok=True)
        audio, tokens, polly, segs, block_info = [], [], [], [], []
        t0 = 0.0
        for n, text in enumerate(blocks):
            stem = vdir / f"block-{n:02d}"
            if not args.skip_synth:
                synth(text, voice, stem)
            pcm = np.frombuffer(stem.with_suffix(".pcm").read_bytes(), dtype="<i2")
            marks = [
                json.loads(line)
                for line in stem.with_suffix(".marks").read_text().splitlines()
                if line.strip()
            ]
            words = [m for m in marks if m["type"] == "word"]
            dur = len(pcm) / SR
            first = len(tokens)
            for k, m in enumerate(words):
                start = t0 + m["time"] / 1000
                derived = t0 + (
                    words[k + 1]["time"] / 1000 if k + 1 < len(words) else dur
                )
                polly.append(
                    {
                        "start": start,
                        "derivedEnd": derived,
                        "final": k + 1 == len(words),
                        "block": n,
                    }
                )
                tokens.append(m["value"])
            entries = word_entries(tokens[first:])
            for e in entries:
                e["i"] += first
            segs.append(
                {
                    "id": f"b{n:02d}",
                    "start": round(t0, 3),
                    "end": round(t0 + dur, 3),
                    "words": entries,
                }
            )
            block_info.append((t0, dur))
            audio.append(pcm)
            audio.append(np.zeros(int(GAP_S * SR), dtype="<i2"))
            t0 += dur + GAP_S
        wav = vdir / f"polly-{voice}-16k.wav"
        sf.write(wav, np.concatenate(audio), SR, subtype="PCM_16")
        seg_file = vdir / "segments.json"
        seg_file.write_text(
            json.dumps({"audio": wav.name, "offsetSec": 0.0, "segments": segs})
        )
        result = vdir / "mfa.json"
        if not result.exists():
            subprocess.run(
                [
                    "micromamba",
                    "run",
                    "-n",
                    "mfa",
                    "python",
                    "align_mfa.py",
                    "--segments",
                    str(seg_file),
                    "--audio-dir",
                    str(vdir),
                    "--out",
                    str(result),
                    "--variant",
                    "english_us_arpa",
                ],
                cwd=HERE / "mfa",
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        rows = json.loads(result.read_text())["words"]
        mfa: dict[int, list[float]] = {}
        for r in rows:
            if r["status"] == "aligned":
                cur = mfa.setdefault(r["i"], [r["start"], r["end"]])
                cur[0], cur[1] = min(cur[0], r["start"]), max(cur[1], r["end"])

        # energy envelope for audible block ends
        x, _ = sf.read(wav, dtype="float32")
        win = SR // 100
        rms = np.sqrt(np.convolve(x * x, np.ones(win) / win, mode="same"))
        loud = rms > 10 ** (-40 / 20)

        onset, connected, prepause, final_derived, final_mfa, pauses = (
            [],
            [],
            [],
            [],
            [],
            [],
        )
        energy_vs_mfa = []
        for i, p in enumerate(polly):
            if i not in mfa:
                continue
            ms, me = mfa[i]
            onset.append((ms - p["start"]) * 1000)
            overhang = (p["derivedEnd"] - me) * 1000
            if p["final"]:
                b0, bd = block_info[p["block"]]
                seg = loud[int(ms * SR) : int((b0 + bd) * SR)]
                idx = np.nonzero(seg)[0]
                audible = ms + (idx[-1] + 1) / SR if len(idx) else me
                final_derived.append((p["derivedEnd"] - audible) * 1000)
                final_mfa.append((me - audible) * 1000)
            elif i + 1 in mfa and mfa[i + 1][0] - me >= 0.15:
                prepause.append(overhang)
                nxt = polly[i + 1]["start"]
                seg = loud[int(ms * SR) : int(nxt * SR)]
                quiet_run = np.convolve(
                    ~seg, np.ones(SR // 10, dtype=int), mode="valid"
                )  # 100 ms of quiet
                q = np.nonzero(quiet_run == SR // 10)[0]
                if len(q):
                    energy_vs_mfa.append(((ms + q[0] / SR) - me) * 1000)
                pauses.append((mfa[i + 1][0] - me) * 1000)
            else:
                connected.append(overhang)
        aligned = len(mfa)
        print(
            f"\n== Polly neural '{voice}': {len(blocks)} blocks, {len(polly)} words, MFA aligned {aligned}"
        )
        print(summary("MFA onset - Polly start", onset))
        print(summary("derived end - MFA end, connected words", connected))
        print(summary("derived end - MFA end, word before a pause", prepause))
        print(
            f"{'':44s} (pauses: median {statistics.median(pauses) if pauses else 0:.0f} ms, max {max(pauses) if pauses else 0:.0f} ms)"
        )
        print(summary("pre-pause: energy end (no MFA) - MFA end", energy_vs_mfa))
        print(summary("block-final: derived end - audible end", final_derived))
        print(summary("block-final: MFA end - audible end", final_mfa))


if __name__ == "__main__":
    main()
