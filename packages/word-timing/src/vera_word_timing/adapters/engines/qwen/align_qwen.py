"""A-QWEN: Qwen3-ForcedAligner-0.6B wrapper implementing ALIGNER-CONTRACT.md.
Runs inside the container (see Dockerfile). Paths are container paths."""

import argparse
import hashlib
import json
import os
import resource
import sys
import time
from importlib.metadata import version

REPO = "Qwen/Qwen3-ForcedAligner-0.6B"
REVISION = "c7cbfc2048c462b0d63a45797104fc9db3ad62b7"
LANGUAGE = os.environ.get("VERA_QWEN_LANGUAGE", "English")  # model-card language name


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True)
    ap.add_argument("--audio-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--variant", default="default")
    a = ap.parse_args()
    t0 = time.time()

    import soundfile as sf
    import torch
    from huggingface_hub import snapshot_download
    from qwen_asr import Qwen3ForcedAligner

    spec = json.load(open(a.segments))
    audio, sr = sf.read(
        os.path.join(a.audio_dir, spec["audio"]), dtype="float32", always_2d=True
    )
    audio = audio.mean(axis=1)
    off = float(spec.get("offsetSec", 0.0))

    path = snapshot_download(REPO, revision=REVISION)
    weights = {}
    for fn in sorted(os.listdir(path)):
        if fn.endswith(".safetensors"):
            weights[fn] = sha256(os.path.join(path, fn))
    torch.set_num_threads(os.cpu_count() or 1)
    model = Qwen3ForcedAligner.from_pretrained(
        path, dtype=torch.float32, device_map="cpu"
    )
    proc = model.aligner_processor
    frame_ms = model.timestamp_segment_time
    t_align = time.time()

    rows = []
    for seg in spec["segments"]:
        entries = seg["words"]
        # The model whitespace-splits text and strips every char that is not a
        # letter, digit or apostrophe. Mirror that per word so tokens map 1:1.
        cleaned = [proc.clean_token(w["text"]) for w in entries]
        keep = [k for k, c in enumerate(cleaned) if c]
        res = {}
        if keep:
            s, e = int(round(seg["start"] * sr)), int(round(seg["end"] * sr))
            try:
                out = model.align(
                    audio=(audio[s:e], sr),
                    text=" ".join(cleaned[k] for k in keep),
                    language=LANGUAGE,
                )[0]
                items = list(out)
                if len(items) == len(keep) and all(
                    it.text == cleaned[k] for it, k in zip(items, keep)
                ):
                    for it, k in zip(items, keep):
                        res[k] = (it.start_time, it.end_time)
                else:
                    print(
                        f"segment {seg['id']}: token mismatch {len(items)} vs {len(keep)}",
                        file=sys.stderr,
                    )
            except Exception as ex:  # no interpolation: whole segment fails
                print(f"segment {seg['id']}: {ex!r}", file=sys.stderr)
        for k, w in enumerate(entries):
            row = {"i": w["i"]}
            if "sub" in w:
                row["sub"] = w["sub"]
            if k in res:
                row["start"] = round(off + seg["start"] + float(res[k][0]), 3)
                row["end"] = round(off + seg["start"] + float(res[k][1]), 3)
                row["status"] = "aligned"
            else:
                row.update(start=None, end=None, status="failed")
            rows.append(row)

    pk = {
        p: version(p)
        for p in [
            "qwen-asr",
            "torch",
            "transformers",
            "numpy",
            "soundfile",
            "huggingface-hub",
            "accelerate",
            "safetensors",
        ]
    }
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024  # Linux: KiB
    json.dump(
        {
            "aligner": "A-QWEN",
            "variant": a.variant,
            "words": rows,
            "provenance": {
                "packages": pk,
                "models": [
                    {
                        "id": REPO,
                        "revision": REVISION,
                        "files": weights,
                        "sha256": weights.get("model.safetensors"),
                    }
                ],
                "settings": {
                    "frameMs": frame_ms,
                    "language": LANGUAGE,
                    "dtype": "float32",
                    "device": "cpu",
                    "units": "word",
                    "alignSeconds": round(time.time() - t_align, 2),
                },
                "platform": "linux/amd64 docker",
                "wallSeconds": round(time.time() - t0, 2),
                "peakRssBytes": rss,
            },
        },
        open(a.out, "w"),
        indent=1,
    )


if __name__ == "__main__":
    main()
