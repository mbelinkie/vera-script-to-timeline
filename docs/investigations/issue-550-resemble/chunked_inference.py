"""Offline CPU screen using shorter chunks than the upstream CLI default."""
import sys
import time
from pathlib import Path

import torch
import torchaudio
from resemble_enhance.enhancer.inference import load_enhancer
from resemble_enhance.inference import inference

source, target = map(Path, sys.argv[1:3])
if target.exists():
    raise SystemExit(f'Refusing to overwrite {target}')
started = time.monotonic()
audio, rate = torchaudio.load(source)
model = load_enhancer('/opt/models/enhancer_stage2', 'cpu')
model.configurate_(nfe=64, solver='midpoint', lambd=1.0, tau=0.5)
with torch.inference_mode():
    result, rate = inference(model, audio.mean(0), rate, 'cpu', chunk_seconds=5.0, overlap_seconds=1.0)
torchaudio.save(target, result[None], rate)
print(f'Elapsed seconds including model load: {time.monotonic() - started:.2f}', flush=True)
