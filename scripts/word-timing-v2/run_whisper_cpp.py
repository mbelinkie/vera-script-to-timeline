"""Run whisper.cpp (Research's incumbent recogniser) and save a T-C transcript.

Mirrors Research's invocation (`-m MODEL -f AUDIO -l en -ojf -np`, whole file,
no VAD) and adds `--dtw large.v3.turbo` so tokens carry DTW timestamps: the
best word timing whisper.cpp offers natively. Research itself keeps only
segment `offsets`, so its production timing is coarser than what is scored
here.

Words: tokens whose text starts with a space begin a new word; special tokens
(`[_...]`) are dropped. Word start = first token's DTW time (falls back to the
token's `offsets.from`), word end = last token's `offsets.to`, clamped so it
never precedes the start.

Usage: run_whisper_cpp.py --audio X-16k.wav --model ggml-large-v3-turbo.bin --out T-C-whisper.json
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import tempfile
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dtw", default="large.v3.turbo")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "whisper"
        t0 = time.monotonic()
        subprocess.run(["whisper-cli", "-m", str(args.model), "-f", str(args.audio), "-l", "en", "-ojf", "-of", str(base),
                        "-np", "--dtw", args.dtw], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wall = time.monotonic() - t0
        data = json.loads(base.with_suffix(".json").read_text())

    words: list[dict] = []
    for seg in data["transcription"]:
        for tok in seg.get("tokens", []):
            text = tok.get("text", "")
            if not text.strip() or text.startswith("[_"):
                continue
            t_dtw = tok.get("t_dtw", -1)
            start = (t_dtw * 10 if t_dtw is not None and t_dtw >= 0 else tok["offsets"]["from"]) / 1000
            end = tok["offsets"]["to"] / 1000
            if text.startswith(" ") or not words:
                words.append({"text": text.strip(), "start": start, "end": max(end, start + 0.01)})
            else:
                words[-1]["text"] += text
                words[-1]["end"] = max(words[-1]["end"], end, words[-1]["start"] + 0.01)
    out_words = [{"k": k, "text": w["text"], "start": round(w["start"], 3), "end": round(w["end"], 3),
                  "type": "event" if w["text"].startswith("[") or w["text"].startswith("(") else "word",
                  "confidence": None} for k, w in enumerate(words)]
    args.out.write_text(json.dumps({
        "source": "T-C-whisper", "provider": "whisper.cpp (local)", "model": args.model.name,
        "words": out_words, "transcript": " ".join(w["text"] for w in out_words),
        "provenance": {"flags": f"-l en -ojf -np --dtw {args.dtw}", "wallSeconds": round(wall, 1),
                       "timestampSemantics": "word start = first token DTW time (10 ms units); end = last token offsets.to",
                       "machine": f"{platform.platform()} {platform.machine()}"},
    }, indent=1))
    print(f"{args.out}: {len(out_words)} words, wall {wall:.1f}s")


if __name__ == "__main__":
    main()
