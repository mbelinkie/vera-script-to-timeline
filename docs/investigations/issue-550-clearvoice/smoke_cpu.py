import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from clearvoice import ClearVoice


def main() -> None:
    if torch.version.cuda is not None or torch.cuda.is_available():
        raise RuntimeError("Expected the CPU-only PyTorch build")

    sample_rate = 48_000
    sample_count = sample_rate
    time = np.arange(sample_count, dtype=np.float32) / sample_rate
    rng = np.random.default_rng(550)
    audio = (0.08 * np.sin(2 * np.pi * 220 * time) + 0.005 * rng.standard_normal(sample_count)).astype(np.float32)

    with tempfile.TemporaryDirectory(prefix="clearvoice-cpu-") as directory:
        source = Path(directory) / "synthetic.wav"
        sf.write(source, audio, sample_rate)

        clearvoice = ClearVoice(task="speech_enhancement", model_names=["MossFormer2_SE_48K"])
        output = clearvoice(input_path=str(source), online_write=False)

    while isinstance(output, (list, tuple)) and len(output) == 1:
        output = output[0]
    if isinstance(output, dict) and len(output) == 1:
        output = next(iter(output.values()))

    enhanced = np.asarray(output, dtype=np.float32)
    if enhanced.size == 0 or not np.isfinite(enhanced).all():
        raise RuntimeError(f"Invalid enhancement output: shape={enhanced.shape}")

    print(f"CPU inference passed: input={audio.shape}, output={enhanced.shape}, rate={sample_rate}")


if __name__ == "__main__":
    main()
