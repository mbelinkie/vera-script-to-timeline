#!/usr/bin/env python3
"""Parakeet TDT 0.6B v3 (int8 ONNX, onnx-asr, CPU) -> word-level T-C-parakeet.json.

Run with the preflight venv python:
  ~/.local/share/vera/issue-51-preflight/run-a/autosubs/parakeet-env/bin/python run_parakeet.py --audio A.wav --vad vad.json --out T-C-parakeet.json
Recognises each VAD segment (<=30 s) separately; onnx-asr gives per-token START times
(0.08 s frames) in seconds relative to the segment. Tokens beginning with a space start a
word; other tokens (subwords, punctuation) attach to the current word.
"""

import argparse
import glob
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time
import wave
from pathlib import Path

MODEL_GLOB = str(
    Path.home()
    / ".local/share/vera/issue-51-preflight/run-a/autosubs/app-caches/models/models--istupakov--parakeet-tdt-0.6b-v3-onnx/snapshots/*"
)
CAP = 0.5  # max word duration derived from token starts
FRAME = 0.08  # encoder frame (8x subsampling of 10 ms)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def words_from_segment(res, seg_start, seg_end):
    toks, ts = res.tokens or [], res.timestamps or []
    words = []  # dict(text, start, last_tok_idx)
    for i, (t, s) in enumerate(zip(toks, ts)):
        if t.startswith(" ") or not words:
            words.append({"text": t.strip(), "start": seg_start + s, "last": i})
        else:
            words[-1]["text"] += t
            words[-1]["last"] = i
    for w in words:
        nxt = w["last"] + 1
        start = w["start"]
        if nxt < len(ts):
            end = min(
                seg_start + ts[nxt], start + CAP
            )  # next token start (word or punctuation)
        else:
            end = min(start + CAP, seg_end)  # last token of segment: no successor
        w["end"] = max(end, start + FRAME)
    return [w for w in words if w["text"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--vad", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import numpy as np
    import onnx_asr
    import onnxruntime as rt

    rt.disable_telemetry_events()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    mdir = glob.glob(MODEL_GLOB)[0]
    with wave.open(a.audio, "rb") as f:
        assert (
            f.getnchannels() == 1
            and f.getsampwidth() == 2
            and f.getframerate() == 16000
        )
        x = (
            np.frombuffer(f.readframes(f.getnframes()), "<i2").astype(np.float32)
            / 32768
        )
    segs = json.load(open(a.vad))["segments"]
    assert all(b - a_ <= 30.0 for a_, b in segs)
    o = rt.SessionOptions()
    o.intra_op_num_threads = 8
    o.inter_op_num_threads = 1
    o.log_severity_level = 3
    t0 = time.monotonic()
    model = onnx_asr.load_model(
        "nemo-parakeet-tdt-0.6b-v3",
        mdir,
        quantization="int8",
        sess_options=o,
        providers=["CPUExecutionProvider"],
    ).with_timestamps()
    words, texts, seen = [], [], set()
    for s, e in segs:
        r = model.recognize(
            x[int(round(s * 16000)) : int(round(e * 16000))], sample_rate=16000
        )
        texts.append(r.text.strip())
        seen.update(round(t / FRAME, 3) % 1 for t in (r.timestamps or [])[:50])
        words += words_from_segment(r, s, e)
    wall = time.monotonic() - t0
    out_words = [
        {
            "k": k,
            "text": w["text"],
            "start": round(w["start"], 3),
            "end": round(w["end"], 3),
            "type": "word",
            "confidence": None,
        }
        for k, w in enumerate(words)
    ]
    files = {
        os.path.basename(p): sha(p)
        for p in sorted(glob.glob(mdir + "/*.onnx"))
        if "int8" in p or p.endswith("nemo128.onnx")
    }
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
        1 if sys.platform == "darwin" else 1024
    )
    out = {
        "source": "T-C-parakeet",
        "provider": "NVIDIA Parakeet (local, onnx-asr)",
        "model": "nemo-parakeet-tdt-0.6b-v3 (int8 ONNX, istupakov/parakeet-tdt-0.6b-v3-onnx)",
        "words": out_words,
        "transcript": " ".join(texts),
        "provenance": {
            "modelId": "nemo-parakeet-tdt-0.6b-v3",
            "repo": "istupakov/parakeet-tdt-0.6b-v3-onnx",
            "snapshot": os.path.basename(mdir),
            "quantization": "int8",
            "onnxSha256": files,
            "onnxAsrVersion": __import__("importlib.metadata").metadata.version(
                "onnx-asr"
            ),
            "onnxruntimeVersion": rt.__version__,
            "providers": ["CPUExecutionProvider"],
            "wallSeconds": round(wall, 1),
            "peakRssMB": round(
                rss / (1024 * 1024) if sys.platform == "darwin" else rss, 0
            ),
            "segmentsUsed": len(segs),
            "vadFile": os.path.basename(a.vad),
            "timestampSemantics": "onnx-asr token START times, 0.08 s frame grid (8x subsampling x 10 ms), relative to segment; word start = first token time + segment start",
            "endTimeDerivation": f"model supplies no end times. word end = min(start of the token following the word's last token in the same segment [any token, incl. punctuation], word start + {CAP} s); for the final word of a segment, min(word start + {CAP} s, segment end); minimum one frame (0.08 s). Approximate; to be refined by MFA.",
            "wordJoining": "tokens starting with a space begin a word; other tokens (subwords, punctuation) are appended; punctuation stays in word text",
            "machine": f"{platform.platform()} {platform.machine()}; "
            + subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
            ).stdout.strip()
            + "; 8 intra-op threads",
        },
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"{a.out}: {len(out_words)} words, wall {wall:.1f}s")


if __name__ == "__main__":
    main()
