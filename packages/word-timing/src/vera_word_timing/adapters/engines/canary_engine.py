"""Canary-1B v2 engine (int8 ONNX via onnx-asr): forced-language recognition per segment.

Runs in the Parakeet runtime (onnx-asr 0.12.0, onnxruntime 1.23.2). Input: a
16 kHz mono WAV, a JSON list of [start, end] segments (each <= 30 s) and a
language code; output JSON: per-segment text. Canary is configured for
spoken-form output (no inverse text normalisation), so numbers come out as
words. Model: istupakov/canary-1b-v2-onnx@5ebc1520 (CC-BY-4.0); the folder is
given by VERA_CANARY_MODEL_DIR.
"""

import argparse
import json
import os
import time
import wave

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--segments", required=True)
    ap.add_argument("--language", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import onnx_asr
    import onnxruntime as rt

    rt.disable_telemetry_events()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    model_dir = os.environ.get("VERA_CANARY_MODEL_DIR", "")
    if not model_dir or not os.path.isdir(model_dir):
        raise SystemExit("canary model folder not found (VERA_CANARY_MODEL_DIR)")
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
    opts = rt.SessionOptions()
    opts.intra_op_num_threads = 8
    opts.log_severity_level = 3
    model = onnx_asr.load_model(
        "nemo-canary-1b-v2", model_dir, quantization="int8", sess_options=opts
    )
    t0 = time.monotonic()
    out = []
    for s, e in json.load(open(a.segments)):
        chunk = x[int(s * 16000) : int(e * 16000)]
        text = str(
            model.recognize(chunk, sample_rate=16000, language=a.language)
        ).strip()
        out.append({"start": s, "end": e, "text": text})
    json.dump(
        {
            "model": "istupakov/canary-1b-v2-onnx@5ebc1520cef7b6b318b3526ad17adbfe00bc1bfc int8",
            "language": a.language,
            "wallSeconds": round(time.monotonic() - t0, 1),
            "segments": out,
        },
        open(a.out, "w"),
        ensure_ascii=False,
    )


if __name__ == "__main__":
    main()
