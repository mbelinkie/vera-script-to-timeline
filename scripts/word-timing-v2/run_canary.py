"""NVIDIA Canary-1B v2 (int8 ONNX via onnx-asr) with a forced source language.

Recognition only (no timestamps); word timing comes from the aligner. The
audio is cut at VAD segments of at most 30 s (Canary is an encoder-decoder
model; long inputs are not supported), each decoded with `language=LANG`
(source and target the same, so no translation), and the text is joined.

Run in the Parakeet environment (onnx-asr 0.12.0, onnxruntime 1.23.2):
  run_canary.py --audio X-16k.wav --vad vad.json --language de --out canary.json --model-dir DIR
Model: istupakov/canary-1b-v2-onnx at a pinned revision (CC-BY-4.0).
"""

import argparse
import json
import math
import os
import time
import wave

import numpy as np

REPO = "istupakov/canary-1b-v2-onnx"
REVISION = "5ebc1520cef7b6b318b3526ad17adbfe00bc1bfc"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--vad", required=True)
    ap.add_argument("--language", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--model-dir", required=True, help="folder with the pinned int8 files"
    )
    a = ap.parse_args()
    import onnx_asr
    import onnxruntime as rt

    rt.disable_telemetry_events()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    path = a.model_dir
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
    segments = []
    for s, e in json.load(open(a.vad))["segments"]:  # split anything over 30 s evenly
        k = max(1, math.ceil((e - s) / 30.0))
        segments += [(s + i * (e - s) / k, s + (i + 1) * (e - s) / k) for i in range(k)]
    opts = rt.SessionOptions()
    opts.intra_op_num_threads = 8
    opts.log_severity_level = 3
    model = onnx_asr.load_model(
        "nemo-canary-1b-v2", path, quantization="int8", sess_options=opts
    )
    t0 = time.monotonic()
    texts = []
    for s, e in segments:
        chunk = x[int(s * 16000) : int(e * 16000)]
        texts.append(
            str(model.recognize(chunk, sample_rate=16000, language=a.language)).strip()
        )
    wall = time.monotonic() - t0
    json.dump(
        {
            "model": f"{REPO}@{REVISION} int8",
            "language": a.language,
            "segments": len(segments),
            "wallSeconds": round(wall, 1),
            "text": " ".join(t for t in texts if t),
            "perSegment": [
                {"start": round(s, 3), "end": round(e, 3), "text": t}
                for (s, e), t in zip(segments, texts, strict=True)
            ],
        },
        open(a.out, "w"),
        ensure_ascii=False,
        indent=1,
    )
    print(f"{a.out}: {len(segments)} segments, wall {wall:.1f}s")


if __name__ == "__main__":
    main()
